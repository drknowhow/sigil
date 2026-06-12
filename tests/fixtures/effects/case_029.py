def make_counter():
    n = 0
    def bump():
        nonlocal n
        n += 1
        return n
    return bump
