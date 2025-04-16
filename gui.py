# gui.py
# Main test GUI script

import tkinter as tk

from PIL import Image, ImageTk
import cv2 
import numpy as np

import threading

import queue

import socket
import serial

import csv 

import time
import datetime

import optparse

import sys


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
SIG_IMAGE_END = "CC0F"
# Telemetry
SIG_TELEMETRY = "33"

DEFAULT_IP   = '192.168.137.7'  # IP address of the UDP server 
DEFAULT_PORT = 50007     

SERIAL_COM_PORT = 'COM4' # Serial port name (Windows: 'COM1', Linux: '/dev/ttyUSB0', Mac: '/dev/tty.usbserial')

IMAGE_DATA_LENGTH = 8
            # just the data part, no header or leader - normally 6144, depends on row length



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
        self.text_widget.insert(tk.END, message) 
        self.text_widget.see(tk.END) 
        self.text_widget.config(state="disabled")  

    def flush(self):
        pass  # Required for compatibility with sys.stdout

# Window object, specifying image source, buttons, text, image refresh rate, and other parameters
# implementation partially inspired by https://scribles.net/showing-video-image-on-tkinter-window-with-opencv/ 
class MainWindow():
    def __init__(self, window):
        self.log_to_file("GUI started")
        self.window = window 
        self.window
        #self.cap = cap # image source
        #self.width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        #self.height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        self.interval = 100 # Interval in ms to get the latest frame

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
        self.mainImage = tk.Canvas(self.window, width=IMAGE_WIDTH/4, height=IMAGE_HEIGHT/4)
        self.mainImage.create_rectangle(0, 0, IMAGE_WIDTH/4, IMAGE_HEIGHT/4, fill="red", outline="")
        #self.mainImage.pack(side=tk.TOP, padx=10, pady=10) 
        self.mainImage.grid(row=0, column=0, rowspan=6, columnspan=1)
        
        # Text box
        #self.l = tk.Label(self.window, text = "Send a command to readout system")
        #self.l.config(font = ("Courier, 12"))
        #self.l.pack(side=tk.TOP, padx=10, pady=10)
        #self.l.grid(row=1, column=0, padx=10, pady=10)

        # Create buttons to call associated function
        self.button_1 = tk.Button(self.window, text="Reset", command=self.send_reset)
        #self.button_1.pack(side=tk.LEFT, padx=10, pady=10)
        self.button_1.grid(row=0, column=1)

        self.button_2 = tk.Button(self.window, text="Abort", command=self.send_abort)
        #self.button_2.pack(side=tk.LEFT, padx=10, pady=10)
        self.button_2.grid(row=1, column=1)

        self.button_3 = tk.Button(self.window, text="Enter Image Collection Mode", command=self.send_enter_image_collection)
        #self.button_3.pack(side=tk.LEFT, padx=10, pady=10)
        self.button_3.grid(row=2, column=1)

        self.button_4 = tk.Button(self.window, text="Image Request", command=self.send_image_request)
        #self.button_4.pack(side=tk.LEFT, padx=10, pady=10)
        self.button_4.grid(row=3, column=1)

        self.button_5 = tk.Button(self.window, text="Change sensor settings...", command=open_popup)
        #self.button_5.pack(side=tk.LEFT, padx=10, pady=10)
        self.button_5.grid(row=4, column=1)

        self.button_6 = tk.Button(self.window, text="Toggle UDP/Serial", command=self.toggle_udp_serial)
        #self.button_6.pack(side=tk.LEFT, padx=10, pady=10)
        self.button_6.grid(row=5, column=1)

        self.commModetext = tk.Text(self.window, width=15, height=1)
        self.commModetext.insert(1.0, "Using UDP")
        self.commModetext.config(state="disabled")
        #self.commModetext.pack(side=tk.BOTTOM, padx=10, pady=10)
        self.commModetext.grid(row=6, column=1)

        self.tele = tk.Text(self.window, width=30, height=6)
        self.tele.insert(1.0, "Waiting for telemetry")
        self.tele.config(state="disabled")
        #self.tele.pack(side=tk.BOTTOM, padx=10, pady=10)
        self.tele.grid(row=7, column=1)

        self.console_output = tk.Text(self.window, height=10, width=80, wrap="word")
        self.console_output.config(state="disabled")  
        #self.console_output.pack(side=tk.BOTTOM, padx=10, pady=10)
        self.console_output.grid(row=7, column=0, padx=10)

        sys.stdout = ConsoleRedirect(self.console_output)  # Redirect stdout to the text box
        #sys.stderr = ConsoleRedirect(self.console_output)  # Redirect stderr to the text box

        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Initialize connection
        # Attempt to initialize UDP
        self.sock = None
        try:
            self.sock = udp_start()
            self.data, self.addr = self.sock.recvfrom(4096)
            print(self.addr)
        except OSError as e:
            self.log_to_file(f"Error creating UDP socket: {e}")

        
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
                self.commModetext = tk.Text(self.window, width=15, height=1)
                self.commModetext.insert(1.0, "Using Serial")
                self.commModetext.config(state="disabled")
                self.commModetext.pack(side=tk.BOTTOM, padx=10, pady=10)
                
        except serial.SerialException as e:
            print(f"Error opening serial port: {e}")
            self.ser = None
        
        self.frame_queue = queue.Queue() # Queue to hold frames for processing - maxsize prevents memory overflow

        self.processor_thread = threading.Thread(target=self.update_image, daemon=True)
        self.processor_thread.start()

    def update_image(self):
    # Start timeout timer here?

        # Fill all values with NaN as placeholder
        self.frame = np.zeros((IMAGE_HEIGHT, IMAGE_WIDTH), dtype=np.int32) 
        # Tracker array for if corresponding row in frame is filled
        self.rowsFilled = np.ndarray((IMAGE_HEIGHT), dtype=bool)
        self.rowsFilled.fill(False)

        

    
        while (True): 
            #time.sleep(0.2)
            
            dataHex = None
           
            # Transmitting UDP
            if (self.transmission_udp and self.sock != None):
                try: 
                    self.data, self.addr = self.sock.recvfrom(4096)
                except:
                    # This should only run when socket is closed by main thread in on_closing
                    print("No socket detected, expecting GUI to close")
                    time.sleep(2) # Delay loop from restarting and printing the above again
                dataHex = self.data.hex()
                # Print raw bytes of received packet for diagnostic
                print("UDP: " + dataHex)
            # Transmitting Serial
            elif(not self.transmission_udp and self.ser.is_open):
                
                out = b""
                while (self.ser.inWaiting() > 0):
                    out += self.ser.read(1)
                if (out != b""):
                    print("Serial: " + out) 
                continue
            # Not transmitting
            else:
                continue

            #self.sock.sendto(int("CC0F", 16).to_bytes(2), addr)
            #if (int(self.data) > 0):
            
            #out = b""
            #while (self.ser.inWaiting() > 0):
            #    out += self.ser.read(1)
            #print(out) 
            
            

            # Eventually, want each bit of telemetry to have its own box rather than putting it all in one box
            # Also, be able to log commands and telemetry
            if (dataHex != None):
                header = dataHex[0:2]
                if (header.casefold() == SIG_IMAGE_DATA.casefold()):
                    if (len(dataHex) == 8 + IMAGE_DATA_LENGTH): # Length of an image data packet - normally 6144+8
                        
                        rowIndex = int(dataHex[2:6], 16)
                        print("Detected image packet for row", rowIndex)

                        # Convert hex string to 12-bit integers, 3 hex digits per integer
                        imageData = dataHex[6:(6 + IMAGE_DATA_LENGTH)]
                        #padding = (3 - len(imageData) % 3) % 3 # This and next line may not be neccessary if correct length is always sent - replace with error if incorect length?
                        #imageData = '0' * padding + imageData

                        #self.frame[rowIndex] = [int(imageData[i:i+3], 16) for i in range(0, len(imageData), 3)]
                        for i in range(0, len(imageData), 3):
                            self.frame[rowIndex, i // 3] = int(imageData[i:i+3], 16)
                        
                        self.rowsFilled[rowIndex] = True 

                        # Replace this with if (True) to test without full data
                        if (True):
                        #if (np.all(self.rowsFilled)): # If all rows are filled, display the frame

                            print("Updating image:")
                            # Reset rowsFilled to all false
                            self.rowsFilled.fill(False)
                        
                            # Display video frame here

                            #print(self.frame[0:15, 0:15])

                            #self.frame[400:500, 400:500] = 4000

                            # Downscale to 1/4 size for display
                            frameResized = cv2.resize(self.frame, (IMAGE_WIDTH//4, IMAGE_HEIGHT//4), interpolation=cv2.INTER_NEAREST)

                            normalized = (frameResized / 4095.0 * 255).astype(np.uint8)

                            pil_image = ImageTk.PhotoImage(image=Image.fromarray(normalized, mode='L')) # L = grayscale

                            # Check over these lines
                            self.mainImage.create_image(0, 0, anchor=tk.NW, image=pil_image)
                            self.mainImage.image = pil_image

                            
                        #rowsFilled = np.fill(IMAGE_HEIGHT, False) 
                    elif (len(dataHex) == 20): # Length of an image start packet
                        self.log_to_file("Received image start packet")
                    elif (len(dataHex) == 28): # Length of an image end packet
                        self.log_to_file("Received image end packet")
                        # Create "process telemetry" function to simplfy code?

                elif (header.casefold() == SIG_TELEMETRY.casefold()):
                    currTelemetry = Telemetry.from_hex(dataHex)
                   
                    self.tele.config(state="normal")
                    self.tele.delete(1.0, tk.END) # clears entire text box at once
                    
                    # Print telemetry data to GUI
                    self.tele.insert("1.0", currTelemetry.state)
                    self.tele.insert("end", f"\nTemperature 1: {currTelemetry.temp1} C")
                    self.tele.insert("end", f"\nTemperature 2: {currTelemetry.temp2} C")
                    self.tele.insert("end", f"\nVoltage: {currTelemetry.voltage} V")
                    self.tele.insert("end", f"\nFault code: {currTelemetry.fault_code}")

                    self.tele.config(state="disabled")

                    self.log_to_file("Received telemetry", currTelemetry)
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
                rowsFilled[latestRowPacket.rowIndex] = True 
                if (np.all(rowsFilled)): # If all rows are filled, display the frame
                    # Display video frame here
                    #update_image()
                    
                rowsFilled = np.fill(IMAGE_HEIGHT, False) 
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
                self.commModetext.config(state="normal")
                self.commModetext.delete(1.0, tk.END)
                self.commModetext.insert(1.0, "Using Serial")
                self.commModetext.config(state="disabled")

            except serial.SerialException as e:
                print(f"Error opening serial port: {e}")
            
            
            
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
                self.commModetext.config(state="normal")
                self.commModetext.delete(1.0, tk.END)
                self.commModetext.insert(1.0, "Using UDP")
                self.commModetext.config(state="disabled")
                self.ser.close()
            except:
                print("Error creating UDP socket")
            

    # Custom functions for each button
    def send_reset(self):
        if (self.transmission_udp):
            self.sock.sendto(int(CMD_RESET, 16).to_bytes(2), self.addr)
        elif (self.ser.is_open):
            self.ser.write(str.encode(CMD_RESET))
        
        self.log_to_file("Sent reset")

    def send_abort(self):
        if (self.transmission_udp):
            self.sock.sendto(int(CMD_ABORT, 16).to_bytes(2), self.addr)
        elif (self.ser.is_open):
            self.ser.write(str.encode(CMD_ABORT))
        
        self.log_to_file("Sent abort")

    def send_enter_image_collection(self):
        if (self.transmission_udp):
            self.sock.sendto(int(CMD_P_IMAGE_ENABLE, 16).to_bytes(2), self.addr)
            # add unix timecode: self.sock.sendto(int(CMD_P_IMAGE_ENABLE + self.get_unix_time_hex(), 16).to_bytes(10), self.addr)
        elif (self.ser.is_open):
            self.ser.write(str.encode(CMD_P_IMAGE_ENABLE) + str.encode(self.get_unix_time_hex()))
        
        self.log_to_file("Sent enter image collection mode")

    def send_image_request(self):
        if (self.transmission_udp):
            self.sock.sendto(int(CMD_IMAGE_REQUEST, 16).to_bytes(2), self.addr)
        elif (self.ser.is_open):
            self.ser.write(str.encode(CMD_IMAGE_REQUEST))
        
        self.log_to_file("Sent image request")

    def change_sensor_settings(spec1): #spec1 instead of self?
        # TODO
        print("Sensor setting changed to " + str(spec1))

    # Get Unix timestamp as 64-bit integer to sent with packets
    def get_unix_time_hex():
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
            print(message)
            writer = csv.writer(file)
            
            # Get the current timestamp
            timestamp = datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # Format: YYYY-MM-DD HH:MM:SS.mmm
            
            # Write the log entry
            if (telemetry == None):
                writer.writerow([timestamp, message])
            else:
                writer.writerow([timestamp, message, telemetry.state, telemetry.temp1, telemetry.temp2, telemetry.voltage, telemetry.fault_code])


    def on_closing(self):
        print("Closing GUI...")
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
    
