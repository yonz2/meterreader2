import os
import gridfs
from pymongo import MongoClient
from bson import ObjectId  # Import ObjectId to check and convert
from io import BytesIO
import cv2  # Required if image is in numpy array format
from PIL import Image  # Optional for PIL image objects



# Import your custom modules
import helpers.config as config 

# Make sure to use the same logger as therest of hte application
import logging
logger_name = os.environ.get("LOGGER_NAME") or os.path.splitext(os.path.basename(__file__))[0]
logger = logging.getLogger(logger_name)


# Helper function to make metadata JSON serializable
def convert_to_serializable(data):
    """
    Recursively converts non-serializable fields (like ObjectId) in a dictionary to JSON serializable formats.
    :param data: The metadata dictionary.
    :return: A JSON serializable version of the dictionary.
    """
    if isinstance(data, dict):
        return {key: convert_to_serializable(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [convert_to_serializable(item) for item in data]
    elif isinstance(data, ObjectId):
        return str(data)  # Convert ObjectId to string
    else:
        return data

class MongoDBHandler:
    def __init__(self, config): 
        """
        Initialize the MongoDB handler with GridFS support.
        :param config: The Config object providing configuration data.
        """
        self.config = config

        mongodb_uri = self.config.get("MongoDB", "URI", "mongodb://172.20.0.2:27017/")
        mongodb_database = self.config.get("MongoDB", "database", "meterreader")
        mongodb_collection = self.config.get("MongoDB", "collection", "image_metadata")

        self.client = MongoClient(mongodb_uri)
        self.db = self.client[mongodb_database]
        self.fs = gridfs.GridFS(self.db)
        self.collection = self.db[mongodb_collection]

    def insert_image(self, filename, image_object):
        """
        Store an image in GridFS.
        :param filename: Name of the image file.
        :param image_object: Image object from YOLOv11 (e.g., numpy array or PIL image).
        :return: The ID of the stored file.
        """
        # Convert image_object (e.g., numpy array) to binary stream
        if isinstance(image_object, Image.Image):  # If it's a PIL Image
            buffer = BytesIO()
            image_object.save(buffer, format="JPEG")
            data = buffer.getvalue()
        elif isinstance(image_object, (bytes, bytearray)):
            # If it's already in bytes format
            data = image_object
        else:
            # Assume OpenCV/numpy image; encode to bytes
            success, encoded_image = cv2.imencode('.jpg', image_object)
            if not success:
                raise ValueError("Failed to encode the image to bytes")
            data = encoded_image.tobytes()

        # Store the binary data in GridFS
        return self.fs.put(data, filename=filename)

    def insert_file_from_path(self, file_path):
        """
        Insert a file into GridFS, replacing an existing file with the same filename if it exists.
        :param file_path: Path to the file to be stored.
        :return: The ID of the stored file in GridFS.
        """
        try:
            filename = os.path.basename(file_path)

            # Check for existing file with the same filename and delete it
            existing_file = self.fs.find_one({"filename": filename})
            if existing_file:
                self.fs.delete(existing_file._id)
                logger.warning(f"Replaced existing file with filename '{filename}' in GridFS.")

            # Insert the new file into GridFS
            with open(file_path, "rb") as file:
                file_content = file.read()
            file_id = self.insert_image(filename, file_content)
            
            return file_id
        except FileNotFoundError:
            raise FileNotFoundError(f"The file at path '{file_path}' was not found.")
        except Exception as e:
            raise Exception(f"An error occurred while inserting the file: {e}")


    def update_image_metadata(self, filename, metadata):
        """
        Update or insert image metadata in the specified collection.
        :param filename: Name of the image file.
        :param metadata: Metadata dictionary.
        """
        self.collection.update_one({"filename": filename}, {"$set": metadata}, upsert=True)

    def get_image_data(self, filename):
        """
        Retrieve an image's binary data from GridFS by filename.
        
        Args:
            filename (str): Name of the image file.
        
        Returns:
            tuple: (binary data of the image, content type)
        
        Raises:
            FileNotFoundError: If the file is not found in GridFS.
        """
        file_obj = self.fs.find_one({"filename": filename})
        if file_obj:
            # Attempt to determine content type (default to 'image/jpeg' if not provided)
            content_type = file_obj.content_type if hasattr(file_obj, "content_type") else "image/jpeg"
            return file_obj.read(), content_type  # Return binary data and content type
        else:
            raise FileNotFoundError(f"File '{filename}' not found in GridFS.")

    def get_image_metadata(self, limit=16):
        """
        Retrieve metadata for the latest processed images from the metadata collection.
        Sorts by the 'processed_at' timestamp.
        :param limit: Number of records to fetch.
        """
        return list(
            self.collection.find().sort([("processed_at", -1)]).limit(limit)
        )

    def get_metadata_by_filename(self, filename):
        """
        Retrieve metadata for a specific image by its filename.
        :param filename: Name of the image file.
        :return: Metadata dictionary for the image, or None if not found.
        """
        try:
            metadata = self.collection.find_one({"filename": filename})
            return metadata
        except Exception as e:
            raise Exception(f"An error occurred while fetching metadata for '{filename}': {e}")

    def get_grouped_metadata(self, limit=16):
        """
        Fetch metadata from MongoDB, group by filename, and ensure the result is JSON-serializable.
        
        :param limit: Number of records to fetch (default: 16).
        :return: A dictionary with grouped metadata, JSON-serializable.
        """
        try:
            # Fetch the metadata documents from MongoDB, sorted by the most recent
            raw_metadata = list(self.collection.find().sort([("_id", -1)]).limit(limit))

            # Convert raw MongoDB documents into JSON-serializable format
            metadata = convert_to_serializable(raw_metadata)

            # Group metadata by filename
            grouped_metadata = {}
            for item in metadata:
                filename = item['filename']
                grouped_metadata[filename] = item  # Directly store the metadata object

            return grouped_metadata

        except Exception as ex:
            raise Exception(f"Error fetching grouped metadata: {ex}")
        
    def prune_old_entries(self, retain_count=16):
        """
        Deletes all images and related files from GridFS, and metadata from the collection, 
        except for the latest `retain_count` entries.
        
        :param retain_count: Number of latest entries to retain (default: 16).
        """
        try:
            # Sort by _id and fetch the IDs and file references of entries to delete
            all_entries = list(self.collection.find({}, {"_id": 1, "filename": 1, "detected_object_file": 1, 
                                                        "marked_image": 1, "scaled_imagepath": 1})
                                .sort([("_id", -1)]))  # Latest first
            entries_to_delete = all_entries[retain_count:]  # Skip the latest `retain_count`

            # Extract IDs and all related filenames to delete
            ids_to_delete = [entry["_id"] for entry in entries_to_delete]
            filenames_to_delete = []
            
            for entry in entries_to_delete:
                # Collect all filenames associated with this entry
                filenames_to_delete.append(entry.get("filename"))
                filenames_to_delete.append(entry.get("detected_object_file"))
                filenames_to_delete.append(entry.get("marked_image"))
                filenames_to_delete.append(entry.get("scaled_imagepath"))
            
            # Remove None values or duplicates
            filenames_to_delete = list(filter(None, set(filenames_to_delete)))

            deleted_files_count = 0

            if ids_to_delete:
                # Delete GridFS files associated with the entries
                for filename in filenames_to_delete:
                    try:
                        grid_out = self.fs.find_one({"filename": filename})
                        if grid_out:
                            self.fs.delete(grid_out._id)
                            deleted_files_count += 1
                    except Exception as ex:
                        self.logger.log_message(f"Error deleting GridFS file '{filename}': {ex}")

                # Delete metadata entries from the collection
                delete_result = self.collection.delete_many({"_id": {"$in": ids_to_delete}})
                logger.info(f"Pruned {delete_result.deleted_count} old entries from the database, and deleted {deleted_files_count} files from GridFS.")
                
                return {"deleted_metadata_count": delete_result.deleted_count, "deleted_files_count": deleted_files_count}
            else:
                logger.info("No entries to prune from MongoDB")
                return {"deleted_metadata_count": 0, "deleted_files_count": 0}
        except Exception as ex:
            logger.error(f"Error pruning old entries: {ex}")
            raise Exception(f"Error pruning old entries: {ex}")

def main():
    # used to test the MongoDB Handler

    # Create a Config object
    config_instance = config.ConfigLoader("config.yaml")
    db_handler = MongoDBHandler(config_instance) # connects to the Mongo Database

    ### need some testing code
  
if __name__ == "__main__":
    main()
