def count_lines(path):
    with open(path) as fh:
        return sum(1 for _ in fh)
