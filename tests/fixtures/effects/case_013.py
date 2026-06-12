def dispatch(obj, name):
    return getattr(obj, name)()
