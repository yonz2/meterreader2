# (c) 2024 Yonz
"""
Script Name: predict_image
Description: For example, this script processes images using 
             machine learning predictions, drawing bounding boxes, and extracting ROI from images.
Author: Yonz
Created Date: 2024-04-05
Last Modified Date: 2024-04-06
Version: 0.8

This script uses ROBOFLOW Models to run the predistions. The Roboflow parameters are read from env. Variables (see .env)
"""
#
import cv2
import os
import json
import math
import argparse
import logging
from dotenv import load_dotenv

import numpy as np
from matplotlib import pyplot as plt

import yaml


def load_image(filepath):
    """Loads an image from a given file path, with error handling.

    Args:
        filepath (str): Path to the image file.

    Returns:
        image: Loaded image object or None if loading fails.
    """
    if not os.path.exists(filepath):
        print(f"Error: File {filepath} does not exist.")
        return None
    elif not os.path.isfile(filepath):
        print(f"Error: {filepath} is not a file.")
        return None
    elif not os.access(filepath, os.R_OK):
        print(f"Error: File {filepath} is not readable.")
        return None

    try:
        img = cv2.imread(filepath)
        return img
    except Exception as e:
        print(f"Error: An exception occurred while loading the image. {e}")
        return None


def save_image(image, path):
    """Saves an image to a specified file path, with checks for writeability.

    Args:
        image: An image object.
        path (str): File path where the image will be saved.

    Returns:
        bool: True if the image is saved successfully, False otherwise.
    """
    # Check if the directory exists and is writable
    directory = os.path.dirname(path)
    if not os.path.exists(directory):
        try:
            os.makedirs(directory)
        except OSError:
            print(f"Error: Unable to create directory {directory}.")
            return False
    elif not os.access(directory, os.W_OK):
        print(f"Error: The directory {directory} is not writable.")
        return False

    # Attempt to save the image
    try:
        cv2.imwrite(path, image)
    except Exception as e:
        print(f"Error: Unable to save the image to {path}. {e}")
        return False

    return True


def scale_image(image, new_size=[640,640], orientation='portrait', pad_color = []):
    """Scales an image to a specified maximum height, ensuring the output dimensions 
    are multiples of 32 by cropping if necessary.

    Args:
        image: An image object to be scaled.
        new_size([int,int]): A tuple defining th enew size of the image (must be a multiple of 32).
        orientation (str):  portrait: width is fixed, excess height will be cropped eq. from top and bottom
                            landscape: height is fixed, excess width will be cut from left and right hand side
        pad_color ([0,0,0,0]):    undefined: calculate average color value of the nearest pixels
                            [x,y,z] : Color value to use


    Returns:
        tuple: A tuple containing the scaled and cropped image, and the scale factor.
    """

    new_height, new_width = new_size

    if new_height % 32 != 0:
        raise ValueError("New height must be a multiple of 32")
    if new_width % 32 != 0:
        raise ValueError("New width must be a multiple of 32")

    height, width = image.shape[:2]
    if orientation == 'portrait':
        scale_factor = new_width / width
        scaled_width = new_width
        scaled_height = int(height * scale_factor)
    elif orientation == 'landscape':
        scale_factor = new_height / height
        scaled_width = int (width * scale_factor)
        scaled_height = new_height
    else:
        raise ValueError(f"Orientation: {orientation} is undefined")

 
    resized_image = cv2.resize(image, (scaled_width, scaled_height), interpolation=cv2.INTER_AREA)

    resized_height, resized_width = resized_image.shape[:2] 

    # Calculate cropping amounts

    if orientation == 'portrait':
        crop_top = 0
        crop_bottom = max(resized_height - new_height,0)
        crop_left = 0
        crop_right = 0
    elif orientation == 'landscape':
        crop_top = 0
        crop_bottom = 0
        crop_left =  max(int((resized_width - new_width) // 2),0)
        crop_right = max((resized_width - new_width - crop_left),0)


    # Crop the image
    return_image = resized_image[ crop_top : resized_height - crop_bottom, crop_left : resized_width - crop_right ]

    # Make sure the image is of correct size, i.e. if it is to small. If so, pad it with a black border

    cropped_height, cropped_width = return_image.shape[:2]
 
    if orientation == 'portrait' and cropped_height < new_height:
        pad_top =       max( int((new_height - cropped_height) // 2),0)
        pad_bottom =    max( int(new_height - cropped_height - pad_top), 0)

        # Create separate border images for top and bottom
        if pad_top > 0:
            average_color_top = np.mean(return_image[:min(pad_top,10), :], axis=0).astype(int)  # Top 10 rows
            top_border_image = np.tile(average_color_top, (pad_top, 1, 1))
            return_image = np.vstack((top_border_image, return_image))  # Add top border
        if pad_bottom > 0:
            average_color_bottom = np.mean(return_image[-1*min(pad_bottom,10):, :], axis=0).astype(int)  # Bottom 10 rows
            bottom_border_image = np.tile(average_color_bottom, (pad_bottom, 1, 1))
            return_image = np.vstack((return_image, bottom_border_image))  # Add bottom border

    elif orientation == 'landscape' and cropped_width < new_width:
        pad_left = max((new_width - cropped_width) // 2, 0)
        pad_right = max((new_width - cropped_width - pad_left), 0)

        # Create separate border images for left and right
        if pad_left > 0:
            average_color_left = np.mean(return_image[:, :min(pad_left,5)], axis=0).astype(int)  # Left 10 columns
            left_border_image = np.tile(average_color_left, (return_image.shape[0], pad_left, 1))
            if pad_color:
                pad_color_arr = np.array(pad_color)
                left_border_image = np.tile(pad_color_arr, (return_image.shape[0], pad_left, 1))
            return_image = np.hstack((left_border_image, return_image))  # Add left border
        if pad_right > 0:
            average_color_right = np.mean(return_image[:, -1*min(pad_right,5):], axis=0).astype(int)  # Right 10 columns
            right_border_image = np.tile(average_color_right, (return_image.shape[0], pad_right, 1))
            if pad_color:
                pad_color_arr = np.array(pad_color)
                right_border_image = np.tile(pad_color_arr, (return_image.shape[0], pad_right, 1))
            return_image = np.hstack((return_image, right_border_image))  # Add right border

        return_image = return_image.astype(np.uint8)  # Convert to uint8
        # print(f"Exiting Scaling function: Dtype={return_image.dtype}")
    return return_image



def convert_to_grayscale(image):
    """Converts the image passed to the funczion to Grayscale

    Args:
        image: An image object.

    """
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

def convert_to_binary(image, bgr=False, invert=False):
    """Converts the image to binary.

    Args:
      image: The image to be converted to a binary image.
      bgr (bool): If True, converts the binary to a BGR 3-channel image.
      invert (bool): If True, inverts the image.

    Returns:
      Binary version of the image, in the specified format.
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image  # Image is already grayscale

    _, image_binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

    if invert:
        image_binary = cv2.bitwise_not(image_binary)

    if bgr:
        image_binary = cv2.cvtColor(image_binary, cv2.COLOR_GRAY2BGR)  # Assign the result back!

    return image_binary


def rotate_image(img, rotation_degrees):
    """Rotates an image by the specified degrees.

    Args:
      img: The image to be rotated, either grayscale or BGR format (NumPy array).
      rotation_degrees: The angle of rotation in degrees.

    Returns:
      The rotated image as a NumPy array in uint8 format.
    """
    img_rotated = img  # Default to same image

    try:
        (h, w) = img.shape[:2]
        center = (w / 2, h / 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, rotation_degrees, 1.0)

        if len(img.shape) == 2:
            img_rotated = cv2.warpAffine(img, rotation_matrix, (w, h))
        else:
            img_rotated = cv2.warpAffine(img, rotation_matrix, (w, h), flags=cv2.INTER_CUBIC)

        # Ensure the output image is in uint8 format
        img_rotated = img_rotated.astype(np.uint8)  

    except Exception as e:
        print(f"Error when trying to rotate image: {e}")

    return img_rotated


def determine_rotation_angle(img, horizontal_threshold=0.1):
    """Determines the angle to rotate an image to straighten it, considering only horizontal lines.

    Args:
    img: A grayscale or BGR image as a NumPy array.
    horizontal_threshold: The absolute slope threshold for considering a line horizontal (default: 0.1).

    Returns:
    The angle in degrees to rotate the image for straightening based on horizontal lines.
    """

    # Convert to grayscale if needed
    # if len(img.shape) == 3:
    #     img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # else:
    #     img_gray = img

    try:
        # Convert the image to a NumPy array (if it's not already)
        img = np.array(img)

        # Convert to grayscale if needed
        if len(img.shape) == 3:
            img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            img_gray = img

    except AttributeError as e:
        print(f"Error processing image: {e}")
        return 0
        # Add more specific handling if needed (e.g., logging, skipping)

    # Apply Canny edge detection
    img_edges = cv2.Canny(img_gray, 100, 100, apertureSize=3)
    # if DISPLAY_IMAGE_FLAG:
    #     display_image(img_edges, waitkey=True)

    # Detect lines using HoughLinesP
    lines = cv2.HoughLinesP(img_edges, 1, np.pi / 180.0, 100, minLineLength=100, maxLineGap=5)

    if lines is None:
        return 0  # No lines detected, assume no rotation

    horizontal_angles = []
    for [[x1, y1, x2, y2]] in lines:
        if x1 != x2: # Avoid divide by Zero Error
            slope = (y2 - y1) / (x2 - x1)
        else:
            continue
        if abs(slope) < horizontal_threshold:
            angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
            horizontal_angles.append(angle)

    if not horizontal_angles:
        return 0  # No horizontal lines detected, assume no rotation

    median_angle = np.median(horizontal_angles)
    return median_angle


def find_aligned_boxes(boxes, digit_y_alignment):
    """Finds bounding boxes aligned at a specific Y position.

    Args:
    boxes: A list of bounding boxes represented as cv2.Rect objects.
    digit_y_alignment: The maximum allowed Y difference for alignment (integer).

    Returns:
    A list of cv2.Rect objects representing the aligned bounding boxes, sorted by X-Value
    """

    aligned_boxes = []
    current_box = None
    for box in boxes:
        box_x, box_y, box_h, box_w = box
        if not current_box or abs(current_box_y - box_y) < digit_y_alignment:
            if not current_box:
                current_box = box
                current_box_x, current_box_y, current_box_h, current_box_w = current_box
                aligned_boxes.append(box)
            else:
                current_box = box

    # Sort aligned_boxes by X-coordinate
    aligned_boxes.sort(key=lambda box: box[0]) 

    return aligned_boxes

def plot_image(image, title="Image", cmap=None, bgr=False, axis="on"):
    """
    Plots an image using Matplotlib, handling color conversions and different image types.

    Args:
        image (numpy.ndarray): The image to plot.
        title (str, optional): The title of the plot. Defaults to "Image".
        cmap (str, optional): Colormap for grayscale images. Defaults to None.
        bgr (bool, optional): If True, converts BGR to RGB. Defaults to False.
        axis (str, optional) : Turn theplot's axis on or off. Defaults to On.

    """
    if not isinstance(image, np.ndarray):
        raise TypeError("Image must be a NumPy array.")

    if len(image.shape) == 2:  # Grayscale or Binary
        plt.imshow(image, cmap=cmap if cmap else 'gray')
    elif len(image.shape) == 3:
        channels = image.shape[2]
        if channels == 3:  # Color image
            if bgr:
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            plt.imshow(image)
        elif channels == 4: #RGBA Image
            plt.imshow(image)
        else:
            raise ValueError(f"Image has an unsupported number of channels: {channels}")
    else:
        raise ValueError(f"Image has an unsupported number of dimensions: {len(image.shape)}")

    plt.title(title)
    plt.axis(axis)
    plt.show()

def main():
    print("This is just a collection of helper functions....")

    # image = load_image("/Users/yonz/Workspace/images/meter-frame-1/IMG_6981.jpg")

    image = load_image("/Users/yonz/Workspace/meterreader2/meterreader_YOLO/meter-counter-640-1/crops/counters-aonJ/IMG_6986.jpg")

    print(f"Original Image shape: {image.shape}")

    # Attemt to rotate the image so that the horizontal lines are straight,
    # then padd that image to a fixed site, for use in a second model
    rotation_angle = determine_rotation_angle(image, horizontal_threshold=0.1)          
    image_rotated = rotate_image(image, rotation_angle)
    save_image( image_rotated, "/Users/yonz/Workspace/images/IMG_6986_2.jpg")

    # Scale the image
    scaled_image = scale_image(image_rotated,new_size=[192,768], orientation='landscape', pad_color=[255,255,255]  )
    print(f"Scaled Image shape: {scaled_image.shape}\nRottion Angle: {rotation_angle}")
    save_image( scaled_image, "/Users/yonz/Workspace/images/IMG_6986_3.jpg")

    # Convert to Binary (inverse)

    binary_image = convert_to_binary(scaled_image, invert=True)
    save_image( binary_image, "/Users/yonz/Workspace/images/IMG_6986_4.jpg")

    return 0


if __name__ == "__main__":
    main()
