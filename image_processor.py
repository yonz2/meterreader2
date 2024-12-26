import os
import json
from dotenv import load_dotenv
from pymongo import MongoClient
from roboflow import Roboflow
import cv2
import base64
# import io
# from PIL import Image


import pytesseract
import logging
from datetime import datetime, timezone
from custom_logger import setup_custom_logger, log_message
from monogodb_handler import MongoDBHandler
from monogodb_handler import get_database_and_collection, convert_to_serializable


class ImageProcessor:
    def __init__(self, db_handler=None):
        load_dotenv()
        self._rf_api_key = os.getenv("ROBOFLOW_API_KEY", "")
        self._rf_serverURL = os.getenv("ROBOFLOW_SERVER_URL", "http://localhost:9001/")
        self._rf_workspace = os.getenv("ROBOFOLOW_WORKSPACE", "meterreader")
        self._rf_project = os.getenv("ROBOFOLOW_PROJECT", "metervalues")
        self._rf_version = os.getenv("ROBOFOLOW_PROJECT_VERSION", "3")
        self._rf_confidence = 50
        self._rf_overlap = 50
        self.rf = Roboflow(api_key=self._rf_api_key)
        self.rf_project = self.rf.workspace(self._rf_workspace).project(self._rf_project)
        self.rf_model = self.rf_project.version(self._rf_version, self._rf_serverURL).model

        self.image_processor_standalone = False
        self.db_handler = db_handler


    def scale_image_to_max_height(self, image_path, max_height=640):
        log_message(f"Scaling Image: {image_path}")
        image = cv2.imread(image_path)
        height, width, channels = image.shape
        scale_factor = min(max_height / height, 1.0)
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)
        resized_image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
        file_path, file_extension = os.path.splitext(image_path)
        new_file_path = f"{file_path}_{max_height}{file_extension}"
        cv2.imwrite(new_file_path, resized_image)
        log_message(f"Scaled image saved to : {new_file_path}")
        return new_file_path, scale_factor

    def detect_reading(self, source_image_path):
        log_message(f"Calling Roboflow Inference with: {source_image_path}")
        predictions = self.rf_model.predict(source_image_path, confidence=self._rf_confidence, overlap=self._rf_overlap)
        log_message(f" - Roboflow Inference returned ... predictions")
        results = predictions.json()
        output_filepath = os.path.splitext(source_image_path)[0] + "_with_boxes.jpg"
        predictions.save(output_filepath)
        log_message(f" - Annotated Image saved to: {output_filepath}")
        return results, output_filepath

    def perform_ocr(self, detection_results, image_path, scaling_factor):
        log_message(f"Running OCR on {image_path}")


        # Find the prediction with the highest confidence detection_results.predictions
        max_confidence_prediction = max(detection_results['predictions'], key=lambda x: x['confidence'])

                # Extract bounding box coordinates (adjust as needed)
        x = max_confidence_prediction['x']
        y = max_confidence_prediction['y']
        width = max_confidence_prediction['width']
        height = max_confidence_prediction['height']

        # Calculate the top left / bottom right coordinaes and scle them to the original image ....
        x1 = max(int(x - width / 2), 0)  # Ensure integer coordinates for OpenCV
        y1 = max(int(y - height / 2), 0)
        x2 = int(x + width / 2)
        y2 = int(y + height / 2)

        # Calculate actual dimensions
        width_original = int(width / scaling_factor)
        height_original = int(height / scaling_factor)

        # Calculate cropping coordinates
        x1_original = int(x1 / scaling_factor)
        y1_original = int(y1 / scaling_factor)

        # Ensure coordinates stay within image bounds
        x2_original = int(x2 / scaling_factor)
        y2_original = int(y2 / scaling_factor) 

        # Dirty patch .... Make sure the bounding box is long enough to cover the whole number
        # Make the rectangle a bit bigger
        aspect_ration = width_original / height_original
        if aspect_ration < 2.5:
            # if the reading width is not ca. 3 times the height, expand the bounding box
            x2_original = int( int(x1_original + height_original * 3.3) )
        x1_original = int(x1_original - 10)
        y1_original = int(y1_original - 10)
        x2_original = int(x2_original + 10)
        y2_original = int(y2_original + 10)
    
        # Load image with OpenCV
        opencv_image = cv2.imread(image_path)

        # Extract the ROI (Region of Interest)
        log_message(f" - Cropping {os.path.basename(image_path)} : y1={y1_original}, y2={y2_original}, x1={x1_original}, x2={x2_original}, aspect ration: {aspect_ration}, width={width_original}, height={height_original}")
        detected_object_rgb = opencv_image[y1_original:y2_original, x1_original:x2_original]

        log_message(f" - Converting cropped image to Graysacle")
        detected_object = cv2.cvtColor(detected_object_rgb, cv2.COLOR_BGR2GRAY)
        detected_object_rgb = None
        detected_object_file = os.path.splitext(image_path)[0] + "_detected.jpg"

        log_message(f" - Save the detected bounding box image to {detected_object_file}")
        cv2.imwrite(detected_object_file, detected_object)

        # Use Tesseract directly on OpenCV image (assuming compatible format)
        log_message(f" - Calling OCR Function with Binary image")
        # Include only digits in the whitelist
        # The config string combines two options:
        # --psm 6: Sets the page segmentation mode to "Single Block" (useful for meter readings).
        # -c tessedit_char_whitelist= followed by the whitelist string.
        whitelist = "0123456789"

        text_grayscale = pytesseract.image_to_string(detected_object, config="--psm 6 -c tessedit_char_whitelist=" + whitelist)
        text_grayscale = text_grayscale.strip() # remove trailing and leading whitespace (e.g. newline)
     
        bbox = []
        bbox.append((x1,y1,x2,y2))
        bbox.append((x1_original,y1_original,x2_original,y2_original))
        log_message(f" - OCR Function returned: {text_grayscale}")
        # Return the extracted text
        return f"{text_grayscale}", detected_object_file, bbox, max_confidence_prediction['confidence']   

    def generate_thumbnail(self, image_path, max_height=200):
        """
        Generates a base64-encoded thumbnail of the given image.

        :param image_path: Path to the input image.
        :param max_height: Maximum height for the thumbnail (default: 200 pixels).
        :return: A string in the format '"photo": "data:image/jpeg;base64,/9j/4..."'.
        """
        try:
            # Read the image using OpenCV
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"Image not found or cannot be opened: {image_path}")

            # Get original dimensions
            original_height, original_width = image.shape[:2]

            # Calculate the new dimensions
            if original_height > max_height:
                scale_factor = max_height / original_height
                new_width = int(original_width * scale_factor)
                new_height = int(max_height)
            else:
                new_width = int(original_width)
                new_height = int(original_height)

            # Resize the image while maintaining the aspect ratio
            resized_image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)

            # Convert the resized image to a JPEG format
            _, buffer = cv2.imencode('.jpg', resized_image)

            # Encode the image as a Base64 string
            base64_encoded = base64.b64encode(buffer).decode('utf-8')

            # Return the formatted string
            return f'data:image/jpeg;base64,{base64_encoded}'

        except Exception as ex:
            # Log the error (optional) and return an empty string
            log_message(f"Error generating thumbnail: {ex}", logging.ERROR)
            return ""


    def process_image(self, image_path):

        """
        Processes an image file, ensuring the file exists and is readable before processing.
        :param image_path: Path to the image file to process.
        """
        try:
            # Verify that the file exists and is readable
            if not os.path.isfile(image_path):
                raise FileNotFoundError(f"The file '{image_path}' does not exist.")
            if not os.access(image_path, os.R_OK):
                raise PermissionError(f"The file '{image_path}' is not readable.")

            log_message(f"___________ Starting Image processing ___________ ")

            scaled_imagepath, scale_factor = self.scale_image_to_max_height(image_path, max_height=1280)

            detections, marked_image = self.detect_reading(scaled_imagepath)
            detected_text, detected_object_file, bounding_box, confidence = self.perform_ocr(detections, marked_image, scale_factor)

            # Store images in MongoDB/GRID.FS
            image_filename = os.path.basename(image_path)
            if self.image_processor_standalone: # if debugging or running standalone, do not delete the original image file
                self.db_handler.insert_file_from_path(image_path)
            else:    
                self.db_handler.move_file_from_path(image_path)

            scaled_image_filename = os.path.basename(scaled_imagepath)
            self.db_handler.move_file_from_path(scaled_imagepath)

            marked_thumbnail = self.generate_thumbnail(marked_image, max_height=200)
            marked_filename = os.path.basename(marked_image)        
            self.db_handler.move_file_from_path(marked_image)

            detected_thumbnail = self.generate_thumbnail(detected_object_file, max_height=200)
            detected_object_filename = os.path.basename(detected_object_file)    
            self.db_handler.move_file_from_path(detected_object_file)

            # Store image metadata in MongoDB
            image_metadata = {
                "filename": image_filename,
                "scaled_imagepath": scaled_image_filename,
                "scale_factor": scale_factor,  
                "bounding_box": bounding_box,  
                "marked_image": marked_filename,
                "thumbnail": marked_thumbnail,  
                "detected_text": detected_text,
                "confidence": confidence,    
                "detected_object_file": detected_object_filename,
                "detected_thumbnail": detected_thumbnail,
                "processed_at": datetime.now(tz=timezone.utc).isoformat()  # Add UTC timestamp  
            }
            self.db_handler.update_image_metadata(image_filename, image_metadata)

            log_message(f"___________ Image processing completed ___________ ")

        except FileNotFoundError as fnf_error:
            log_message(str(fnf_error), logging.ERROR)
        except PermissionError as perm_error:
            log_message(str(perm_error), logging.ERROR)
        except Exception as e:
            log_message(f"An error occurred while processing the image: {e}", logging.ERROR)



# ... (main function is removed since it's not needed anymore)
if __name__ == "__main__":
    setup_custom_logger()
    
    file_path = './static/IMG_TEST.jpg'  # Replace with your image file path
    db_handler = get_database_and_collection()
    image_processor = ImageProcessor(db_handler)
    # Flag to make sure the original file is not deleted ... used when debugging, or running stadalone
    image_processor.image_processor_standalone = True

    image_processor.process_image(file_path)

    # Retrieve image metadata
    print("-----------------------------------------------------")
    file_name = os.path.basename(file_path)
    metadata = convert_to_serializable(db_handler.get_metadata_by_filename(file_name))
    if metadata:
        # Pretty print the metadata
        print("Metadata for the image:")
        print(json.dumps(metadata, indent=4, sort_keys=True))
    else:
        print("Metadata not found for the specified filename.")
    print("-----------------------------------------------------")
    print("Done")
