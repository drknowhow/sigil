from requests import get as fetch

def grab(url):
    return fetch(url).json()
