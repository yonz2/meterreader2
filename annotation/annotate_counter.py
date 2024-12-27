import cv2
import os
import numpy as np
import pytesseract

from predict_helpers import *

def extract_digits_ocr(img):
  """Extracts digits from an image using Tesseract OCR.

  Args:
    img: The image to process as a NumPy array.

  Returns:
    The extracted digits as a string, or None if no text is detected.
  """

  try:
    whitelist = "0123456789"
    ocr_config = "--psm 6 -c tessedit_char_whitelist=" + whitelist
    text = pytesseract.image_to_string(img, config=ocr_config)
    text = text.strip()  # Remove leading/trailing whitespace
    return text
  except Exception as e:
    print(f"Error during OCR: {e}")
    return None


def annotate_meter(image_path, image_path_new,image_path_gray,image_path_thresh):

    image = cv2.imread(image_path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    cv2.imwrite(image_path_gray, gray)   

    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY) 

    # 2. Straighten
    #       Attemt to rotate the image so that the horizontal lines are straight,
    rotation_angle = determine_rotation_angle(thresh, horizontal_threshold=0.1)          
    image_rotated = rotate_image(thresh, rotation_angle)
    cv2.imwrite(image_path_thresh, image_rotated)

    contours, _ = cv2.findContours(image_rotated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    img_size_h, img_size_w = image_rotated.shape[:2]
    annotation = []
    pos = 0
    digit_image_size = 180
    for contour in contours:
        pos += 1
        x, y, w, h = cv2.boundingRect(contour)
        if (h < w) or (h > int(np.ceil(img_size_h * 0.8))) or (w > int(np.ceil(img_size_w * 0.8))):
            # Unrealistic size of box
            print(f"Unrealistic size of box {pos}: {image_path} Contour: x={x}, y={y}, h:{h}, w={w}, Area= {cv2.contourArea(contour)}")
            cv2.imwrite(f"{image_path_thresh[:-4]}_{pos}X.png", thresh[y:y+h, x:x+w])  # Save digit
            continue
        if cv2.contourArea(contour) > 200:
            print(f"Realistic size of box {pos}: {image_path} Contour: x={x}, y={y}, h:{h}, w={w}, Area= {cv2.contourArea(contour)}")
            w_delta = int(np.ceil(w * 1.25 + 1)) - w
            h_delta = int(np.ceil(h * 1.08 + 1)) - h
            h = int(h + h_delta)
            w = int(w + w_delta)
            x = int(np.floor(x - w_delta / 2))
            y = int(np.floor(y - h_delta / 2))
            cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)  # Draw green rectangle
            # Generate annotation in Roboflow format (example: YOLO)

            # Add text with coordinates and size
           
            digit_image = thresh[y:y+h, x:x+w]  # Extract digit region
                        # Invert the digit image
            digit_image_inverse = cv2.bitwise_not(digit_image)

            # Create a white background image
            background = np.ones((digit_image_size, digit_image_size), dtype=np.uint8) * 255 

            # Calculate scaling factor
            max_dimension = max(w, h)
            if max_dimension > digit_image_size: # Scale to fit within 180x180
                print(f"\tScaling a digit while processing {image_path} Contour: x={x}, y={y}, h:{h}, w={w}")
                scale_factor = digit_image_size / max_dimension  
                # Resize the digit image
                digit_image_inverse = cv2.resize(digit_image_inverse, (0, 0), fx=scale_factor, fy=scale_factor)
                # Get new dimensions after resizing
                h, w = digit_image_inverse.shape
            # Calculate the position to center the digit
            x_offset = int((digit_image_size - w) / 2)
            y_offset = int((digit_image_size - h) / 2)

            # Calculate the bounding box values, used for the Annotatoin txt file.
            # Assumption: The image is a digit_image_size x digit_image_size pixels
            x_anno = round(float( (x_offset +  w / 2) / digit_image_size), 3)
            y_anno = round(float((y_offset + h / 2) / digit_image_size), 3)
            h_anno = round(float ( h / digit_image_size), 3)
            w_anno = round(float ( w / digit_image_size), 3)
                


            # Place the digit on the background
            try:
                background[y_offset:y_offset+h, x_offset:x_offset+w] = digit_image_inverse
            except cv2.error as e:
                print(f"CV2 Error processing {image_path} Contour: x={x}, y={y}, h:{h}, w={w}\n{e}")
                continue
            except ValueError as e:
                print(f"Value Error processing {image_path} Contour: x={x}, y={y}, h:{h}, w={w}\n{e}")
                continue
            except:
                print(f"Error processing {image_path} Contour: x={x}, y={y}, h:{h}, w={w}")
                continue

            cv2.imwrite(f"{image_path_thresh[:-4]}_{pos}.png", background)  # Save digit

            img_text = extract_digits_ocr(background)

            annotation_line = f"{pos} {x_anno} {y_anno} {w_anno} {h_anno}" 
            cv2.putText(image, annotation_line, (x, max(y - 10,1)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2) 
 
            # Calculate text position
            text_x = x + int(w + 10)  # Right of center, with a small offset
            text_y = y + int(h / 2)      # Vertically centered        
            cv2.putText(image, img_text, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2) 

            # '0' represents the class ID for the digit (you might need to adjust this)
            # Write annotation to a file
            annotation.append(annotation_line)

    cv2.imwrite(image_path_new, image)
    # Write annotation to a file
    with open(f"{image_path_new[:-4]}.txt", "a") as f: 
        f.write("\n".join(annotation))



# Example usage
image_path = "/Users/yonz/Workspace/meterreader2/meterreader_YOLO/counter-1/crops/counter/IMG_6900.jpg"
# image_path = "/home/yonz/workspace/MeterImages/original-3/IMG_6997.jpg"
image_filename = os.path.basename(image_path)
image_dir = os.path.dirname(image_path)
image_path_new = os.path.join(image_dir, f"{image_filename[:-4]}_ann.jpg")
image_path_thresh = os.path.join(image_dir, f"{image_filename[:-4]}_thresh.jpg")
image_path_gray = os.path.join(image_dir, f"{image_filename[:-4]}_gray.jpg")
annotate_meter(image_path, image_path_new,image_path_gray,image_path_thresh)

