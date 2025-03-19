# gui.py
# Main test GUI script

import cv2
import tkinter as tk
from PIL import Image, ImageTk

# see socket_interface.py
import socket_interface

# Window object, specifying image source, buttons, text, image refresh rate, and other parameters
# implementation partially inspired by https://scribles.net/showing-video-image-on-tkinter-window-with-opencv/ 
class MainWindow():
    def __init__(self, window, cap):
        self.window = window # root
        self.cap = cap # image source
        self.width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        self.height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        self.interval = 100 # Interval in ms to get the latest frame

        # Create canvas for image (could also use a label instead)
        self.canvas = tk.Canvas(self.window, width=self.width, height=self.height)
        self.canvas.grid(row=0, column=0)
        self.canvas.pack()

        # Text box
        self.l = tk.Label(self.window, text = "Send a command to readout system")
        self.l.config(font = ("Courier, 12"))
        self.l.pack()

        # Create buttons to call associated function
        self.button_1 = tk.Button(self.window, text="Reset", command=send_reset)
        self.button_1.pack(side=tk.LEFT, padx=10, pady=10)

        self.button_2 = tk.Button(self.window, text="Abort", command=send_abort)
        self.button_2.pack(side=tk.LEFT, padx=10, pady=10)

        self.button_3 = tk.Button(self.window, text="Enter Image Collection Mode", command=send_enter_image_collection)
        self.button_3.pack(side=tk.LEFT, padx=10, pady=10)

        self.button_4 = tk.Button(self.window, text="Image Request", command=send_image_request)
        self.button_4.pack(side=tk.LEFT, padx=10, pady=10)

        self.button_5 = tk.Button(self.window, text="Change sensor settings...", command=open_popup)
        self.button_5.pack(side=tk.LEFT, padx=10, pady=10)

        self.t = tk.Text(self.window, width=30, height=6)
        self.t.insert(1.0, "Placeholder Telemetry")
        self.t.config(state="disabled")
        self.t.pack()


        # Update image on canvas
        self.update_image()

    def update_image(self):
        # Get the latest frame and convert image format
        self.image = cv2.cvtColor(self.cap.read()[1], cv2.COLOR_BGR2RGB) # to RGB
        self.image = Image.fromarray(self.image) # to PIL format
        self.image = ImageTk.PhotoImage(self.image) # to ImageTk format

        # Update image
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.image)

        # Repeat this function every self.interval ms
        self.window.after(self.interval, self.update_image)

# Move this back into the MainWindow() function
def open_popup():
        top = tk.Toplevel()
        top.geometry("500x250")
        top.title("Change Sensor Settings")
        label_1 = tk.Label(top, text= "Placeholder: Change sensor setting", font=('Courier, 12'))
        label_1.place(x=80,y=80)
        inputtxt = tk.Text(top, height = 1, width = 14, bg = "light yellow")
        inputtxt.pack(side=tk.LEFT, padx=10, pady=10)
        button_1 = tk.Button(top, text="Change sensor settings...", command=lambda: change_sensor_settings(inputtxt.get("1.0", "end-1c")))
        #button_6 = Button(top, text="Change sensor settings...", command=change_sensor_settings(100))
        button_1.pack(side=tk.LEFT, padx=10, pady=10)

        top.mainloop()


# Custom functions for each button
# TODO: send appropriate byte to Socket interface
def send_reset():
    print("Reset sent")

def send_abort():
    print("Abort sent")

def send_enter_image_collection():
    print("Enter image collection mode sent")

def send_image_request():
    print("Image request sent")

def change_sensor_settings(spec1):
    print("Sensor setting changed to " + str(spec1))




# Creates a GUI to display a constantly updating image and provide buttons for custom actions
def create_gui(image_source):
    
    # Create a Tkinter object
    root = tk.Tk()
    root.title("CMOS Readout System Test GUI")

    # Load the window
    window = MainWindow(root, image_source)

    # Run the Tkinter event loop - no code runs beyond here
    # root.mainloop()

    return root, window

if __name__ == "__main__":
    # Create and launch the GUI
    # TODO: replace webcam placeholder with the latest frame from readout system in OpenCV format
    print("Starting GUI - this may take a moment")
    create_gui(cv2.VideoCapture(0))
    #create_gui(cv2.VideoCapture("ReadoutTester/file_example_MP4_1920_18MG.mp4"))
