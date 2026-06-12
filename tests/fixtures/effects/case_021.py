import tempfile

def scratch(data):
    with tempfile.NamedTemporaryFile() as fh:
        fh.write(data)
        return fh.name
