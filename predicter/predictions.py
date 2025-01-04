#
"""
Predictions module contains the MeterReader class that uses pre-trained YOLO models to detect the frame,
counter, and digits on an electricity meter.

The MeterReader class is used to predict the meter value from an input image.
It uses the YOLO models to detect the frame, counter, and digits on the meter image.
The class is initialized with the configuration parameters and the project path.
The predict_image method is used to call all three detections in one go and returns the detected value (integer) or None if nothing is detected.

"""
import os
import logging
from dotenv import load_dotenv

from ultralytics import YOLO

# Import Image manipulation functions and other helpers used by the prediction functions
from predicter import predict_helpers

# In your main application file or any other file where you need these modules
from helpers import config as config


# Make sure to use the same logger as the rest of the application
logger_name = os.environ.get("LOGGER_NAME") or os.path.splitext(os.path.basename(__file__))[0]
logger = logging.getLogger(logger_name)

class MeterReader:
    """
    MeterReader is a class that uses pre-trained YOLO models to detect the frame,
    counter, and digits on an electricity meter.
    """

    def __init__(self, config, project_path=""):
        """
        Initializes the MeterReader class, loads YOLO models, and determines the device.
        
        Args:
            project_path (str): The base path for project and model weights.
        """

        self.config = config

        # Determine the device: Apple Silicon or default defined in config.yaml
        self.device = config.get('YOLO', 'device')
        logger.debug("Device used for inference: %s", self.device)

        # Define model paths
        if project_path:
            self.weights_path = project_path
        else:
            self.weights_path = config.get('YOLO', 'weights_path')
        self.weights = config.get('YOLO', 'weights')
        self.model_paths = {
            "frame": os.path.join(self.weights_path, self.weights['frame']),
            "counter": os.path.join(self.weights_path, self.weights['counter']),
            "digits": os.path.join(self.weights_path, self.weights['digits']),
        }

        # Load models
        logger.debug("Loading models... from:\n%s\n", self.weights_path)
        self.model_frame = YOLO(self.model_paths["frame"])
        self.model_counter = YOLO(self.model_paths["counter"])
        self.model_digits = YOLO(self.model_paths["digits"])
        logger.info("Models loaded successfully! - %s", self.weights)

    def detect_frame(self, image_path):
        """
        Detects the frame in the meter image.
        
        Args:
            image_path (str): Path to the input image.
        
        Returns:
            tuple: Annotated image with bounding boxes, cropped frame image.
        """
        image = predict_helpers.load_image(image_path)
        logger.debug("Processing image: %s, Shape: %s", image_path, image.shape)

        results = self.model_frame(
            image, device=self.device, imgsz=[640, 704], conf=0.4, iou=0.5, verbose=False
        )
        predict_helpers.plot_image(results[0].plot(), "Detected Frame on %s" % os.path.basename(image_path), bgr=True)
        frame_image = None
        if results[0].boxes.xyxy is not None:
            box = results[0].boxes.xyxy[0]
            x1, y1, x2, y2 = map(int, box.tolist())
            frame_image = image[y1:y2, x1:x2].copy()

        return results[0].plot(), frame_image

    def detect_counter(self, frame_image):
        """
        Detects the counter region from the frame image.
        
        Args:
            frame_image (ndarray): Cropped frame image.
        
        Returns:
            tuple: Annotated image, binary processed counter image, A thumbnail of the counter image (256 pixels wide)
        """
        results = self.model_counter(
            frame_image, device=self.device, imgsz=[640, 704], conf=0.4, iou=0.5, verbose=False
        )

        counter_image = None
        predict_helpers.plot_image(results[0].plot(), "Detected Counter", bgr=True)
        if results[0].boxes.xyxy.nelement() != 0:
            box = results[0].boxes.xyxy[0]
            x1, y1, x2, y2 = map(int, box.tolist())
            counter_image = frame_image[y1:y2, x1:x2].copy()

            rotation_angle = predict_helpers.determine_rotation_angle(counter_image, horizontal_threshold=0.1)
            rotated_image = predict_helpers.rotate_image(counter_image, rotation_angle)
            binary_image = predict_helpers.convert_to_binary(rotated_image, invert=True, bgr=True)
            # plot_image(binary_image, "Binary Image will be passed to Dgits Detection")
            detected_thumbnail = predict_helpers.generate_thumbnail(counter_image)
            return results[0].plot(), binary_image, detected_thumbnail
        else:
            return None, None, None

    def detect_digits(self, digits_image):
        """
        Detects digits from the binary processed counter image.
        
        Args:
            digits_image (ndarray): Processed binary image of the counter.
        
        Returns:
            tuple: Annotated image, string value, integer value.
        """
        digit_name_map = {
            "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
            "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9"
        }

        meter_value_str = ""
        meter_value_int = None
        results = self.model_digits(
            digits_image, device=self.device, imgsz=[192, 768], conf=0.6, iou=0.5, verbose=False
        )

        if results[0].boxes is not None and len(results[0].boxes.xyxy) > 0:
            predict_helpers.plot_image(results[0].plot(), "Detected Digits", bgr=True)
            boxes = results[0].boxes.xyxy.tolist()  # Convert to list for easier iteration
            class_ids = results[0].boxes.cls.tolist()
            names = results[0].names

            valid_boxes = []
            # Iterate through the detected boxes and filter out the valid ones based on simple criteria:
            # 1. Height > Width
            # 2. Area > 200 square pixels
            for i, box in enumerate(boxes):
                x1, y1, x2, y2 = map(int, box)
                w = x2 - x1
                h = y2 - y1
                area = w * h

                if h > w and area >= 200:
                    valid_boxes.append((i, x1, y1, x2, y2))
                    # logger.debug("Valid Box found: Class %s, x1=%d, y1=%d, x2=%d, y2=%d, w=%d, h=%d, area=%d", names[int(class_ids[i])], x1, y1, x2, y2, w, h, area)
            
            if valid_boxes:
                # Sort valid boxes by x1 (reading order) to assemble the value string
                valid_boxes.sort(key=lambda box: box[1])  # Sort by the second element (x1)

                num_digits_to_read = min(6, len(valid_boxes))  # Read up to 6 digits, the last digit (after the comma is not relevant)
                for digit_no in range(num_digits_to_read):
                    i, x1, y1, x2, y2 = valid_boxes[digit_no]
                    digit_name = names[int(class_ids[i])]
                    digit_value = digit_name_map.get(digit_name)  # Get the digit value from the map
                    if digit_value is not None:
                        meter_value_str += digit_value
                        # logger.debug("Valid box label: #%d (x1=%d): %s -> %s", digit_no + 1, x1, digit_name, digit_value)
                    else:
                        # logger.debug("Warning: Digit name '%s' not found in lookup table.", digit_name)
                        meter_value_str = None  # Reset meter value since a digit could not be identified.
                        break  # Stop processing since the meter value is now invalid

                if meter_value_str is not None:  # Only convert to int if all digits could be identified.
                    logger.debug("Meter Value (str): %s", meter_value_str)
                    try:
                        meter_value_int = int(meter_value_str)
                        # logger.debug("Meter Value (int): %d", meter_value_int)
                    except ValueError:
                        logger.error("Could not convert Meter Value (%s) to int", meter_value_str)

            else:
                logger.warning("No valid boxes found matching the criteria.")
        else:
            logger.warning("No digits detected.")

        return results[0].plot(), meter_value_str, meter_value_int
    
    def predict_image(self, image_path):
        """
        Wrapper function to call all three detections in one go.
        Returns the detected value (integer) or None if nothing is detected.
        
        Args:
            image_path (str): Path to the input image.
        
        Returns:
            int or None: The detected meter value.
        """
        # Call the detect_frame method
        frame_plot, frame_image = self.detect_frame(image_path)
        
        if frame_image is None:
            logger.debug("No frame detected.")
            return None
        
        # Call the detect_counter method
        counter_plot, counter_image, thumbnail_image = self.detect_counter(frame_image)
        
        if counter_image is None:
            logger.debug("No counter detected.")
            return None
        
        # Call the detect_digits method
        digits_plot, digits_str, digits_int = self.detect_digits(counter_image)
        
        if digits_int is not None:
            logger.debug("Detected Meter Value: %d", digits_int)
            return digits_int
        else:
            logger.debug("No digits detected.")
            return None

def main():
    # Example usage of the class
    # Load environment variables if running locally
    load_dotenv()

    # Create a Config object
    config_instance = config.ConfigLoader("config.yaml")

    # Note: All configuration parameters are stored in config.yaml
    meter_reader = MeterReader(config_instance)
    image_test_path = "/home/yonz/workspace/MeterImages/original/IMG_7004.jpg"
    
    meter_value = meter_reader.predict_image(image_test_path)

    print("Image: %s\nFinal Meter Value: %d" % (image_test_path, meter_value))

    return 0

if __name__ == "__main__":
    main()