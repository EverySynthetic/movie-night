"""Shared config and helpers. Everything user-specific lives in config.json (see config.example.json)."""
import json, os, time
from pathlib import Path

HOME = Path(os.environ.get("MOVIE_NIGHT_HOME", Path.home() / ".movie-night"))
HOME.mkdir(parents=True, exist_ok=True)
FEED = HOME / "feed.jsonl"


def load_config():
    p = Path(os.environ.get("MOVIE_NIGHT_CONFIG", HOME / "config.json"))
    if not p.exists():
        raise SystemExit(f"No config at {p}. Copy config.example.json there and edit it.")
    return json.loads(p.read_text())


def post(kind, who, text, film_t=None):
    """Append one line to the shared feed that the couch page shows."""
    with FEED.open("a") as f:
        f.write(json.dumps({"ts": time.time(), "film_t": film_t, "kind": kind, "who": who, "text": text}) + "\n")


def recent(kind=None, since=0.0, n=80):
    if not FEED.exists():
        return []
    rows = [json.loads(l) for l in FEED.read_text().splitlines()[-n:]]
    return [r for r in rows if r["ts"] > since and (kind is None or r["kind"] == kind)]
