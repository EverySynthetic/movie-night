#!/usr/bin/env python3
"""live: movie night for a film that only exists on a streaming service (or anything playing on this machine).
Listens to the audio of whatever is playing (the default sink's monitor, via PulseAudio/PipeWire `parec`), and every --seg seconds
turns it into a card: what was said (faster-whisper) and what the music is doing (librosa), plus the latest picture from `eye`
and anything the host typed on the couch page. Guests (any local chat models) react in a sentence or two, or pass.
Dry by default: with no guests configured/selected nobody is contacted.
  python -m movie_night.live [--seg 20] [--guests a,b,c] [--break-guests x,y] [--break-minutes 25] [--every 3]"""
import argparse, asyncio, json, os, re, subprocess, sys, tempfile, time
import numpy as np, librosa
from faster_whisper import WhisperModel
from .common import load_config, post, recent
from . import guests as G


def listen(sec, sink=None):
    sink = sink or subprocess.run(["pactl", "get-default-sink"], capture_output=True, text=True).stdout.strip()
    raw = tempfile.mktemp(suffix=".raw")
    with open(raw, "wb") as f:          # to a file, not a pipe: a pipe fills in ~1.5 s and parec blocks
        p = subprocess.Popen(["parec", "-d", sink + ".monitor", "--rate=22050", "--channels=1", "--format=s16le", "--latency-msec=50"],
                             stdout=f, stderr=subprocess.DEVNULL, start_new_session=True)
        time.sleep(sec); p.send_signal(2)
        try: p.wait(timeout=5)
        except Exception: p.kill()
    y = np.fromfile(raw, dtype=np.int16).astype(np.float32) / 32768.0
    os.remove(raw); return y


NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
MAJ = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MIN = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def music_words(y, sr=22050):
    """A plain-words estimate from signal analysis. It describes the sound; it does not hear it."""
    if len(y) < sr * 2 or np.abs(y).max() < 0.002:
        return "silence"
    bits = []
    tempo = float(np.atleast_1d(librosa.beat.beat_track(y=y, sr=sr)[0])[0])
    if tempo > 40: bits.append(f"a pulse of about {tempo:.0f} beats a minute")
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr).mean(axis=1)
    best = max(((np.corrcoef(chroma, np.roll(p, k))[0, 1], k, n) for p, n in ((MAJ, "major"), (MIN, "minor")) for k in range(12)))
    if best[0] > 0.6: bits.append(f"in {NOTES[best[1]]} {best[2]}")
    cent = float(librosa.feature.spectral_centroid(y=y, sr=sr).mean())
    bits.append("dark in tone" if cent < 1500 else "bright in tone")
    rms = librosa.feature.rms(y=y)[0]
    if (librosa.amplitude_to_db(rms, ref=np.max(rms)) < -45).mean() > 0.4: bits.append("mostly quiet")
    return "music: " + ", ".join(bits)


def host_notes(since):
    out = [r["text"] for r in recent("don", since)] + [r["text"] for r in recent("host", since)]
    pic = [r["text"] for r in recent("picture", since)]
    return " / ".join(out + pic[-1:])


async def react(g, card):
    msg = G.PROMPT.format(host=card["host"], minutes=card["minutes"], screen=card["screen"], said=card["said"], music=card["music"])
    return await asyncio.get_running_loop().run_in_executor(None, G.chat, g, msg, card["hist"])


async def interval(cfg, names, digest, hist):
    """Heavy guests join at breaks, one after another, never live."""
    for n in names:
        g = cfg["guests"][n]
        try:
            out = await asyncio.get_running_loop().run_in_executor(None, G.chat, g, G.BREAK.format(host=cfg.get("host_name", "the host"), digest=digest), hist.get(n))
            if out: post("guest", n, out); hist.setdefault(n, []).append({"role": "assistant", "content": out})
        except Exception as e: post("note", n, f"(could not join the break: {type(e).__name__})")
        finally: G.evict(g)


async def main():
    a = argparse.ArgumentParser(); a.add_argument("--seg", type=int, default=20); a.add_argument("--guests", default=""); a.add_argument("--break-guests", default="")
    a.add_argument("--break-minutes", type=float, default=25); a.add_argument("--every", type=int, default=3, help="one guest reacts per card, in turn, when every=N")
    a.add_argument("--language", default="en"); a = a.parse_args()
    cfg = load_config(); live = [g for g in a.guests.split(",") if g]; brk = [g for g in a.break_guests.split(",") if g]
    whisper = WhisperModel("small.en" if a.language == "en" else "small", device="cpu", compute_type="int8")
    t0 = last = time.time(); i = 0; hist = {g: [] for g in live}; bhist = {}; recent_cards = []; next_break = time.time() + a.break_minutes * 60; lastkey = None
    post("system", "couch", f"Live movie night. Guests on the couch: {', '.join(live) or 'none (dry run)'}.")
    loop = asyncio.get_running_loop()
    while True:
        y = await loop.run_in_executor(None, listen, a.seg)
        if len(y) < 2205: post("note", "couch", "(heard nothing: is the film playing and the volume up?)"); continue
        y16 = librosa.resample(y, orig_sr=22050, target_sr=16000)
        segs, _ = whisper.transcribe(y16, vad_filter=True, beam_size=1, **({} if a.language == "en" else {"task": "translate", "language": a.language}))
        said = " ".join(s.text.strip() for s in segs).strip()
        if said.lower().strip(" .!?,") in {"you", "thank you", "thanks for watching", "bye", "so", "uh", "um", "the"} or len(said) < 3: said = ""
        music = music_words(y); key = re.sub(r"a pulse of about \d+ beats a minute, ", "", music); changed = key != lastkey; lastkey = key
        screen = (host_notes(last) or "nothing described yet").replace("Picture: ", ""); last = time.time()
        card = {"host": cfg.get("host_name", "the host"), "minutes": int((time.time() - t0) // 60), "said": said or "no dialogue",
                "music": music if changed else "unchanged, the same music continues", "screen": screen}
        post("card", "film", (f"On screen: {screen}  " if screen != "nothing described yet" else "") + (f"Said: “{said}”  " if said else "") + f"[{card['music']}]", time.time() - t0)
        recent_cards.append((screen + " | " if screen != "nothing described yet" else "") + (f"said: {said}" if said else ""))
        if brk and time.time() >= next_break:
            asyncio.create_task(interval(cfg, brk, " / ".join(recent_cards[-8:])[:1800], bhist)); next_break = time.time() + a.break_minutes * 60; recent_cards = []
        for j, name in enumerate(live):
            if (i + j) % a.every: continue
            async def one(name=name, card=dict(card)):
                try:
                    out = await react(cfg["guests"][name], {**card, "hist": hist[name]})
                    if out: post("guest", name, out); hist[name] += [{"role": "user", "content": card["said"]}, {"role": "assistant", "content": out}]
                except Exception as e: post("note", name, f"(could not react: {type(e).__name__})")
            asyncio.create_task(one())
        i += 1


if __name__ == "__main__":
    asyncio.run(main())
