
import socket

# Create a UDP socket
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# Bind to address and port - port 50007 chosen as it is unused by other applications
# IP is static
server_socket.bind(('192.168.137.6', 50007))