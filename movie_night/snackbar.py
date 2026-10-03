#!/usr/bin/env python3
"""snackbar: every few minutes put a small curiosity (popcorn) or a good word (candy) on the feed. Edit snacks.txt (kind|text).
  python -m movie_night.snackbar [--every 240]"""
import argparse, random, time
from pathlib import Path
from .common import post

def main():
    a = argparse.ArgumentParser(); a.add_argument("--every", type=int, default=240); a = a.parse_args()
    lines = [l.strip().split("|", 1) for l in open(Path(__file__).resolve().parent.parent / "snacks.txt") if "|" in l]; random.shuffle(lines)
    for kind, text in lines:
        time.sleep(a.every); post("snack", "snack bar", ("🍿 " if kind == "popcorn" else "🍬 ") + text)

if __name__ == "__main__":
    main()
