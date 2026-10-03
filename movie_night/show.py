#!/usr/bin/env python3
"""show: play prepared scene cards on the film's clock. Start it at the same moment as the film.
  python -m movie_night.show SCENES.json [--guests a,b] [--speed 1] [--every 3]
Dry by default (no --guests: nobody is contacted)."""
import argparse, asyncio, json, time
from pathlib import Path
from .common import load_config, post
from . import guests as G


async def main():
    a = argparse.ArgumentParser(); a.add_argument("scenes"); a.add_argument("--guests", default=""); a.add_argument("--speed", type=float, default=1.0); a.add_argument("--every", type=int, default=3); a = a.parse_args()
    cfg = load_config(); S = json.load(open(a.scenes)); live = [g for g in a.guests.split(",") if g]; hist = {g: [] for g in live}; t0 = time.time()
    post("system", "couch", f"Movie night starting: {Path(S['video']).name}. Guests: {', '.join(live) or 'none (dry run)'}.")
    loop = asyncio.get_running_loop()
    for i, sc in enumerate(S["scenes"]):
        wait = sc["t0"] / a.speed - (time.time() - t0)
        if wait > 0: await asyncio.sleep(wait)
        post("card", "film", f"On screen: {sc['scene']}  " + (f"Said: “{sc['said']}”  " if sc["said"] else "") + f"[{sc['music']}]", sc["t0"])
        for j, name in enumerate(live):
            if (i + j) % a.every: continue
            msg = G.PROMPT.format(host=cfg.get("host_name", "the host"), minutes=int(sc["t0"] // 60), screen=sc["scene"], said=sc["said"] or "no dialogue", music=sc["music"])
            try: out = await loop.run_in_executor(None, G.chat, cfg["guests"][name], msg, hist[name])
            except Exception as e: post("note", name, f"(could not react: {type(e).__name__})"); continue
            if out: post("guest", name, out, sc["t0"]); hist[name] += [{"role": "user", "content": sc["scene"]}, {"role": "assistant", "content": out}]
    post("system", "couch", "The film is over.")


if __name__ == "__main__":
    asyncio.run(main())
