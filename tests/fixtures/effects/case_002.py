import requests

def get_url(u):
    r = requests.get(u)
    return r.status_code
