"""Demo module: a plausible slice of a price-fetching service."""
import requests, json, random
from pathlib import Path

CACHE = Path("./cache")

def fetch_prices(tickers, start, end):
    """Pull daily OHLCV from the API, with a local cache."""
    out = {}
    for t in tickers:
        p = CACHE / f"{t}.json"
        if p.exists():
            out[t] = json.loads(p.read_text())
        else:
            r = requests.get(f"https://api.example.com/v2/bars/{t}",
                             params={"start": start, "end": end})
            r.raise_for_status()
            out[t] = r.json()
            p.write_text(json.dumps(out[t]))
    return out

def dedupe(xs):
    """Order-preserving dedupe."""
    seen = set()
    result = []
    for x in xs:
        if x not in seen:
            seen.add(x)
            result.append(x)
    return result

def moving_average(values, window: int) -> list:
    return [sum(values[i:i+window]) / window
            for i in range(len(values) - window + 1)]

def jitter_backoff(attempt: int) -> float:
    return min(60.0, (2 ** attempt) + random.random())
