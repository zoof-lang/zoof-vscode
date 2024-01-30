"""
Run this to listen to the extension's logs, send via UDP.
"""

import socket


sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("127.0.0.1", 12012))

while True:
    data, addr = sock.recvfrom(2**20)
    print(data.decode())
