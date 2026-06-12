"""A small flask-style legacy app — the lift target for example 1.

Deliberately effect-rich: network, filesystem cache, env config, clock,
randomness, logging, and one dynamic-dispatch trap.
"""

import json
import logging
import os
import random
import time
from pathlib import Path

import requests

CACHE_DIR = Path("./cache")
API_BASE = "https://api.example.com/v2"
log = logging.getLogger("webapp")


def get_config(key, default=None):
    return os.environ.get(f"WEBAPP_{key.upper()}", default)


def cache_path(name):
    return CACHE_DIR / f"{name}.json"


def read_cache(name, ttl_seconds=86400):
    p = cache_path(name)
    if not p.exists():
        return None
    age = time.time() - p.stat().st_mtime
    if age > ttl_seconds:
        return None
    return json.loads(p.read_text())


def write_cache(name, payload):
    CACHE_DIR.mkdir(exist_ok=True)
    cache_path(name).write_text(json.dumps(payload))


def fetch_user(user_id):
    cached = read_cache(f"user-{user_id}")
    if cached is not None:
        return cached
    r = requests.get(f"{API_BASE}/users/{user_id}", timeout=10)
    r.raise_for_status()
    data = r.json()
    write_cache(f"user-{user_id}", data)
    return data


def fetch_orders(user_id, since):
    r = requests.get(f"{API_BASE}/orders", params={"user": user_id, "since": since})
    r.raise_for_status()
    return r.json()["orders"]


def order_totals(orders):
    totals = {}
    for o in orders:
        totals[o["currency"]] = totals.get(o["currency"], 0) + o["amount"]
    return totals


def format_money(amount, currency):
    return f"{amount / 100:.2f} {currency}"


def jitter_sleep(attempt):
    delay = min(30.0, (2**attempt) + random.random())
    time.sleep(delay)
    return delay


def retry(fn, attempts=3):
    last = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — legacy code
            log.warning("attempt %s failed: %s", i, exc)
            last = exc
            jitter_sleep(i)
    raise last


def handler_for(event):
    name = f"handle_{event['type']}"
    return globals().get(name) or (lambda e: log.info("unhandled: %s", e))


def handle_order_created(event):
    user = fetch_user(event["user_id"])
    log.info("order for %s", user["name"])
    return order_totals(fetch_orders(event["user_id"], event["since"]))


def dispatch(event):
    return handler_for(event)(event)


def health():
    return {"ok": True, "ts": time.time(), "env": get_config("env", "dev")}
