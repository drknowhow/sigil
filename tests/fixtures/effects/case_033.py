def handler_for(name):
    return globals().get("handle_" + name)

def dispatch(name, event):
    return handler_for(name)(event)
