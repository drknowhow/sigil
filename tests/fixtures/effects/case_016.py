import random

def ping(n):
    if n <= 0:
        return random.random()
    return pong(n - 1)

def pong(n):
    return ping(n - 1)
