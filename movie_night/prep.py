#!/usr/bin/env python3
"""prep: turn a film FILE into scene cards ahead of time (picture via a vision model, dialogue via faster-whisper, music via librosa).
  python -m movie_night.prep FILM.mp4 [--seg 20] [--who "Name (description), Name (description)"]
Writes <MOVIE_NIGHT_HOME>/<film>/scenes.json; `python -m movie_night.show` plays it back on the film's clock."""
import argparse, base64, json, subprocess, sys, tempfile, urllib.request
from pathlib import Path
import librosa
from faster_whisper import WhisperModel
from .common import HOME, load_config
from .live import music_words


def duration(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip())


def frames(path, t0, t1, d, n=3):
    out = []
    for k in range(n):
        t = t0 + (t1 - t0) * (k + 0.5) / n; f = Path(d) / f"f_{int(t0)}_{k}.jpg"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", path, "-frames:v", "1", "-vf", "scale=640:-2", str(f)], check=True)
        out.append(base64.b64encode(f.read_bytes()).decode())
    return out


def caption(cfg, imgs, who):
    v = cfg["vision"]
    q = ("These are three frames from the same short moment of a film, in order. In two or three plain sentences, say what is happening: who or what is on screen, "
         "what they are doing, the setting, the mood. Say only what you can see." + (f" Characters, if relevant: {who}." if who else ""))
    body = {"model": v["model"], "stream": False, "think": False, "keep_alive": "10m", "options": {"temperature": 0.2, "num_predict": 300}, "messages": [{"role": "user", "images": imgs, "content": q}]}
    req = urllib.request.Request(v["host"].rstrip("/") + "/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)["message"]["content"].strip().replace("\n", " ")


def main():
    a = argparse.ArgumentParser(); a.add_argument("video"); a.add_argument("--seg", type=float, default=20.0); a.add_argument("--who", default=""); a = a.parse_args()
    cfg = load_config(); out = HOME / Path(a.video).stem; out.mkdir(exist_ok=True); d = tempfile.mkdtemp(); D = duration(a.video)
    has_audio = bool(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", a.video], capture_output=True, text=True).stdout.strip())
    whisper = WhisperModel("small.en", device="cpu", compute_type="int8"); scenes = []; t = 0.0; i = 0
    while t < D - 0.5:
        t1 = min(t + a.seg, D); music, said = "no soundtrack (silent film)", ""
        if has_audio:
            wav = Path(d) / f"a_{i}.wav"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-t", f"{t1-t:.2f}", "-i", a.video, "-ac", "1", "-ar", "22050", str(wav)], check=True)
            y, _ = librosa.load(str(wav), sr=22050); music = music_words(y)
            segs, _ = whisper.transcribe(librosa.load(str(wav), sr=16000)[0], vad_filter=True, beam_size=1); said = " ".join(s.text.strip() for s in segs).strip()
        imgs = frames(a.video, t, t1, d); cap = ""
        for _ in range(3):
            cap = caption(cfg, imgs, a.who)
            if cap: break
        scenes.append({"t0": round(t, 2), "t1": round(t1, 2), "scene": cap or "(no description came back)", "music": music, "said": said})
        print(f"[{int(t)//60:02d}:{int(t)%60:02d}] {cap[:90]}", flush=True); t = t1; i += 1
    json.dump({"video": str(Path(a.video).resolve()), "duration": D, "scenes": scenes}, open(out / "scenes.json", "w"), indent=1); print("wrote", out / "scenes.json", len(scenes), "scenes")


if __name__ == "__main__":
    main()
