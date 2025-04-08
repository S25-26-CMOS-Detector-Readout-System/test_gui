# gui.py
# Main test GUI script

import cv2
import tkinter as tk
from PIL import Image, ImageTk

import numpy as np
import cv2 
import threading


#import image_processor

import threading

# import threading # included in image_processor
import queue

import serial
import time

# see socket_interface.py
#import socket_interface

#import udp_server

import socket
import optparse

IMAGE_HEIGHT = 2048
IMAGE_WIDTH = 2048

# Command definitions - GUI to PCB - "CMD_P" indicates additional dynamic information must be concatenated before transmission
# Image collection enable
CMD_P_IMAGE_ENABLE = "CC0F"
# Image data request
CMD_IMAGE_REQUEST = "CCF0"
# Reset
CMD_RESET = "33AA"
# Abort
CMD_ABORT = "3355"
# CMOS Setting
CMD_P_CMOS_SETTING = "AA"

# PCB to GUI
# Acknowledge
SIG_ACK = "44"
# Image data start
SIG_IMAGE_START = "CCF0"
# Image data row 
SIG_IMAGE_DATA = "CC"
# Image data end
SIG_IMAGE_DATA = "CC0F"
# Telemetry
SIG_TELEMETRY = "33"

DEFAULT_IP   = '192.168.137.7'   # IP address of the UDP server 
DEFAULT_PORT = 50007     

SERIAL_COM_PORT = 'COM4' # Serial port


# Todo:
# Create a "timeout" timer to ensure that the frame is not stuck in an incomplete state - skip to next frame if not all rows are filled
# Display fault codes
# Display telemetry data
# Display sensor settings

# Main test software loop

class RowPacket():
    def __init__(self, rowIndex, rowData):
        self.rowIndex = rowIndex # Row index of the image
        self.rowData = rowData # Row data of the image


# Window object, specifying image source, buttons, text, image refresh rate, and other parameters
# implementation partially inspired by https://scribles.net/showing-video-image-on-tkinter-window-with-opencv/ 
class MainWindow():
    def __init__(self, window):
        self.window = window # root
        #self.cap = cap # image source
        #self.width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        #self.height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        self.interval = 100 # Interval in ms to get the latest frame

        # True if using UDP to transmit, false if using serial
        self.transmission_udp = True

        
        self.sock = udp_start()
        #time.sleep(2)
        self.data, self.addr = self.sock.recvfrom(4096)
        print(self.addr)

        try: 
            self.ser = serial.Serial(
                port=SERIAL_COM_PORT,     # Port name (Windows: 'COM1', Linux: '/dev/ttyUSB0', Mac: '/dev/tty.usbserial')
                baudrate=115200,           # Baud rate (must match microcontroller setting)
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1                # Read timeout in seconds
            )
        except serial.SerialException as e:
            print(f"Error opening serial port: {e}")
            self.ser = None
        
        self.frame_queue = queue.Queue() # Queue to hold frames for processing - maxsize prevents memory overflow

        self.processor_thread = threading.Thread(target=self.update_image, daemon=True)
        self.processor_thread.start()
        
        """
        # Create canvas for image (could also use a label insteamobd)
        self.canvas = tk.Canvas(self.window, width=1024, height=1024)
        self.canvas.grid(row=0, column=0)
        self.canvas.pack()
        """
        """
        self.image_frame = tk.Frame(self.window)
        self.image_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.controls_frame = tk.Frame(self.window)
        self.controls_frame.pack(side=tk.TOP, fill=tk.X)
        """

        self.mainImage = tk.Canvas(self.window, width=IMAGE_WIDTH/4, height=IMAGE_HEIGHT/4)
        self.mainImage.create_rectangle(0, 0, IMAGE_WIDTH/4, IMAGE_HEIGHT/4, fill="red", outline="")
        self.mainImage.pack(side=tk.TOP, padx=10, pady=10) 
        
        # Text box
        self.l = tk.Label(self.window, text = "Send a command to readout system")
        self.l.config(font = ("Courier, 12"))
        self.l.pack(side=tk.TOP, padx=10, pady=10)

        # Create buttons to call associated function
        self.button_1 = tk.Button(self.window, text="Reset", command=self.send_reset)
        self.button_1.pack(side=tk.LEFT, padx=10, pady=10)

        self.button_2 = tk.Button(self.window, text="Abort", command=self.send_abort)
        self.button_2.pack(side=tk.LEFT, padx=10, pady=10)

        self.button_3 = tk.Button(self.window, text="Enter Image Collection Mode", command=self.send_enter_image_collection)
        self.button_3.pack(side=tk.LEFT, padx=10, pady=10)

        self.button_4 = tk.Button(self.window, text="Image Request", command=self.send_image_request)
        self.button_4.pack(side=tk.LEFT, padx=10, pady=10)

        self.button_5 = tk.Button(self.window, text="Change sensor settings...", command=open_popup)
        self.button_5.pack(side=tk.LEFT, padx=10, pady=10)

        self.button_6 = tk.Button(self.window, text="Toggle UDP/Serial", command=self.toggle_udp_serial)
        self.button_6.pack(side=tk.LEFT, padx=10, pady=10)

        self.commModetext = tk.Text(self.window, width=15, height=1)
        self.commModetext.insert(1.0, "Using UDP")
        self.commModetext.config(state="disabled")
        self.commModetext.pack(side=tk.BOTTOM, padx=10, pady=10)

        self.tele = tk.Text(self.window, width=30, height=6)
        self.tele.insert(1.0, "Waiting for telemetry")
        self.tele.config(state="disabled")
        self.tele.pack(side=tk.BOTTOM, padx=10, pady=10)




        # Update image on canvas
        #self.update_image()

        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

    def update_image(self):
    # Start timeout timer here?8
        dummy_value = 0
        # Fill all values with NaN as placeholder
        self.frame = np.zeros((IMAGE_HEIGHT, IMAGE_WIDTH), dtype=np.int32) 
        # Tracker array for if corresponding row in frame is filled
        self.rowsFilled = np.ndarray((IMAGE_HEIGHT), dtype=bool)
        self.rowsFilled.fill(False)

        while (True): 
            time.sleep(0.2)
            #print("hello")
            #dummy_value = dummy_value + 1
            
            self.data, self.addr = self.sock.recvfrom(4096)

            #self.sock.sendto(int("CC0F", 16).to_bytes(2), addr)
            #if (int(self.data) > 0):
            
            dataHex = self.data.hex()
            print(dataHex)

            # Eventually, want each bit of telemetry to have its own box rather than putting it all in one box
            header = dataHex[0:2]
            if (header == SIG_TELEMETRY):
                self.tele.config(state="normal")
                self.tele.delete(1.0, tk.END) # clears entire text box at once
                # Current state
                if (dataHex[2:4] == "0F"):
                    self.tele.insert("1.0", "Standby mode")
                elif (dataHex[2:4] == "F0"):
                    self.tele.insert("1.0", "Image collection mode")
                else:
                    self.tele.insert("1.0", "Invalid mode")

                # Temperature
                self.tele.insert("end", "\nTemperature 1: " + str(int(dataHex[4:8], 16)) + " C")
                self.tele.insert("end", "\nTemperature 2: " + str(int(dataHex[8:12], 16)) + " C")
                # Voltage
                self.tele.insert("end", "\nVoltage: " + str(int(dataHex[12:16], 16)) + " V")
                # Fault code
                self.tele.insert("end", "\nFault code: " + str(int(dataHex[16:24], 16)))
                
                

                self.tele.config(state="disabled")
            elif (header == SIG_ACK):
                print("ACK received")
            elif (header == SIG_IMAGE_DATA):
                rowIndex = int(dataHex[2:6], 16)
                #self.frame[rowIndex] = latestRowPacket.rowData
                self.rowsFilled[rowIndex] = True 
                if (np.all(self.rowsFilled)): # If all rows are filled, display the frame
                    pass
                    # Display video frame here
                    #update_image()
                    
                #rowsFilled = np.fill(IMAGE_HEIGHT, False) 
                

            

            #self.ser.write(str.encode(str(dummy_value))) # Send a dummy byte to trigger the readout system - replace with actual command

            #out = b""
            #while self.ser.inWaiting() > 0:
            #    out += self.ser.read(1)
            #print(out)


            """
            # Image packets may be received out of order due to network factors
            if (rowPacketReceived): 
                frame[latestRowPacket.rowIndex] = latestRowPacket.rowData
                rowsFilled[latestRowPacket.rowIndex] = True 
                if (np.all(rowsFilled)): # If all rows are filled, display the frame
                    # Display video frame here
                    #update_image()
                    
                rowsFilled = np.fill(IMAGE_HEIGHT, False) 
            """

    def toggle_udp_serial(self):
        if self.transmission_udp:
            #self.ser.open()
            #self.ser = serial.Serial(...)
            try:
                if (self.ser == None): 
                    self.ser = serial.Serial(
                        port=SERIAL_COM_PORT,     # Port name (Windows: 'COM1', Linux: '/dev/ttyUSB0', Mac: '/dev/tty.usbserial')
                        baudrate=115200,           # Baud rate (must match microcontroller setting)
                        bytesize=serial.EIGHTBITS,
                        parity=serial.PARITY_NONE,
                        stopbits=serial.STOPBITS_ONE,
                        timeout=1                # Read timeout in seconds
                    )
                else:
                    self.ser.open()
                self.transmission_udp = False
                self.commModetext.config(state="normal")
                self.commModetext.delete(1.0, tk.END)
                self.commModetext.insert(1.0, "Using Serial")
                self.commModetext.config(state="disabled")

            except serial.SerialException as e:
                print(f"Error opening serial port: {e}")
            
            
            
        else:
            #self.ser.close()
            #self.ser = None
            self.transmission_udp = True
            self.commModetext.config(state="normal")
            self.commModetext.delete(1.0, tk.END)
            self.commModetext.insert(1.0, "Using UDP")
            self.commModetext.config(state="disabled")

    # Custom functions for each button
    def send_reset(self):
        self.sock.sendto(int(CMD_RESET, 16).to_bytes(2), self.addr)
        print("Reset sent")

    def send_abort(self):
        self.sock.sendto(int(CMD_ABORT, 16).to_bytes(2), self.addr)
        print("Abort sent")

    def send_enter_image_collection(self):
        self.sock.sendto(int(CMD_P_IMAGE_ENABLE, 16).to_bytes(2), self.addr)
        print("Enter image collection mode sent")

    def send_image_request(self):
        self.sock.sendto(int(CMD_IMAGE_REQUEST, 16).to_bytes(2), self.addr)
        print("Image request sent")

    def change_sensor_settings(spec1):
        # TODO
        print("Sensor setting changed to " + str(spec1))

    def get_unix_time_hex():
        # Get Unix timestamp in milliseconds as 64-bit integer
        timestamp_ms = int(time.time() * 1000)
        # Convert to 16-character hex string, removing '0x' prefix
        return format(timestamp_ms, '016x')

# Example usage:
# timestamp = get_unix_time_hex()
# print(timestamp)  # e.g. '0187654321abcdef'


    def on_closing(self):
        print("Closing GUI...")
        if self.processor_thread.is_alive():
            self.processor_thread.join()
            pass
        if (not self.ser):
            pass
        elif (self.ser.is_open):
            self.ser.close()


    """
    def update_image(self): # Get a frame from the queue and display it
        try: 
            #self.image = image_processor.get_image()
            frame = self.frame_queue.get_nowait()
            self.image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.image = Image.fromarray(self.image)
            self.image = ImageTk.PhotoImage(self.image)
            # Change (update) image within main thread
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.image)
        except queue.Empty: 
            pass
    """


    """
    def update_image(self):
        # Get the latest frame and convert image format
        self.image = cv2.cvtColor(self.cap.read()[1], cv2.COLOR_BGR2RGB) # to RGB
        self.image = Image.fromarray(self.image) # to PIL format
        self.image = ImageTk.PhotoImage(self.image) # to ImageTk format

        # Update image
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.image)

        # Repeat this function every self.interval ms
        print("hello")
        self.window.after(self.interval, self.update_image)"
    """
        

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


def udp_start():
    parser = optparse.OptionParser()
    parser.add_option("-p", "--port", dest="port", type="int", default=DEFAULT_PORT, help="Port to listen on [default: %default].")
    parser.add_option("--hostname", dest="hostname", default=DEFAULT_IP, help="Hostname to listen on.")

    (options, args) = parser.parse_args()

    return echo_server(options.hostname, options.port)

def echo_server(host, port):
    print("Creating UDP server")
    # Create a UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    #Bind UDP Server
    #print(host)
    #print(port)
    sock.bind((host,port))
    
    print('UDP Server on IP Address: {} port {}'.format(host, port))
    print('Waiting to receive message from main system to get return address')

    return sock



# Creates a GUI to display a constantly updating image and provide buttons for custom actions
def create_gui():
    
    # Create a Tkinter object
    root = tk.Tk()
    root.title("CMOS Readout System Test GUI")

    # Load the window
    window = MainWindow(root)


    # Run the Tkinter event loop - no code runs beyond here
    root.mainloop()

    return root, window

if __name__ == "__main__":
    # Create and launch the GUI
    # TODO: replace webcam placeholder with the latest frame from readout system in OpenCV format
    print("Starting GUI - this may take a moment")
    create_gui()
    
