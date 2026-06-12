import os

def config_exists(name):
    base = os.path.expanduser("~/.config")
    return os.path.exists(os.path.join(base, name))
