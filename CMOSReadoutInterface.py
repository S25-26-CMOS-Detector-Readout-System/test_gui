# CMOSReadoutInterface.py
# This file provides a software interface for the CMOS Readout System.

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

from enum import Enum

class PacketType(Enum):
    """Enum for packet types."""
    TYPE_INVALID = 0
    # Rx types
    TYPE_IMAGE_ENABLE = 1
    TYPE_IMAGE_REQUEST = 2
    TYPE_RESET = 3
    TYPE_ABORT = 4
    TYPE_CMOS_SETTING = 5
    TYPE_GET_CMOS=6
    TYPE_FLASH_WRITE = 7
    # Tx types
    TYPE_ACK = 8
    TYPE_IMAGE_START = 9
    TYPE_IMAGE_DATA = 10
    TYPE_IMAGE_END = 11
    TYPE_TELEMETRY = 12



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
# Get CMOS Setting
CMD_P_GET_CMOS = "AA78"
CMD_WRITE_FLASH = "FFFF"

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

PKTS_PER_ROW = 4
#IMAGE_DATA_LENGTH = (IMAGE_WIDTH * 3 // PKTS_PER_ROW) # Length of data part of image row packet in bytes, no header or leader - normally 6144, depends on row length

class Packet:
    """
    Class representing all types of packet, with fields for type and data fields.
    The data type in each field may depend on the packet type. For example, a TYPE_IMAGE_DATA packet has field "data1" as a 2D numpy array of the scaled-down image
    """
    def __init__(self, type, data1=None, data2=None, data3=None, data4=None):
        self.type = type
        self.data1 = data1
        self.data2 = data2
        self.data3 = data3
        self.data4 = data4
        
class Telemetry:
    """Class representing telemetry data."""
    def __init__(self, state="", temp1=0.0, temp2=0.0, voltage=0.0, fault_code=-1):
        self.state = state
        self.temp1 = temp1
        self.temp2 = temp2 
        self.voltage = voltage
        self.fault_code = fault_code

    @staticmethod
    def from_hex(hex_str):
        """Convert a hex string from a telemetry packet to a Telemetry object."""
        if len(hex_str) != 24:
            print("Telemetry hex string has incorrect length")
        
        # Function assumes system header (0x33) occupies position 0:2 of hex_str
        state = "Standby mode" if (hex_str[2:4].casefold() == "0F".casefold()) else "Image collection mode" if (hex_str[2:4].casefold() == "F0".casefold()) else "Invalid mode"
        temp1 = float(int(hex_str[4:8], 16)) # Adjust this depending on how values are formatted in hex
        temp2 = float(int(hex_str[8:12], 16))
        voltage = float(int(hex_str[12:16], 16))
        faultCode = int(hex_str[16:24], 16)
        
        return Telemetry(state, temp1, temp2, voltage, faultCode)
    
class CMOSReadoutInterface:
    """Main interface class for CMOS readout operations."""

    def __init__(self, image_height, image_width, socket=None, serial_port=None, transmission_udp=True, enable_save_images=False, image_save_dir = None):
        self.image_height = image_height
        self.image_width = image_width
        self.socket = socket # UDP socket to transmit to
        self.serial_port = serial_port # Serial port, alternate communication method
        self.transmission_udp = transmission_udp # True if using UDP, false if using serial
        self.enable_save_images = enable_save_images # True if images should be saved to disk
        self.image_save_dir = image_save_dir # Directory to save images to, if desired

        self.latest_packet = Packet(PacketType.TYPE_INVALID) # Latest packet received from PCB

        # Image frame built up as packets are received
        self._frame = np.zeros((self.image_height, self.image_width), dtype=np.int32) 

        # Tracker array for if corresponding row+section in frame is filled
        self._rows_filled = np.ndarray((self.image_height, PKTS_PER_ROW), dtype=bool)
        self._rows_filled.fill(False)


    
    def getPacket(self):
        """Receive a packet from the PCB"""
        # Receiving UDP
        if (self.transmission_udp and self.socket != None):
            try: 
                data, addr = self.socket.recvfrom(4096)
            except:
                print("No socket detected, expecting GUI to close")
                time.sleep(2) # Delay loop from restarting and printing the above again
            data_hex = data.hex()
            # Print raw bytes of received packet for diagnostic 
            #print("UDP: " + data_hex)
        # Receiving Serial
        elif (not self.transmission_udp and self.serial_port.is_open):
            out = b""
            while (self.serial_port.inWaiting() > 0):
                out += self.serial_port.read(1)
            if (out != b""):
                print("Serial: " + out) 
            pass
        # Not receiving either
        else:
            pass
       

        # Raw hex data received from socket, as a string   
        data_hex = None
        
    
        if (data_hex != None and len(data_hex) > 0):
            header = data_hex[0:2]
            if (header.casefold() == SIG_IMAGE_DATA.casefold()):
                # if (len(data_hex) > 6144 + 8): # Length of an image data packet (may need to update) 
                if (len(data_hex) > 1000): 
                    # Received packet is of image row/section data

                    rowIndex = int(data_hex[2:6], 16)
                    colIndex = int(data_hex[6:8], 16)
                    #print("Detected image packet for row", rowIndex)

                    #if (rowIndex >= IMAGE_HEIGHT):
                    #    continue

                    # Convert hex string to 12-bit integers, 3 hex digits per integer
                    #imageData = data_hex[8:(8 + IMAGE_DATA_LENGTH)]
                    imageData = data_hex[8:(8 + (self.image_width * 3 // PKTS_PER_ROW))]

                    #padding = (3 - len(imageData) % 3) % 3 # This and next line may not be neccessary if correct length is always sent - replace with error if incorect length?
                    #imageData = '0' * padding + imageData

                    #self._frame[rowIndex] = [int(imageData[i:i+3], 16) for i in range(0, len(imageData), 3)]
                    for i in range(0, len(imageData), 3):
                        self._frame[rowIndex, (i // 3) + (colIndex * self.image_width // 4)] = int(imageData[i:i+3], 16)
                    
                    self._rows_filled[rowIndex, colIndex] = True 

                    
                            
                elif (data_hex[0:4].casefold() == SIG_IMAGE_START.casefold()): # Length of an image start packet
                    self.log_to_file("Received image start packet")
                elif (data_hex[0:4].casefold() == SIG_IMAGE_END.casefold()): # Length of an image end packet
                    self.log_to_file("Received image end packet")

                    # Optional: Report completion of image frame to GUI
                    #percent_filled = np.count_nonzero(self._rows_filled) / self._rows_filled.size * 100
                    #self.log_to_file(f"Frame completion: {percent_filled:.1f}%")
                    
                    # Reset rows_filled to all false
                    self._rows_filled.fill(False)

                    # Reset frame to all zeros
                    self._frame = np.zeros((self.image_height, self.image_width), dtype=np.int32) 
            
                    
                    # Downscale to 1/4 size for display
                    frameResized = cv2.resize(self._frame, (self.image_width//4, self.image_height//4), interpolation=cv2.INTER_NEAREST) 
                    normalized_8 = (frameResized / 4095.0 * 255).astype(np.uint8)


                    if (self.enable_save_images):
                        # Save non-scaled image to disk
                        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = os.path.join(self.image_save_dir, f"image_{timestamp}.png")
                        normalized_16 = (self._frame * (65535.0/4095)).astype(np.uint16) # Convert to 16-bit for saving
                        cv2.imwrite(filename, normalized_16)
                        self.log_to_file(f"Saved image to {filename}")

                    return Packet(type=PacketType.TYPE_IMAGE_DATA, data1=normalized_8)
                # Create "process telemetry" function to simplfy code?

            elif (header.casefold() == SIG_TELEMETRY.casefold()):
                curr_telemetry = Telemetry.from_hex(data_hex)
                
                return Packet(Type=PacketType.TYPE_TELEMETRY, data1=curr_telemetry)

                self.log_to_file("Received telemetry", curr_telemetry)

            elif (header.casefold() == SIG_ACK.casefold()):
                self.log_to_file("Received ACK")

    def sendPacket(self, Packet):
        """Send a Packet to the PCB."""
        if (self.transmission_udp and self.socket != None):
            # Convert packet to hex string
            packet_hex = Packet.type.value + Packet.data1 + Packet.data2 + Packet.data3 + Packet.data4
            # Send packet over UDP
            self.sock.sendto(int(packet_hex, 16).to_bytes(len(packet_hex) // 2), self.addr)
        elif (not self.transmission_udp and self.ser.is_open):
            # Convert packet to hex string
            packet_hex = Packet.type.value + Packet.data1 + Packet.data2 + Packet.data3 + Packet.data4
            # Send packet over serial
            self.ser.write(bytes.fromhex(packet_hex))
        else:
            print("No connection detected, unable to send packet")


    def log_to_file(self, message, telemetry=None):
        """
        Log events such as packet reception and sending, optionally including telemtry data, to a CSV file.
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

   

# Get Unix timestamp as 64-bit integer to sent with packets
    def get_unix_time_hex(self):
        timestamp = int(time.time())
        # Convert to 16-character hex string, removing '0x' prefix
        return format(timestamp, '016x')
    
