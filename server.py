import os
import io
import logging
import json

from dotenv import load_dotenv

from quart import Quart, current_app, g, request, Response, jsonify, abort
from quart import render_template, url_for, send_from_directory
from quart import send_file
from quart import websocket  # Import the websocket module

from datetime import datetime, timezone

import asyncio
import sys

from werkzeug.utils import secure_filename

from predicter.predicter import MeterReader

from helpers.monogodb_handler import MongoDBHandler

from helpers.mqtt_helper import HomeAssistant_MQTT

# Load environment variables if running locally
load_dotenv()

# In your main application file or any other file where you need these modules
from helpers import custom_logger as custom_logger
import logging
from helpers import config as config

# Import Image manipulation functions and other helpers used by the prediction functions
from predicter import predict_helpers


# Create a Config object
config_instance = config.ConfigLoader("config.yaml")

# Create a CustomLogger object
logger = custom_logger.CustomLogger(logger_name="MeterReader")

# Initialize db handler and ImageProcessor (Load models)
db_handler = MongoDBHandler(config_instance, logger) # connects to the Mongo Database
meter_reader = MeterReader(config_instance, logger) # Loads the model used for predictions

# Create an instance of the HomeAssistant_MQTT class
ha_mqtt = HomeAssistant_MQTT(config_instance, logger) 


# Create the Quart application object
app = Quart(__name__, 
            static_url_path='',
            static_folder='static',
            template_folder='templates')
app.config['MAX_CONTENT_LENGTH'] = 10*1024*1024 # 10MB

# Set static folder path
static_folder_path = f"{app.static_folder}/"
logger.log_message(f"Root Path: {app.root_path} - Static Folder: {app.static_folder} - Template Folder: {app.template_folder}")

async def process_image(image_path):
    """
    Wrapper function to call all three detections in one go.
    Returns the detected value (integer) or None if nothing is detected.
    
    Args:
        image_path (str): Path to the input image.
    
    Returns:
        int or None: The detected meter value.
    """

    logger.log_message(f"Inside process_Image {image_path}", logging.DEBUG)

    # Call the detect_frame method
    frame_plot, frame_image = meter_reader.detect_frame(image_path)
    
    if frame_image is None:
        logger.log_message(f"No frame detected on image {image_path}")
        counter_image = None
        counter_plot = None
    else:
        logger.log_message(f"Frame Shape returned from 'detect_frame': {frame_image.shape}")
        # Call the detect_counter method
        counter_plot, counter_image, detected_thumbnail = meter_reader.detect_counter(frame_image)
    
    if counter_image is None:
        logger.log_message(f"No counter detected on image {image_path}")
        digits_plot = None
        digits_int = 0
        digits_str = ""
    else:
        logger.log_message(f"Counter Shape returned from 'detect_counter': {counter_image.shape}")
        # Call the detect_digits method
        digits_plot, digits_str, digits_int = meter_reader.detect_digits(counter_image)
    
    if digits_int != 0:
        logger.log_message(f"Detected Meter Value: {digits_int}", logging.DEBUG)
    else:
        digits_int = 0
        digits_str = ""
        logger.log_message(f"No Digits Value found")

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
    logger.log_message(f"Image Data Stored in MongoDB {file_name_image}: Value: {digits_int}", logging.DEBUG)
    db_handler.update_image_metadata(file_name_image, image_metadata)

    # Send a value to Home Assistant
    ha_mqtt.send_value("electricity_meter", float(digits_int))

    return file_name_image, digits_int



# end def    


@app.route("/file", methods=["POST"])
async def handle_file_upload():
    """Handles file upload request."""
    try:
        logger.log_message("Inside Handle file Upload")
        uploaded_file = await request.files
        logger.log_message(f"Request files: {uploaded_file}", logging.INFO)

        img_list = list(uploaded_file.keys())
        if not img_list:
            logger.log_message("No files found in the request", logging.ERROR)
            return Response(status=400, json={"error": "No file uploaded"})

        file = uploaded_file[img_list[0]]
        logger.log_message(f"Processing file: {file.filename}, MIME type: {file.content_type}", logging.INFO)

        if not file:
            logger.log_message("No file uploaded", logging.ERROR)
            return Response(status=400, json={"error": "No file uploaded"})

        # Verify file content
        file_content = file.read()
        if not file_content:
            logger.log_message("File content is empty", logging.ERROR)
            return Response(status=400, json={"error": "File content is empty"})

        try:
            filename = secure_filename(file.filename)
            filepath = os.path.join(static_folder_path, filename)  # Ensure proper path handling
            file.seek(0)  # Reset file pointer before saving
            await file.save(filepath)
            logger.log_message(f"File {filename} uploaded to {static_folder_path}", logging.INFO)
        except Exception as ex:
            logger.log_message(f"Error saving file: {ex}", logging.ERROR)
            return jsonify({"error:":  "Failed to save file"}), 500

        # Process the image (this now handles MongoDB interaction)
        file_name_image, detected_number = await process_image(filepath)

        return jsonify({"message": f"File received: {file_name_image} - Value {detected_number}"}), 200
    except Exception as ex:
        logger.log_message(f"Error uploading file: {ex}", logging.ERROR)
        return jsonify({"error": str(ex)}), 400
    

@app.route("/download/<filename>")
def download_file(filename):  # Removed async
    """Downloads a file from MongoDB."""
    allowed_extensions = {'pdf', 'txt', 'png', 'jpg', 'jpeg', 'gif'}
    if '.' not in filename or filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
        abort(404)
    try:
        image_document = db_handler.get_image_data(filename)
        if image_document:
            return send_file(  # Removed await
                io.BytesIO(image_document['data']),
                mimetype='image/jpeg',  # Adjust mimetype if necessary
                as_attachment=True,
                download_name=filename
            )
        else:
            abort(404)  # Image not found
    except Exception as ex:
        logger.log_message(f"Error downloading file: {ex}", logging.ERROR)
        abort(500)
       

@app.route('/image/<filename>')
async def get_image(filename):
    """Retrieves an image from MongoDB (GridFS) and sends it to the client."""
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
        logger.log_message(f"Error retrieving image: {ex}", logging.ERROR)
        return abort(500)

@app.route("/metadata", methods=["GET"])
async def get_metadata():
    """Fetch metadata grouped by filename."""
    try:
        grouped_metadata = db_handler.get_grouped_metadata(limit=16)
        logger.log_message(f"/metadata: Number of items returned from get_grouped_metadata: {len(grouped_metadata)}")
        return jsonify(grouped_metadata)
    except Exception as ex:
        logger.log_message(f"Error in /metadata route: {ex}", logging.ERROR)
        return jsonify({"error": str(ex)}), 500

@app.route("/prune_db", methods=["POST"])
async def prune_db():
    """Prunes the database, keeping only the latest 16 entries."""
    try:
        result = db_handler.prune_old_entries(retain_count=16)
        return jsonify({
            "message": "Database pruned successfully",
            "deleted_metadata_count": result["deleted_metadata_count"],
            "deleted_files_count": result["deleted_files_count"]
        })
    except Exception as ex:
        logger.log_message(f"Error in /prune_db route: {ex}", logging.ERROR)
        return jsonify({"error": str(ex)}), 500

@app.route("/")
async def info():
    """Displays the main file explorer interface."""
    base_url = request.url_root
    ws_url = f"{base_url.replace('http', 'ws')}ws"

    # Fetch the latest 16 image metadata entries from MongoDB
    grouped_metadata = db_handler.get_grouped_metadata(limit=16)
    logger.log_message(f"Before rendering: Number of items found in MongoDB: {len(grouped_metadata)}", logging.DEBUG)
    # print(json.dumps(item_list, indent=4, sort_keys=True))

    return await render_template("index.html", item_list=grouped_metadata, ws_url=ws_url)


@app.route('/shutdown', methods=['POST'])
async def shutdown():
    """Send a shutdown response to the client."""
    logger.log_message("Shutdown request received. Not exiting yet.")
    response = jsonify({"message": "Server is ready to shut down."})
    response.status_code = 200
    return response  # Ensure the response is fully sent

@app.route('/force_exit', methods=['POST'])
async def force_exit():
    """Immediately terminate the server."""
    logger.log_message("Force exit request received. Terminating server.")
    os._exit(0)  # Hard exit


# Store connected WebSocket clients
clients = set()

@app.websocket('/ws')
async def ws():
    """WebSocket handler to manage client connections."""
    logger.log_message("Adding a WebSocket client...")
    clients.add(websocket)  # Add the current WebSocket connection
    try:
        while True:
            await websocket.receive()  # Keep the connection alive
    except Exception as ex:
        logger.log_message(f"WebSocket error: {ex}", logging.WARNING)
    finally:
        # Remove the WebSocket connection from the set when it disconnects
        clients.discard(websocket)
        logger.log_message("WebSocket client removed.")


# Error handling
@app.errorhandler(404)
def handle_not_found(error):
    return jsonify({"error": "Not Found"}), 404


if __name__ == "__main__":
    logger.log_message(f"Starting Application: Current working directory is: {os.getcwd()}", logging.INFO)
    logger.log_message(f"Static files are located in: {static_folder_path}", logging.INFO)

    # Run the Quart app with the shutdown trigger
    app.run(port=8098, host='0.0.0.0')
