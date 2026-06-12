import secrets

def token():
    return secrets.token_hex(16)
