"""Talk to a guest: any chat model served by an Ollama-compatible endpoint. A guest can pass by answering PASS."""
import json, subprocess, time, urllib.request

PROMPT = ("You are watching a film with {host} the way a person does on a couch. You cannot see or hear it; you are given a card of what is happening. "
          "React to the story and the people in it: what they say, what they are going through, what you feel about it. The music matters only if it truly changed. "
          "One or two plain sentences in your own voice, or say only PASS. No summary, no review. It is fine to say nothing. "
          "Jokes are welcome, like Mystery Science Theater 3000: riff if something is funny, but be kind to the film and to everyone on the couch.\n\n"
          "CARD (about {minutes} minutes in):\nOn screen: {screen}\nSaid: {said}\nMusic: {music}\n")

BREAK = ("It is the interval of a film {host} is watching with a few friends. You cannot see or hear it; here is what the last stretch was like:\n{digest}\n\n"
         "If you want, say a sentence or two about the story and the people in it, plainly, in your own voice. Do not describe the music and do not quote "
         "anyone unless it is in the digest above. Or say only PASS. No summary, no review.")


def chat(guest, message, history=None, timeout=300):
    """guest = {"host": "http://localhost:11434", "model": "...", "system": optional}"""
    msgs = ([{"role": "system", "content": guest["system"]}] if guest.get("system") else []) + (history or [])[-6:] + [{"role": "user", "content": message}]
    body = {"model": guest["model"], "stream": False, "messages": msgs, "keep_alive": guest.get("keep_alive", "30m")}
    req = urllib.request.Request(guest["host"].rstrip("/") + "/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = (json.load(r).get("message") or {}).get("content", "").strip()
    return None if (not out or out.upper().startswith("PASS")) else out


def evict(guest):
    """Optional: free a heavy guest's model after its turn. config: guest.evict_cmd, e.g. ssh box 'ollama stop MODEL'."""
    cmd = guest.get("evict_cmd")
    if cmd:
        subprocess.run(cmd, shell=True, capture_output=True, timeout=60)
        time.sleep(3)
