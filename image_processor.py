import numpy as np
import cv2 
import gui

IMAGE_HEIGHT = 2048
IMAGE_WIDTH = 2048
# FIll all values with NaN as placeholder
frame = np.zeros((IMAGE_HEIGHT, IMAGE_WIDTH), dtype=np.int32) 
# Tracker array for if corresponding row in frame is filled
rowsFilled = np.fill(IMAGE_HEIGHT, False) 

#root, window = gui.MainWindow() #Get tkinter root, and MainWindow object

# Todo:
# Create a "timeout" timer to ensure that the frame is not stuck in an incomplete state - skip to next frame if not all rows are filled
# Display fault codes
# Display telemetry data
# Display sensor settings
# Simulate a CV2 video feed and run the gui.py script separately?

# Main test software loop
while (True): 
    
    # Image packets may be received out of order due to network factors
    if (rowPacketReceived): 
        frame[latestRowPacket.rowIndex] = latestRowPacket.rowData
        rowsFilled[latestRowPacket.rowIndex] = True 
        if (np.all(rowsFilled)): # If all rows are filled, display the frame
            # Display video frame here
            update_image()
        rowsFilled = np.fill(IMAGE_HEIGHT, False) 
    