# (c) 2024 Yonz
# License: Non License
#
#

""" 
## Process
The detation of the value of the electricity meter is done using three different model, to simplify the detection (each model is small enough to allow three t be loaded at the same time). This simplifies the algorithm, as there is hardly any image manipulation required. Inspriration comes from (OpenCV practice: OCR for the electricity meter)[https://en.kompf.de/cplus/emeocv.html]. However, the use of OCR did not give the expected results.

The idea here is to "divide and conquer". I.e. to desect the image in three simple steps, where each step will isolate a part of the image. Each part is big enough so the model will be simple and quick.

 """

#
# Uses the Ultralytics YOLOv11 Libraries
from ultralytics import YOLO
import torch

from  predict_helpers import *

class predicter:
    