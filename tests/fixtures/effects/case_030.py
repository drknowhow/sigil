import random
import requests

def fetch_with_jitter(url, path):
    delay = random.random()
    r = requests.get(url)
    with open(path, "w") as fh:
        fh.write(r.text)
    return delay
