import os

def read_env(key):
    env = os.environ
    return env.get(key)
