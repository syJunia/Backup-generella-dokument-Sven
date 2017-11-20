#!/usr/bin/env python
# Will rotate, cutout and save images in dir

from gimpfu import *
import os

class TransformCrop:
    def __init__(self, size, offset):
        self.size=size
        self.offset=offset
    def applyToImage(self, image):
        sizeToUse = (self.size[0], self.size[1]);
        maxsize = max(sizeToUse[0] + self.offset[0], sizeToUse[1] + self.offset[1], 1500)
        pdb.gimp_image_resize(image, maxsize, maxsize, self.offset[0], self.offset[1])
        if (sizeToUse[0] == 0 and sizeToUse[1] == 0):
            sizeToUse = (image.width, image.height)
        if (sizeToUse[0] > image.width):
            sizeToUse[0] = image.width
        if (sizeToUse[1] > image.height):
            sizeToUse[1] = image.height
        pdb.gimp_image_crop(image, sizeToUse[0], sizeToUse[1], self.offset[0], self.offset[1])

class TransformRotate:
    def __init__(self, timesToRotate):
        self.timesToRotate = timesToRotate
    def applyToImage(self, image):
        if (self.timesToRotate > 0):
            pdb.gimp_drawable_transform_rotate_simple(image.layers[0], self.timesToRotate - 1, TRUE, 0, 0, TRUE)

class TransformOutput:
    def __init__(self, directoryInputRoot, directoryOutputRoot, filePrefix, fileSuffix, fileExtension):
        self.directoryInputRoot = directoryInputRoot
        self.directoryOutputRoot = directoryOutputRoot
        self.filePrefix = filePrefix
        self.fileSuffix = fileSuffix
        self.fileExtension = fileExtension

    def applyToImage(self, image):
        filePathStemAndExtension = os.path.splitext(image.filename)
        directoryAndStem = os.path.split(filePathStemAndExtension[0])
        directory = directoryAndStem[0];
        directoryInputRootLength = len(self.directoryInputRoot);
        directoryMinusRoot = directory[directoryInputRootLength:]
        directoryOutputFull = self.directoryOutputRoot + directoryMinusRoot
        if (os.path.exists(directoryOutputFull) == FALSE):
            os.mkdir(directoryOutputFull)
        pathToSaveTo = directoryOutputFull + "/" + \
                self.filePrefix + directoryAndStem[1] + \
                self.fileSuffix + self.fileExtension
        print "saving processed image to " + pathToSaveTo
        pdb.gimp_file_save(image, image.layers[0], pathToSaveTo, pathToSaveTo)

class ImageProcessor:
    def __init__(self):
        pass
    def processImageFile(self, fileToProcess, fileExtensionsToProcess, transforms):
        if (fileExtensionsToProcess.find(os.path.splitext(fileToProcess)[1]) >= 0):
            image = pdb.gimp_file_load(fileToProcess, fileToProcess)
            layer = image.layers[0]
            for transform in transforms:
                if (transform != None):
                    transform.applyToImage(image)
    def processImagesInDirectory(self, directoryToProcess, \
            isDirectoryRecursive, fileExtensionsToProcess, transforms):
        if (directoryToProcess.endswith("/") == FALSE):
            directoryToProcess = directoryToProcess + "/";
        filesystemItems = os.listdir(directoryToProcess)
        for filesystemItem in filesystemItems:
            pathToProcess = directoryToProcess + filesystemItem
            print pathToProcess
            if (os.path.isfile(pathToProcess) == TRUE):
                self.processImageFile(pathToProcess, fileExtensionsToProcess, transforms)
            elif (isDirectoryRecursive == TRUE and os.path.isdir(pathToProcess) == TRUE):
                self.processImagesInDirectory(pathToProcess + "/", isDirectoryRecursive, fileExtensionsToProcess, transforms)

def python_fu_batch_multi_processor(directoryInputRoot, isDirectoryInputRecursive, fileExtensionsToProcess, cropSizeX, cropSizeY, cropOffsetX, cropOffsetY, timesToRotate, filePrefixOutput, fileSuffixOutput, fileTypeOutput, directoryOutputRoot):
    crop = TransformCrop([cropSizeX, cropSizeY], [cropOffsetX, cropOffsetY])
    rotate = TransformRotate(timesToRotate % 4)
    output = TransformOutput(directoryInputRoot, directoryOutputRoot, filePrefixOutput, fileSuffixOutput, fileTypeOutput)
    imageProcessor = ImageProcessor()
    imageProcessor.processImagesInDirectory(directoryInputRoot, isDirectoryInputRecursive, fileExtensionsToProcess,[ crop, rotate, output ] )

# for testing in console...
# python_fu_batch_multi_processor("C:/Temp/ImagesIn/", TRUE, ".gif;.jpg;.png;.xcf", 0, 0, 0, 0, 1, "", "-Processed", ".png", "C:/Temp/ImagesOut/")

register(
    "python-fu-batch-multi-processor",
    "Performs various transforms to multiple files and saves the results.",
    "Performs various transforms to multiple files and saves the results.",
    "stg",
    "stg",
    "2013",
    "Batch Multiprocessor...",
    "",
    [
        (PF_STRING, "directoryInputRoot", "Input Directory", "/home/sven/Bilder/scan"),
        (PF_BOOL, "isDirectoryInputRecursive", "Include Subdirectories?", 0),
        (PF_STRING, "fileExtensionsToProcess", "FileExtensionsToProcess", ".gif;.jpg;.png;.xcf;.jpeg"),
        (PF_INT, "cropSizeX", "Crop Width (0 for no crop)", 980),
        (PF_INT, "cropSizeY", "Crop Height (0 for no crop)", 880),
        (PF_INT, "cropOffsetX", "Crop Offset X", 130),
        (PF_INT, "cropOffsetY", "Crop Offset Y", 160),
        (PF_INT, "timesToRotate", "Times To Rotate Clockwise 90 Degrees", 1),
        (PF_STRING, "filePrefixOutput", "Output File Prefix", ""),
        (PF_STRING, "fileSuffixOutput", "Output File Suffix", ""),
        (PF_STRING, "fileExtensionOutput", "Output File Extension:", ".pdf"),
        (PF_STRING, "directoryOutputRoot", "Output Directory", "/home/sven/Bilder/scan"),
    ],
    [],
    python_fu_batch_multi_processor,
    menu="<Image>/Filters/Languages/Python-Fu",
    )

main()
