import socket
import struct

def create_raw_socket(interface):
    """
    Create a raw socket for sending and receiving Ethernet frames.
    :param interface: The Ethernet interface to bind to (e.g., "eth0").
    :return: Configured raw socket.
    """
    try:
        # Create a raw socket
        raw_socket = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(0x0003))
        
        # Bind the socket to the specified interface
        raw_socket.bind((interface, 0))
        return raw_socket
    except PermissionError:
        print("Permission denied: Run the script with elevated privileges.")
        exit(1)
    except Exception as e:
        print(f"Error creating raw socket: {e}")
        exit(1)

def send_bytes(raw_socket, interface, destination_mac, payload):
    """
    Send a sequence of bytes as an Ethernet frame.
    :param raw_socket: The raw socket object.
    :param interface: The Ethernet interface to send the frame from.
    :param destination_mac: The destination MAC address as a string (e.g., "FF:FF:FF:FF:FF:FF").
    :param payload: The data to send as a byte sequence.
    """
    try:
        # Parse the MAC address
        destination_mac_bytes = bytes.fromhex(destination_mac.replace(":", ""))
        source_mac_bytes = raw_socket.getsockname()[4]

        # Create an Ethernet frame (destination MAC + source MAC + Ethertype + payload)
        ethertype = b'\x08\x00'  # Example Ethertype for IPv4
        frame = destination_mac_bytes + source_mac_bytes + ethertype + payload
        
        # Send the frame
        raw_socket.send(frame)
        print(f"Sent {len(payload)} bytes to {destination_mac} on {interface}")
    except Exception as e:
        print(f"Error sending bytes: {e}")

def receive_bytes(raw_socket):
    """
    Receive a sequence of bytes from the Ethernet interface.
    :param raw_socket: The raw socket object.
    :return: The received data (including Ethernet headers).
    """
    try:
        # Receive data (with a buffer size of 65535 bytes)
        frame, addr = raw_socket.recvfrom(65535)
        print(f"Received {len(frame)} bytes from {addr}")
        return frame
    except Exception as e:
        print(f"Error receiving bytes: {e}")
        return None

"""
def main():
    # Ethernet interface to use
    interface = "eth0"  # Replace with the name of your Ethernet interface

    # Destination MAC address (example: broadcast address)
    destination_mac = "FF:FF:FF:FF:FF:FF"

    # Example payload data
    payload = b"Hello, Ethernet!"

    # Create a raw socket
    raw_socket = create_raw_socket(interface)

    # Send bytes
    send_bytes(raw_socket, interface, destination_mac, payload)

    # Receive bytes
    received_frame = receive_bytes(raw_socket)
    if received_frame:
        # Extract Ethernet header and payload
        destination_mac_received = received_frame[:6]
        source_mac_received = received_frame[6:12]
        ethertype_received = received_frame[12:14]
        payload_received = received_frame[14:]

        print(f"Destination MAC: {destination_mac_received.hex(':')}")
        print(f"Source MAC: {source_mac_received.hex(':')}")
        print(f"Ethertype: {ethertype_received.hex()}")
        print(f"Payload: {payload_received}")

    # Close the socket
    raw_socket.close()

"""
