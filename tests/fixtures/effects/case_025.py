import socket

def probe(host, port):
    s = socket.socket()
    s.connect((host, port))
    s.close()
