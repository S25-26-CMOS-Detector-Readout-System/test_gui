# gui.py
# Main test GUI script


import tkinter as tk

import threading

import queue

import socket

import csv 

import time
import datetime

import optparse

import sys

import os

from PIL import Image, ImageTk
import cv2 
import numpy as np

import serial


IMAGE_HEIGHT = 2048
IMAGE_WIDTH = 512

# Command definitions - GUI to PCB - "CMD_P" indicates additional dynamic information must be concatenated before transmission
# Image collection enable
CMD_P_IMAGE_ENABLE = "CC0F"
# Image data request
CMD_IMAGE_REQUEST = "CCF0"
# Reset
CMD_RESET = "33AA"
# Abort
CMD_ABORT = "3355"
# Set CMOS Setting
CMD_P_CMOS_SETTING = "AA87"
# Get CMSO Setting
CMD_P_GET_CMOS = "AA78"

# PCB to GUI
# Acknowledge
SIG_ACK = "44"
# Image data start
SIG_IMAGE_START = "CCF0"
# Image data row 
SIG_IMAGE_DATA = "CC"
# Image data end
SIG_IMAGE_END = "CC0F"
# Telemetry
SIG_TELEMETRY = "33"

DEFAULT_IP   = '192.168.137.6'  # IP address of the UDP server 
DEFAULT_PORT = 50007     

SERIAL_COM_PORT = 'COM4' # Serial port name (Windows: 'COM1', Linux: '/dev/ttyUSB0', Mac: '/dev/tty.usbserial')

IMAGE_SAVE_DIR = "saved_images" # Directory to save images to



IMAGE_DATA_LENGTH = IMAGE_WIDTH * 3 # Length of data part of image row packet in bytes, no header or leader - normally 6144, depends on row length
            



# Todo:
# Create a "timeout" timer to ensure that the frame is not stuck in an incomplete state - skip to next frame if not all rows are filled
# Display fault codes
# Display sensor settings

# Main test software loop

class Telemetry:
    def __init__(self, state="", temp1=0.0, temp2=0.0, voltage=0.0, fault_code=-1):
        self.state = state
        self.temp1 = temp1
        self.temp2 = temp2 
        self.voltage = voltage
        self.fault_code = fault_code

    @staticmethod
    def from_hex(hex_str):
        if len(hex_str) != 24:
            print("Telemetry hex string has incorrect length")
        
        # Function assumes system header (0x33) occupies position 0:2 of hex_str
        state = "Standby mode" if (hex_str[2:4] == "0F") else "Image collection mode" if (hex_str[2:4] == "F0") else "Invalid mode"
        temp1 = float(int(hex_str[4:8], 16)) # Adjust this depending on how values are formatted in hex
        temp2 = float(int(hex_str[8:12], 16))
        voltage = float(int(hex_str[12:16], 16))
        faultCode = int(hex_str[16:24], 16)
        
        return Telemetry(state, temp1, temp2, voltage, faultCode)
    

# Replaces standard sys.stdout with a GUI text box to display console output
class ConsoleRedirect:
    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.text_widget.config(state="normal")  
        self.text_widget.delete("1.0", tk.END)  
        self.text_widget.config(state="disabled") 
        

    def write(self, message):
        self.text_widget.config(state="normal") 
        # When print() is called, write() is called twice - once with the message, once with a newline
        self.text_widget.insert(tk.END, message) 
        self.text_widget.see(tk.END) 
        self.text_widget.config(state="disabled")  

    """
    def write(self, message, timestamp):
        self.text_widget.config(state="normal") 
        currTime = datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        self.text_widget.insert(tk.END, f"{currTime}: {message}\n")
        self.text_widget.see(tk.END) 
        self.text_widget.config(state="disabled")
    """

    def flush(self):
        pass  # Required for compatibility with sys.stdout

# Window object, specifying image source, buttons, text, image refresh rate, and other parameters
# implementation partially inspired by https://scribles.net/showing-video-image-on-tkinter-window-with-opencv/ 
class MainWindow():
    def __init__(self, window):
        
        self.window = window 

        # True if using UDP to transmit, false if using serial
        self.transmission_udp = True

        
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

        # Main CMOS sensor output image
        self.main_image = tk.Canvas(self.window, width=IMAGE_WIDTH//4, height=IMAGE_HEIGHT//4)
        self.main_image.create_rectangle(0, 0, IMAGE_WIDTH//4, IMAGE_HEIGHT//4, fill="red", outline="")
        self.main_image.grid(row=0, column=0, rowspan=9, columnspan=1)
        
        # Text box
        #self.l = tk.Label(self.window, text = "Send a command to readout system")
        #self.l.config(font = ("Courier, 12"))
        #self.l.pack(side=tk.TOP, padx=10, pady=10)
        #self.l.grid(row=1, column=0, padx=10, pady=10)

        # Create buttons to call associated function
        self.button_1 = tk.Button(self.window, text="Reset", command=self.send_reset)
        self.button_1.grid(row=0, column=1)

        self.button_2 = tk.Button(self.window, text="Abort", command=self.send_abort)
        self.button_2.grid(row=1, column=1)

        self.button_3 = tk.Button(self.window, text="Enter Image Collection Mode", command=self.send_enter_image_collection)
        self.button_3.grid(row=2, column=1)

        self.button_4 = tk.Button(self.window, text="Image Request", command=self.send_image_request)
        self.button_4.grid(row=3, column=1)

        self.button_5 = tk.Button(self.window, text="Change sensor settings...", command=self.open_popup)
        self.button_5.grid(row=4, column=1)

        self.button_6 = tk.Button(self.window, text="Get sensor setting", command=self.toggle_udp_serial)
        self.button_6.grid(row=5, column=1)

        self.button_7 = tk.Button(self.window, text="Toggle UDP/Serial", command=self.toggle_udp_serial)
        self.button_7.grid(row=6, column=1)

        self.button_8 = tk.Button(self.window, text="0xffff", command=self.read_image)
        self.button_8.grid(row=9, column=3)

        self.comm_mode_text = tk.Text(self.window, width=15, height=1)
        self.comm_mode_text.insert(1.0, "Using UDP")
        self.comm_mode_text.config(state="disabled")
        self.comm_mode_text.grid(row=7, column=1)

        self.enable_save_images = tk.IntVar(value = 1)
        self.checkbutton_save_images = tk.Checkbutton(self.window, text="Save images to disk", variable=self.enable_save_images, onvalue=1, offvalue=0)
        self.checkbutton_save_images.grid(row=8, column=1)

        self.tele = tk.Text(self.window, width=30, height=6)
        self.tele.insert(1.0, "Waiting for telemetry")
        self.tele.config(state="disabled")
        self.tele.grid(row=9, column=1)

        self.console_output = tk.Text(self.window, height=10, width=80, wrap="word")
        self.console_output.config(state="disabled")  
        self.console_output.grid(row=9, column=0, padx=10)

        #sys.stdout = ConsoleRedirect(self.console_output)  # Redirect stdout to the text box
        #sys.stderr = ConsoleRedirect(self.console_output)  # Redirect stderr to the text box
        self.log_to_file("GUI started")

        #self.window.rowconfigure(1, weight=1)  # Make the first column expandable

        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Initialize connection
        # Attempt to initialize UDP
        self.sock = None
        try:
            self.sock = udp_start()
            self.data, self.addr = self.sock.recvfrom(4096)
            print(self.addr)
        except OSError as e:
            self.log_to_file(f"Error creating UDP socket (1): {e}")

        
        try: 
            self.ser = serial.Serial(
                port=SERIAL_COM_PORT,    
                baudrate=115200,           
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1                # Read timeout in seconds
            )
            # If serial successfully opens but UDP is already open, close serial
            if (self.ser.is_open and self.sock != None):
                self.ser.close()
            # If serial is open and UDP is not open, set transmission_udp to false
            elif(self.ser.is_open and self.sock == None):
                self.transmission_udp = False
                self.comm_mode_text = tk.Text(self.window, width=15, height=1)
                self.comm_mode_text.insert(1.0, "Using Serial")
                self.comm_mode_text.config(state="disabled")
                self.comm_mode_text.pack(side=tk.BOTTOM, padx=10, pady=10)
                
        except serial.SerialException as e:
            self.log_to_file(f"Error opening serial connection (1): {e}")
            self.ser = None
        
        self.frame_queue = queue.Queue() # Queue to hold frames for processing - maxsize prevents memory overflow

        self.processor_thread = threading.Thread(target=self.update_image, daemon=True)
        self.processor_thread.start()

    def update_image(self):
    # Start timeout timer here?

        # Fill all values with NaN as placeholder
        self.frame = np.zeros((IMAGE_HEIGHT, IMAGE_WIDTH), dtype=np.int32) 
        # Tracker array for if corresponding row in frame is filled
        self.rows_filled = np.ndarray((IMAGE_HEIGHT), dtype=bool)
        self.rows_filled.fill(False)

        while (True): 
            #time.sleep(0.2)
            
            data_hex = None
           
            # Receiving UDP
            if (self.transmission_udp and self.sock != None):
                try: 
                    self.data, self.addr = self.sock.recvfrom(4096)
                except:
                    # This should only run when socket is closed by main thread in on_closing
                    print("No socket detected, expecting GUI to close")
                    time.sleep(2) # Delay loop from restarting and printing the above again
                data_hex = self.data.hex()
                # Print raw bytes of received packet for diagnostic
                print("UDP: " + data_hex)
            # Reveiving Serial
            elif (not self.transmission_udp and self.ser.is_open):
                out = b""
                while (self.ser.inWaiting() > 0):
                    out += self.ser.read(1)
                if (out != b""):
                    print("Serial: " + out) 
                continue
            # Not receiving either
            else:
                continue

            #self.sock.sendto(int("CC0F", 16).to_bytes(2), addr)
            #if (int(self.data) > 0):
            
            #out = b""
            #while (self.ser.inWaiting() > 0):
            #    out += self.ser.read(1)
            #print(out) 
            
        
            if (data_hex != None):
                header = data_hex[0:2]
                if (header.casefold() == SIG_IMAGE_DATA.casefold()):
                    if (len(data_hex) == 1538): # Length of an image data packet - normally 6144+8
                        
                        rowIndex = int(data_hex[2:6], 16)
                        print("Detected image packet for row", rowIndex)

                        if (rowIndex >= IMAGE_HEIGHT):
                            continue
                        # Convert hex string to 12-bit integers, 3 hex digits per integer
                        imageData = data_hex[6:(6 + IMAGE_DATA_LENGTH)]
                        #padding = (3 - len(imageData) % 3) % 3 # This and next line may not be neccessary if correct length is always sent - replace with error if incorect length?
                        #imageData = '0' * padding + imageData

                        #self.frame[rowIndex] = [int(imageData[i:i+3], 16) for i in range(0, len(imageData), 3)]
                        for i in range(0, len(imageData), 3):
                            self.frame[rowIndex, i // 3] = int(imageData[i:i+3], 16)
                        
                        self.rows_filled[rowIndex] = True 

                        # Replace this with if (True) to test without full data
                        if (False):
                        #if (np.all(self.rows_filled)): # If all rows are filled, display the frame
                            
                            print("Updating image:")
                            # Reset rows_filled to all false
                            self.rows_filled.fill(False)
                        
                            # Display video frame here

                            #print(self.frame[0:15, 0:15])

                            #self.frame[400:500, 400:500] = 4000
                            
                            # Downscale to 1/4 size for display
                            frameResized = cv2.resize(self.frame, (IMAGE_WIDTH//4, IMAGE_HEIGHT//4), interpolation=cv2.INTER_NEAREST) 
                            normalized_8 = (frameResized / 4095.0 * 255).astype(np.uint8)

                            #normalized = (self.frame / 4095.0 * 255).astype(np.uint8)
                            #frameResized = cv2.resize(normalized, (IMAGE_WIDTH//4, IMAGE_HEIGHT//4), interpolation=cv2.INTER_NEAREST )

                            pil_image = ImageTk.PhotoImage(image=Image.fromarray(normalized_8, mode='L')) # L = grayscale - ImageTK only supports 8-bit

                            # Check over these lines
                            self.main_image.create_image(0, 0, anchor=tk.NW, image=pil_image)
                            self.main_image.image = pil_image

                            if (self.enable_save_images.get()):
                                # Save image to disk
                                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                                filename = os.path.join(IMAGE_SAVE_DIR, f"image_{timestamp}.png")
                                normalized_16 = (self.frame * (65535.0/4095)).astype(np.uint16) # Convert to 16-bit for saving
                                cv2.imwrite(filename, normalized_16)
                                self.log_to_file(f"Saved image to {filename}")
                                
                            
                        #rows_filled = np.fill(IMAGE_HEIGHT, False) 
                    elif (data_hex[0:4].casefold() == SIG_IMAGE_START.casefold()): # Length of an image start packet
                        self.log_to_file("Received image start packet")
                    elif (data_hex[0:4].casefold() == SIG_IMAGE_END.casefold()): # Length of an image end packet
                        self.log_to_file("Received image end packet")
                        percent_filled = np.count_nonzero(self.rows_filled) / self.rows_filled.size * 100
                        self.log_to_file(f"Frame completion: {percent_filled:.1f}%")
                        print("Updating image:")
                        # Reset rows_filled to all false
                        self.rows_filled.fill(False)
                    
                        # Display video frame here

                        #print(self.frame[0:15, 0:15])

                        #self.frame[400:500, 400:500] = 4000
                        
                        # Downscale to 1/4 size for display
                        frameResized = cv2.resize(self.frame, (IMAGE_WIDTH//4, IMAGE_HEIGHT//4), interpolation=cv2.INTER_NEAREST) 
                        normalized_8 = (frameResized / 4095.0 * 255).astype(np.uint8)

                        #normalized = (self.frame / 4095.0 * 255).astype(np.uint8)
                        #frameResized = cv2.resize(normalized, (IMAGE_WIDTH//4, IMAGE_HEIGHT//4), interpolation=cv2.INTER_NEAREST )

                        pil_image = ImageTk.PhotoImage(image=Image.fromarray(normalized_8, mode='L')) # L = grayscale - ImageTK only supports 8-bit

                        # Check over these lines
                        self.main_image.create_image(0, 0, anchor=tk.NW, image=pil_image)
                        self.main_image.image = pil_image

                        if (self.enable_save_images.get()):
                            # Save image to disk
                            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                            filename = os.path.join(IMAGE_SAVE_DIR, f"image_{timestamp}.png")
                            normalized_16 = (self.frame * (65535.0/4095)).astype(np.uint16) # Convert to 16-bit for saving
                            cv2.imwrite(filename, normalized_16)
                            self.log_to_file(f"Saved image to {filename}")
                    # Create "process telemetry" function to simplfy code?

                elif (header.casefold() == SIG_TELEMETRY.casefold()):
                    curr_telemetry = Telemetry.from_hex(data_hex)
                   
                    self.tele.config(state="normal")
                    self.tele.delete(1.0, tk.END) # clears entire text box at once
                    
                    # Print telemetry data to GUI
                    self.tele.insert("1.0", curr_telemetry.state)
                    self.tele.insert("end", f"\nTemperature 1: {curr_telemetry.temp1} C")
                    self.tele.insert("end", f"\nTemperature 2: {curr_telemetry.temp2} C")
                    self.tele.insert("end", f"\nVoltage: {curr_telemetry.voltage} V")
                    self.tele.insert("end", f"\nFault code: {curr_telemetry.fault_code}")

                    self.tele.config(state="disabled")

                    self.log_to_file("Received telemetry", curr_telemetry)

                elif (header.casefold() == SIG_ACK.casefold()):
                    self.log_to_file("Received ACK")
                    
                

            #self.ser.write(str.encode(str(dummy_value))) # Send a dummy byte to trigger the readout system - replace with actual command

            #out = b""
            #while self.ser.inWaiting() > 0:
            #    out += self.ser.read(1)
            #print(out)


            """
            # Image packets may be received out of order due to network factors
            if (rowPacketReceived): 
                frame[latestRowPacket.rowIndex] = latestRowPacket.rowData
                rows_filled[latestRowPacket.rowIndex] = True 
                if (np.all(rows_filled)): # If all rows are filled, display the frame
                    # Display video frame here
                    #update_image()
                    
                rows_filled = np.fill(IMAGE_HEIGHT, False) 
            """

    def toggle_udp_serial(self):
        if self.transmission_udp: # If already transmitting via UDP
            try:
                # If serial is not open, open it
                if (self.ser == None): 
                    self.ser = serial.Serial(
                        port=SERIAL_COM_PORT,     # Port name (Windows: 'COM1', Linux: '/dev/ttyUSB0', Mac: '/dev/tty.usbserial')
                        baudrate=115200,           # Baud rate (must match microcontroller setting)
                        bytesize=serial.EIGHTBITS,
                        parity=serial.PARITY_NONE,
                        stopbits=serial.STOPBITS_ONE,
                        timeout=1                # Read timeout in seconds
                    )
                elif (not self.ser.is_open):
                    self.ser.open()
                self.transmission_udp = False
                self.comm_mode_text.config(state="normal")
                self.comm_mode_text.delete(1.0, tk.END)
                self.comm_mode_text.insert(1.0, "Using Serial")
                self.comm_mode_text.config(state="disabled")

            except serial.SerialException as e:
                self.log_to_file(f"Error opening serial connection (2): {e}")
            
        else: # If already transmitting with serial
            #self.ser.close()
            #self.ser = None
            try:
                if (self.sock == None):
                    self.sock = udp_start()
                    self.data, self.addr = self.sock.recvfrom(4096)
                    print(self.addr)
                else:
                    self.data, self.addr = self.sock.recvfrom(4096)
                    print(self.addr)
                self.transmission_udp = True
                self.comm_mode_text.config(state="normal")
                self.comm_mode_text.delete(1.0, tk.END)
                self.comm_mode_text.insert(1.0, "Using UDP")
                self.comm_mode_text.config(state="disabled")
                self.ser.close()
            except:
                self.log_to_file("Error creating UDP socket (2)")
            

    # Custom functions for each button
    def send_reset(self):
        if (self.transmission_udp and self.sock != None):
            self.sock.sendto(int(CMD_RESET, 16).to_bytes(2), self.addr)
            self.log_to_file("Sent reset, UDP")
        elif (not self.transmission_udp and self.ser.is_open):
            self.ser.write(str.encode(CMD_RESET))
            self.log_to_file("Sent reset, serial")
        else:
            self.log_to_file("Failed to send reset - no connection established")
        
        

    def send_abort(self):
        if (self.transmission_udp and self.sock != None):
            self.sock.sendto(int(CMD_ABORT, 16).to_bytes(2), self.addr)
            self.log_to_file("Sent abort, UDP")
        elif (not self.transmission_udp and self.ser.is_open):
            self.ser.write(str.encode(CMD_ABORT))
            self.log_to_file("Sent abort, serial")
        else:
            self.log_to_file("Failed to send abort - no connection established")
        

    def send_enter_image_collection(self):
        if (self.transmission_udp and self.sock != None):
            #self.sock.sendto(int(CMD_P_IMAGE_ENABLE, 16).to_bytes(2), self.addr)
            # with unix timecode: 
            self.sock.sendto(int(CMD_P_IMAGE_ENABLE + self.get_unix_time_hex(), 16).to_bytes(10), self.addr)
            self.log_to_file("Sent enter image collection mode, UDP")
        elif (not self.transmission_udp and self.ser.is_open):
            self.ser.write(str.encode(CMD_P_IMAGE_ENABLE) + str.encode(self.get_unix_time_hex()))
            self.log_to_file("Sent enter image collection mode, serial")
        else:
            self.log_to_file("Failed to send enter image collection mode - no connection established")
        

    def send_image_request(self):
        if (self.transmission_udp and self.sock != None):
            self.sock.sendto(int(CMD_IMAGE_REQUEST, 16).to_bytes(2), self.addr)
            self.log_to_file("Sent image request, UDP")
        elif (not self.transmission_udp and self.ser.is_open):
            self.ser.write(str.encode(CMD_IMAGE_REQUEST))
            self.log_to_file("Sent image request, serial")
        else:
            self.log_to_file("Failed to send image request - no connection established")

    def read_image(self):
        if (self.transmission_udp and self.sock != None):
            self.sock.sendto(int("FFFF", 16).to_bytes(2), self.addr)
            self.log_to_file("Sent read image, UDP")
        else:
            self.log_to_file("Failed to send ffff - no connection established")

    def open_popup(self):
        top = tk.Toplevel()
        top.option_add("*Font", "Consolas 12")
        #top.geometry("500x250")
        top.title("Change Sensor Settings")
        #label_top = tk.Label(top, text= "Change sensor settings")
        #label_top.grid(row=0, column=0, padx=10, pady=10, rowspan=1, columnspan=3)

        label_1 = tk.Label(top, text= "Subsampling setting")
        label_1.grid(row=1, column=0, padx=10, pady=10)
        label_1_a = tk.Label(top, text= "[0-2046]")
        label_1_a.grid(row=1, column=1, padx=0, pady=10)
        inputText_1 = tk.Text(top, height = 1, width = 6, bg = "light yellow")
        inputText_1.grid(row=1, column=2, padx=0, pady=10)

        label_2 = tk.Label(top, text= "Offset")
        label_2.grid(row=2, column=0, padx=10, pady=10)
        label_2_a = tk.Label(top, text= "[-8192-8191]")
        label_2_a.grid(row=2, column=1, padx=0, pady=10)
        inputText_2 = tk.Text(top, height = 1, width = 6, bg = "light yellow")
        inputText_2.grid(row=2, column=2, padx=0, pady=10)

        label_3 = tk.Label(top, text= "Analog gain (PGA_gain)")
        label_3.grid(row=3, column=0, padx=10, pady=10)
        label_3_a = tk.Label(top, text= "[0-3]")
        label_3_a.grid(row=3, column=1, padx=0, pady=10)
        inputText_3 = tk.Text(top, height = 1, width = 6, bg = "light yellow")
        inputText_3.grid(row=3, column=2, padx=0, pady=10)

        gain_x2 = tk.IntVar(value=0)
        prev_gain_mult = tk.IntVar(value=gain_x2.get()) # Previously used gain_x2, used to send command only if tick box is changed
        label_4 = tk.Label(top, text= "Analog gain x2 multiplier")
        label_4.grid(row=4, column=0, padx=10, pady=10)
        checkbutton_4 = tk.Checkbutton(top, text="Enable", variable=gain_x2, onvalue=1, offvalue=0)
        checkbutton_4.grid(row=4, column=2, padx=0, pady=10)

        label_5 = tk.Label(top, text= "Digital gain (ADC_gain)")
        label_5.grid(row=5, column=0, padx=10, pady=10)
        label_5_a = tk.Label(top, text= "[0-255]")
        label_5_a.grid(row=5, column=1, padx=0, pady=10)
        inputText_5 = tk.Text(top, height = 1, width = 6, bg = "light yellow")
        inputText_5.grid(row=5, column=2, padx=0, pady=10)

        bit_options = ["10-bit", "12-bit"]
        bit_selected_opt = tk.StringVar(value="12-bit") 
        prev_bit_option = tk.StringVar(value=bit_selected_opt.get()) # Previously used bit resolution option, used to send command only if dropdown selection is changed
        label_6 = tk.Label(top, text= "Bit resolution")
        label_6.grid(row=6, column=0, padx=10, pady=10)
        #label_5_a = tk.Label(top, text= "0x")
        #label_5_a.grid(row=5, column=1, padx=0, pady=10)
        inputText_6 = tk.OptionMenu(top, bit_selected_opt, *bit_options)
        inputText_6.grid(row=6, column=2, padx=0, pady=10)
        
        def submit_settings():
            
            # Get subsample value and convert to 2-character hex
            if (len(inputText_1.get("1.0", "end-1c")) > 0): 
                subsample = int(inputText_1.get("1.0", "end-1c"))
                if 0 <= subsample <= 2046:
                    subsample_hex = format(subsample, '04x')
                    self.change_sensor_settings(format(35, '02x') + subsample_hex[2:4])
                    self.change_sensor_settings(format(36, '02x') + subsample_hex[0:2])
                    self.change_sensor_settings(format(37, '02x') + subsample_hex[2:4])
                    self.change_sensor_settings(format(38, '02x') + subsample_hex[0:2])
                else:
                    print("Error: Subsample value must be between 0 and 2046")
                    return
            
            if (len(inputText_2.get("1.0", "end-1c")) > 0):
                offset = int(inputText_2.get("1.0", "end-1c"))
                if -8192 <= offset <= 8191:
                    # Convert to 14-bit two's complement hex string
                    if offset < 0:
                        offset_val = (1 << 14) + offset # Add 2^14 to get two's complement
                    else:
                        offset_val = offset
                    offset_hex = format(offset_val & 0x3FFF, '04x') # Mask to 14 bits and format as 4-char hex
                    self.change_sensor_settings(format(100, '02x') + offset_hex[2:4])
                    self.change_sensor_settings(format(101, '02x') + offset_hex[0:2])
                    #offset_hex = format(offset, '04x')
                else:
                    print("Error: Offset value must be between -8192 and 8191")
                    return
            
            if (len(inputText_3.get("1.0", "end-1c")) > 0):
                a_gain = int(inputText_3.get("1.0", "end-1c"))
                if 0 <= a_gain <= 3:
                    a_gain_hex = format(a_gain, '02x')
                    self.change_sensor_settings(format(102, '02x') + a_gain_hex)
                else:
                    print("Error: Analog gain value must be between 0 and 3")
                    return
            
            if (prev_gain_mult.get() != gain_x2.get()):
                prev_gain_mult.set(gain_x2.get())
                gain_mult_hex = format(prev_gain_mult.get(), '02x')
                self.change_sensor_settings(format(121, '02x') + gain_mult_hex)

            if (len(inputText_5.get("1.0", "end-1c")) > 0):
                d_gain = int(inputText_5.get("1.0", "end-1c"))
                if 0 <= d_gain <= 255:
                    d_gain_hex = format(d_gain, '04x')
                    self.change_sensor_settings(format(103, '02x') + d_gain_hex)
                else:
                    print("Error: Digital gain value must be between 0 and 2046")
                    return
            

            if (prev_bit_option.get() != bit_selected_opt.get()):
                prev_bit_option.set(bit_selected_opt.get())
                if bit_selected_opt.get() == "10-bit":
                    self.change_sensor_settings(format(111, '02x') + "01")
                    self.change_sensor_settings(format(112, '02x') + "00")
                elif bit_selected_opt.get() == "12-bit":
                    self.change_sensor_settings(format(111, '02x') + "00")
                    self.change_sensor_settings(format(112, '02x') + "02")
                

            #sensor_setting_data = subsample_hex + offset_hex + a_gain_hex + "0" + a_gain_mult_hex + d_gain_hex + "0" + bit_hex
            
            #self.change_sensor_settings(sensor_setting_data)
            
        button_1 = tk.Button(top, text="Submit sensor settings...", font=("TkDefaultFont"), justify="right", anchor="w", command=submit_settings)
        button_1.grid(row=7, column=1, padx=0, pady=10)

            
    def change_sensor_settings(self, spec1): #spec1 instead of self?
        #print(len(spec1))
        if (self.transmission_udp and self.sock != None):
            self.sock.sendto(int(CMD_P_CMOS_SETTING + spec1, 16).to_bytes(10), self.addr)
            self.log_to_file("Sent change sensor setting, UDP")
            self.log_to_file("Sensor setting changed to " + spec1)
        elif (not self.transmission_udp and self.ser.is_open):
            self.ser.write(str.encode(CMD_P_CMOS_SETTING + spec1))
            self.log_to_file("Sent change sensor setting, serial")
            self.log_to_file("Sensor setting changed to " + spec1)
        else:
            self.log_to_file("Failed to send change sensor setting - no connection established: " + spec1)
            
        


    # Get Unix timestamp as 64-bit integer to sent with packets
    def get_unix_time_hex(self):
        timestamp = int(time.time())
        # Convert to 16-character hex string, removing '0x' prefix
        return format(timestamp, '016x')
    
    # 
    def log_to_file(self, message, telemetry=None):
        """
        Args:
            message (str): A message to save to the log.
            telemetry (telemetry): A class containing telemetry information.
        """
        # Open the CSV in append mode
        with open("packet_log.csv", mode="a", newline="") as file:
            
            writer = csv.writer(file)
            
            # Get the current timestamp
            timestamp = datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # Format: YYYY-MM-DD HH:MM:SS.mmm
            print(timestamp + ": " + message)

            # Write the log entry
            if (telemetry == None):
                writer.writerow([timestamp, message])
            else:
                writer.writerow([timestamp, message, telemetry.state, telemetry.temp1, telemetry.temp2, telemetry.voltage, telemetry.fault_code])


    def on_closing(self):
        self.log_to_file("Closing GUI")
        # Set a flag to stop the processing thread
        self.running = False
        # Close UDP socket if it exists
        if self.sock:
            print("Closing UDP socket...")
            self.sock.close()
        # Close serial if it exists and is open
        if self.ser and self.ser.is_open:
            print("Closing serial...")
            self.ser.close()
        # Wait for processor thread to finish
        if self.processor_thread.is_alive():
            self.processor_thread.join(timeout=1.0)

        sys.stdout = sys.__stdout__  # Restore original stdout
        self.window.destroy()


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
    root.title("CMOS Readout System Test System")

    # Load the window
    window = MainWindow(root)


    # Run the Tkinter event loop - no code runs beyond here
    root.mainloop()

    return root, window


if __name__ == "__main__":
    if not os.path.exists(IMAGE_SAVE_DIR): # Create directory if it does not exist
        os.makedirs(IMAGE_SAVE_DIR)

    # Create and launch the GUI
    print("Starting GUI - this may take a moment")
    create_gui()
    
