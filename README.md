# MeterReader - The Model Training

Notebook: `trainer.ipynb`

This notebok implements the YOLOv11 based trainers for the models used by the meterreader

- Frames : Get Extract the Frame inside of the meter from the original image
- Counter : Extract the Counter from within the frame
- Digits: Get the value of each digit of the Counter

## Training Data

The training data is taken from the respective Roboflow projects. The data is annotated using either Roboflow or manually via script (Digits)

### Roboflow Projects

```

# Roboflow configuration parameters
RF_API_KEY: "xxxxxxxxxxx"
RF_WORKSPACE_NAME: "meterreader"
RF_PROJECT_NAME_FRAME: "meter-frame"
RF_PROJECT_NAME_COUNTERS: "meter-counter-640"
RF_PROJECT_NAME_DIGITS: "meter-digits-itvsi"
RF_VERSION_FRAME: "1"
RF_VERSION_COUNTERS: "1"
RF_VERSION_DIGITS: "2"

```

## Models

The resulting models are saved in the same directory as the downloaded roboflow datasets. 
Moved manually to the "weights" folder in the repository


# MeterReader - The Predicter

Class defintion: `predicter.py` 
Notebook: `predicter_test.ipynb`


This notebok tests the prediction using the models trained by "trainer.ipynb"

- Frames : Get Extract the Frame inside of the meter from the original image
- Counter : Extract the Counter from within the frame
- Digits: Get the value of each digit of the Counter

## Training Data

The training data is taken from the respective Roboflow projects. The data is annotated using either Roboflow or manually via script (Digits)

## Models

The are pre-trained custom models, trained by the "trainer.ipynb script


## Process
The detation of the value of the electricity meter is done using three different model, to simplify the detection (each model is small enough to allow three t be loaded at the same time). This simplifies the algorithm, as there is hardly any image manipulation required. Inspriration comes from [OpenCV practice: OCR for the electricity meter](https://en.kompf.de/cplus/emeocv.html). However, the use of OCR did not give the expected results.

The idea here is to "divide and conquer". I.e. to desect the image in three simple steps, where each step will isolate a part of the image. Each part is big enough so the model will be simple and quick.


### The Frame

![Detected Frame](./static/detected-frame.jpg)

### The counter

![Detected Counter](./static/detected-counter.jpg)

### The digits

![Detected Digits](./static/detected-digits.jpg)




