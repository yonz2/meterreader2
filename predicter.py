
import cv2
from ultralytics import YOLO
import torch
import os
from predict_helpers import *


class MeterReader:
    """
    MeterReader is a class that uses pre-trained YOLO models to detect the frame,
    counter, and digits on an electricity meter.
    """

    def __init__(self, weights_path):
        """
        Initializes the MeterReader class, loads YOLO models, and determines the device.
        
        Args:
            project_path (str): The base path for project and model weights.
        """
        # Determine the device: Apple Silicon or CPU
        self.device = 'mps' if torch.backends.mps.is_available() else 'cpu'
        # print(f"Device used for inference: {self.device}")

        # Define model paths
        self.weights_path = weights_path
        self.model_paths = {
            "frame": os.path.join(self.weights_path, "meter-frame.pt"),
            "counter": os.path.join(self.weights_path, "meter-counter.pt"),
            "digits": os.path.join(self.weights_path, "meter-digits.pt"),
        }

        # Load models
        # print(f"Loading models... from:\n{self.model_paths}\n")
        self.model_frame = YOLO(self.model_paths["frame"])
        self.model_counter = YOLO(self.model_paths["counter"])
        self.model_digits = YOLO(self.model_paths["digits"])
        # print("Models loaded successfully!")

    def detect_frame(self, image_path):
        """
        Detects the frame in the meter image.
        
        Args:
            image_path (str): Path to the input image.
        
        Returns:
            tuple: Annotated image with bounding boxes, cropped frame image.
        """
        image = load_image(image_path)
        # print(f"Processing image: {image_path}, Shape: {image.shape}")

        results = self.model_frame(
            image, device=self.device, imgsz=[640, 704], conf=0.4, iou=0.5, verbose=False
        )
        plot_image(results[0].plot(), f"Detected Frame on {os.path.basename(image_path)}", bgr=True)
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
        plot_image(results[0].plot(), "Detected Counter", bgr=True)
        if results[0].boxes.xyxy .nelement() !=0:
            box = results[0].boxes.xyxy[0]
            x1, y1, x2, y2 = map(int, box.tolist())
            counter_image = frame_image[y1:y2, x1:x2].copy()

            rotation_angle = determine_rotation_angle(counter_image, horizontal_threshold=0.1)
            rotated_image = rotate_image(counter_image, rotation_angle)
            binary_image = convert_to_binary(rotated_image, invert=True, bgr=True)
            # plot_image(binary_image, "Binary Image will be passed to Dgits Detection")
            detected_thumbnail = generate_thumbnail(counter_image)
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
            plot_image(results[0].plot(), title="Detected Digits", bgr=True)
            boxes = results[0].boxes.xyxy.tolist()  # Convert to list for easier iteration
            class_ids = results[0].boxes.cls.tolist()
            names = results[0].names

            valid_boxes = []

            for i, box in enumerate(boxes):
                x1, y1, x2, y2 = map(int, box)
                w = x2 - x1
                h = y2 - y1
                area = w * h

                if h > w and area >= 200:
                    valid_boxes.append((i,x1, y1, x2, y2))
                    # print(f"Valid Box found: Class {names[int(class_ids[i])]}, x1={x1}, y1={y1}, x2={x2}, y2={y2}, w={w}, h={h}, area={area}")
            
            if valid_boxes:
                # Sort valid boxes by x1 (reading order)
                valid_boxes.sort(key=lambda box: box[1])  # Sort by the second element (x1)

                num_digits_to_read = min(6, len(valid_boxes))
                for digitNo in range(num_digits_to_read):
                    i, x1, y1, x2, y2 = valid_boxes[digitNo]
                    digit_name = names[int(class_ids[i])]
                    digit_value = digit_name_map.get(digit_name) # Get the digit value from the map
                    if digit_value is not None:
                        meter_value_str += digit_value
                        # print(f"Valid box label: #{digitNo+1} (x1={x1}): {digit_name} -> {digit_value}")
                    else:
                        # print(f"Warning: Digit name '{digit_name}' not found in lookup table.")
                        meter_value_str = None # Reset meter value since a digit could not be identified.
                        break # Stop processing since the meter value is now invalid

                if meter_value_str is not None: # Only convert to int if all digits could be identified.
                    # print(f"Meter Value (str): {meter_value_str}")
                    try:
                        meter_value_int = int(meter_value_str)
                        # print(f"Meter Value (int): {meter_value_int}")
                    except ValueError:
                        print(f"Could not convert Meter Value ({meter_value_str}) to int")


            else:
                print("No valid boxes found matching the criteria.")
        else:
            print("No digits detected.")

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
            print("No frame detected.")
            return None
        
        # Call the detect_counter method
        counter_plot, counter_image = self.detect_counter(frame_image)
        
        if counter_image is None:
            print("No counter detected.")
            return None
        
        # Call the detect_digits method
        digits_plot, digits_str, digits_int = self.detect_digits(counter_image)
        
        if digits_int is not None:
            # print(f"Detected Meter Value: {digits_int}")
            return digits_int
        else:
            print("No digits detected.")
            return None


if __name__ == "__main__":
    # Example usage of the class
    weights_path = "/Users/yonz/Workspace/meterreader2/weights"
    meter_reader = MeterReader(weights_path)

    image_path = "/Users/yonz/Workspace/images/meter-frame-1/IMG_6981.jpg"

    meter_value = meter_reader.predict_image(image_path)

    print(f"Image: {image_path}\nFinal Meter Value: {meter_value}")