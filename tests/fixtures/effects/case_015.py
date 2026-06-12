def save(path, data):
    with open(path, "w") as fh:
        fh.write(data)

def save_all(items):
    for k, v in items.items():
        save(k, v)
