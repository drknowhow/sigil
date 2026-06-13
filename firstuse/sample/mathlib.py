"""Lifted-Python sample for v2 propose_contract / neutral-IR tests."""


def double(n):
    return n * 2


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x
