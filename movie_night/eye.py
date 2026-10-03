#!/usr/bin/env python3
"""eye: every N seconds grab the screen, have a vision model describe it, post the description as 'picture'.
Frames are deleted right after captioning; only the description is kept. Keep the film fullscreen.
  python -m movie_night.eye [--every 60] [--once]
Screen capture uses `spectacle` (KDE) by default; set "screenshot_cmd" in config.json for others (must write a PNG to {out}).
Streaming services may block capture of their video; if the frame is black the eye says so."""
import argparse, base64, io, json, os, subprocess, tempfile, time, urllib.request
from PIL import Image, ImageStat
from .common import load_config, post

ASK = ("This is a frame from a film being watched in a browser. Ignore the browser, tabs, player controls and any text overlays. "
       "In two plain sentences say what is happening in the film: who or what is on screen, what they are doing, the setting and mood. "
       "If the screen is clearly not a film (a desktop, a document, a chat), say only: NOT A FILM.")


def grab(cfg):
    f = tempfile.mktemp(suffix=".png")
    cmd = cfg.get("screenshot_cmd", "spectacle -b -n -f -o {out}").format(out=f)
    subprocess.run(cmd, shell=True, capture_output=True, timeout=30)
    im = Image.open(f).convert("RGB"); os.remove(f)
    return im


def caption(im, cfg):
    v = cfg["vision"]; buf = io.BytesIO(); im.save(buf, "JPEG", quality=80)
    body = {"model": v["model"], "stream": False, "think": False, "keep_alive": "20m", "options": {"temperature": 0.2, "num_predict": 300},
            "messages": [{"role": "user", "content": ASK, "images": [base64.b64encode(buf.getvalue()).decode()]}]}
    req = urllib.request.Request(v["host"].rstrip("/") + "/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)["message"]["content"].strip().replace("\n", " ")


def main():
    a = argparse.ArgumentParser(); a.add_argument("--every", type=int, default=60); a.add_argument("--once", action="store_true"); a = a.parse_args()
    cfg = load_config(); regions = cfg.get("screen_regions") or [None]; last = None
    while True:
        t = time.time(); text = None
        try:
            full = grab(cfg)
            order = sorted(range(len(regions)), key=lambda i: i != last)
            for i in order:
                r = regions[i]; im = full.crop((r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"])) if r else full.copy()
                im.thumbnail((1024, 1024))
                if ImageStat.Stat(im.convert("L")).mean[0] < 5: text = "(the picture is black or blocked)"; last = i; break
                c = caption(im, cfg)
                if c and not c.upper().startswith("NOT A FILM"): text = c; last = i; break
            if text: post("picture", "eye", text); print(text, flush=True)
            else: print("(not a film, skipped)", flush=True)
        except Exception as e:
            print("eye error:", type(e).__name__, str(e)[:100], flush=True)
        if a.once: break
        time.sleep(max(1, a.every - (time.time() - t)))


if __name__ == "__main__":
    main()
