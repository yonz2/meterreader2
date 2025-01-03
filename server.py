import asyncio
import io
import json
import logging
import os
import sys

from dotenv import load_dotenv
from datetime import datetime, timezone

# Import the Quart modules, used to provide the HTTP Server and rendering of the HTML templates
from quart import Quart, request, Response, jsonify, abort, render_template, websocket, send_file
from werkzeug.utils import secure_filename

# Import the logging models. Incl. the custom_logger module
from helpers import custom_logger

# Import the ConfigLoader class from the helpers module. This class is used to load the 
# configuration settings and make them available to the application.
from helpers import config

# Import the MeterReader class from the predictions module. 
# The MeterReader class is used to process images and extract meter readings.
from predicter.predictions import MeterReader

# Import the MongoDBHandler class from the helpers module. 
# This class is used to interact with the MongoDB database.
from helpers.monogodb_handler import MongoDBHandler

# Import the HomeAssistant_MQTT_Client class from the helpers module. 
# This class is used to send data to Home Assistant.
from helpers.mqtt_client import HomeAssistant_MQTT_Client

# Import Image manipulation functions and other helpers used by the prediction functions
from predicter import predict_helpers


# Initialize the helper Classes and functions:

# Load environment variables if running locally
load_dotenv()

# 1) Create a CustomLogger object
logger = custom_logger.setup_logging(logger_name="MeterReader")

# 2) Create a Config object
config_instance = config.ConfigLoader("config.yaml")


# 3) Initialize Mongo db handler a
db_handler = MongoDBHandler(config_instance) # connects to the Mongo Database

# 4) Initialize the MeterReader object
meter_reader = MeterReader(config_instance) # Loads the model used for predictions

# 5) Create an instance of the HomeAssistant_MQTT class
ha_mqtt = HomeAssistant_MQTT_Client(config_instance) 

# 6) Store connected WebSocket clients
clients = set()

# 7) Initialize the Quart application object
app = Quart(__name__, 
            static_url_path = '',
            static_folder   = 'static', 
            template_folder = 'templates'
            )
app.config['MAX_CONTENT_LENGTH'] = 10*1024*1024 # 10MB
app.logger=logger


# Set static folder path
static_folder_path = f"{app.static_folder}/"
logger.info(f"Root Path: {app.root_path} - Static Folder: {app.static_folder} - Template Folder: {app.template_folder}")

async def process_image(image_path):
    """
    Wrapper function to call all three detections in one go.
    Returns the detected value (integer) or None if nothing is detected.
    
    Args:
        image_path (str): Path to the input image.
    
    Returns:
        int or None: The detected meter value.
    """

    logger.debug("Inside process_Image %s", image_path)
    detected_thumbnail = None
    # Call the detect_frame method
    frame_plot, frame_image = meter_reader.detect_frame(image_path)
    
    if frame_image is None:
        logger.debug("No frame detected on image %s", image_path)
        counter_image = None
        counter_plot = None
    else:
        logger.debug("Frame Shape returned from 'detect_frame': %s", frame_image.shape)
        # Call the detect_counter method
        counter_plot, counter_image, detected_thumbnail = meter_reader.detect_counter(frame_image)
    
    if counter_image is None:
        logger.debug("No counter detected on image %s", image_path)
        digits_plot = None
        digits_int = 0
        digits_str = ""
    else:
        logger.debug("Counter Shape returned from 'detect_counter': %s", counter_image.shape)
        # Call the detect_digits method
        digits_plot, digits_str, digits_int = meter_reader.detect_digits(counter_image)
    
    if digits_int != 0:
        logger.debug("Detected Meter Value: %i", digits_int)
        #
        # This is the key statement in the whole application...
        # Send a value to Home Assistant
        device_id = config_instance.get("HomeAssistant", "device_id")
        ha_mqtt.send_value(device_id, float(digits_int))
        #
        #
    else:
        digits_int = 0
        digits_str = ""
        logger.warning("No Digits Value found on image %s", image_path)


    # Store image metadata and intermediate files in MongoDB
    file_name_image = os.path.basename(image_path)
    
    if frame_plot is not None:
        db_handler.insert_image(file_name_image, frame_plot)
         
    if counter_plot is not None:
        file_name_counter = f"{file_name_image[:-4]}_counter.jpg"
        db_handler.insert_image(file_name_counter, counter_plot)
        
    else:
        file_name_counter = f"No Counter found on {file_name_image[:-4]}"

    if digits_plot  is not None:
        file_name_digits = f"{file_name_image[:-4]}_digits.jpg"
        db_handler.insert_image(file_name_digits, digits_plot)
    else:
        file_name_digits = f"No Digits found on {file_name_image[:-4]}"
        detected_thumbnail = None

    image_metadata = {
        "file_name_image": file_name_image,
        "file_name_counter": file_name_counter,
        "file_name_digits": file_name_digits,
        "image_path": image_path,
        "value_str": digits_str,
        "value_int": digits_int,  
        "detected_thumbnail": detected_thumbnail,
        "processed_at": datetime.now(tz=timezone.utc).isoformat()  # Add UTC timestamp  
            }
    logger.debug("Image Data Stored in MongoDB %s: Value: %i", file_name_image, digits_int)
    db_handler.update_image_metadata(file_name_image, image_metadata)

    return file_name_image, digits_int
# end def    

@app.route("/file", methods=["POST"])
async def handle_file_upload():
    """
    Handle file upload requests.

    This route processes uploaded files and performs any necessary actions.
    Expected Input: A file to be uploaded via a POST request.
    Response: JSON response indicating success or failure.
    """
    try:
        logger.debug("Inside Handle file Upload")
        uploaded_file = await request.files
        logger.info("Request files: %s", uploaded_file)

        img_list = list(uploaded_file.keys())
        if not img_list:
            logger.error("No files found in the request")
            return Response(status=400, json={"error": "No file uploaded"})

        file = uploaded_file[img_list[0]]
        logger.info("Processing file: %s, MIME type: %s", file.filename, file.content_type)

        if not file:
            logger.error("No file uploaded")
            return Response(status=400, json={"error": "No file uploaded"})

        # Verify file content
        file_content = file.read()
        if not file_content:
            logger.error("File content is empty")
            return Response(status=400, json={"error": "File content is empty"})

        try:
            filename = secure_filename(file.filename)
            filepath = os.path.join(static_folder_path, filename)  # Ensure proper path handling
            file.seek(0)  # Reset file pointer before saving
            await file.save(filepath)
            logger.info("File %s uploaded to %s", filename, static_folder_path)
        except Exception as ex:
            logger.error("Error saving file: %s", ex)
            return jsonify({"error:":  "Failed to save file"}), 500

        # Process the image (this now handles MongoDB interaction)
        file_name_image, detected_number = await process_image(filepath)

        return jsonify({"message" : f"File received {file_name_image} - Value {detected_number}"}), 200
    except Exception as ex:
        logger.error("Error uploading file: %s", ex)
        return jsonify({"error": str(ex)}), 400
    

@app.route("/download/<filename>")
def download_file(filename):  # Removed async
    """
    Download a specific file from the MONOGDB server.

    Args:
        filename (str): Name of the file to download.

    Returns:
        File as an attachment or an error response if the file is not found.
    """
    allowed_extensions = {'pdf', 'txt', 'png', 'jpg', 'jpeg', 'gif'}
    if '.' not in filename or filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
        abort(404)
    try:
        image_document = db_handler.get_image_data(filename)
        if image_document:
            return send_file(  
                io.BytesIO(image_document['data']),
                mimetype='image/jpeg',  # Adjust mimetype if necessary
                as_attachment=True,
                attachment_filename=filename
            )
        else:
            abort(404)  # Image not found
    except Exception as ex:
        logger.error("Error downloading file: %s", ex)
        abort(500)
       

@app.route('/image/<filename>')
async def get_image(filename):
    """
    Retrieves an image from MongoDB (GridFS) and sends it to the client.

    Returns:
        JSON metadata details.
    """
    try:
        # Retrieve image binary data and content type
        image_data, content_type = db_handler.get_image_data(filename)
        
        # Return the binary data as an image response
        return await send_file(
            io.BytesIO(image_data),  # Convert binary data to file-like object
            mimetype=content_type,   # Use dynamic content type
            as_attachment=False,     # Ensures it displays in browser
            attachment_filename=filename
        )
    except FileNotFoundError:
        return abort(404)  # Image not found
    except Exception as ex:
        logger.error("Error retrieving image: %s", ex)
        return abort(500)

@app.route("/metadata", methods=["GET"])
async def get_metadata():
    """
    Fetch metadata grouped by filename.

    Returns:
        JSON metadata details.
    """
    try:
        grouped_metadata = db_handler.get_grouped_metadata(limit=16)
        logger.debug("/metadata: Number of items returned from get_grouped_metadata: %i" ,len(grouped_metadata))
        return jsonify(grouped_metadata)
    except Exception as ex:
        logger.error("Error in /metadata route: %s", ex)
        return jsonify({"error": str(ex)}), 500

@app.route("/prune_db", methods=["POST"])
async def prune_db():
    """
    Handle database pruning requests.

    This route is used for clearing unnecessary data from the database.
    """
    try:
        result = db_handler.prune_old_entries(retain_count=16)
        return jsonify({
            "message": "Database pruned successfully",
            "deleted_metadata_count": result["deleted_metadata_count"],
            "deleted_files_count": result["deleted_files_count"]
        })
    except Exception as ex:
        logger.error("Error in /prune_db route: %s", ex)
        return jsonify({"error": str(ex)}), 500

@app.route("/")
async def info():
    """
    Render the home page.

    Returns:
        HTML content for the home page.
    """
    base_url = request.url_root
    ws_url = f"{base_url.replace('http', 'ws')}ws"

    # Fetch the latest 16 image metadata entries from MongoDB
    grouped_metadata = db_handler.get_grouped_metadata(limit=16)
    logger.debug("Before rendering: Number of items found in MongoDB: %i", len(grouped_metadata))

    return await render_template("index.html", item_list=grouped_metadata, ws_url=ws_url)


@app.route('/shutdown', methods=['POST'])
async def shutdown():
    """
    First part of the Server Shutdown process.

    Send a shutdown response to the client.
    """
    logger.info("Shutdown request received. Not exiting yet.")
    response = jsonify({"message": "Server is ready to shut down."})
    response.status_code = 200
    return response  # Ensure the response is fully sent

@app.route('/force_exit', methods=['POST'])
async def force_exit():
    """
    Immediately terminate the server.

    This route is used to force the server to exit without waiting for active connections.
    
    """
    logger.info("Force exit request received. Terminating server.")
    os._exit(0)  # Hard exit




@app.websocket('/ws')
async def ws():
    """
    Handle WebSocket connections.

    This route establishes WebSocket communication for real-time updates.
    """
    logger.debug("Adding a WebSocket client...")
    clients.add(websocket)  # Add the current WebSocket connection
    try:
        while True:
            await websocket.receive()  # Keep the connection alive
    except Exception as ex:
        logger.warning("WebSocket error: %s", ex)
    finally:
        # Remove the WebSocket connection from the set when it disconnects
        clients.discard(websocket)
        logger.debug("WebSocket client removed.")


# Error handling
@app.errorhandler(404)
def handle_not_found(error):
    """
    Error handler for 404 Not Found.

    This function returns a JSON response with an error message.
    """
    return jsonify({"error": f"Not Found - {error}"}), 404


if __name__ == "__main__":
    logger.info("Starting Application: Current working directory is: %s", os.getcwd())
    logger.info("Static files are located in: %s", static_folder_path)

    # Run the Quart app with the shutdown trigger
    app.run(port=8098, host='0.0.0.0')
