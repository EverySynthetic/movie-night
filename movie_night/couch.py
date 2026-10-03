#!/usr/bin/env python3
"""couch: the shared feed page. http://127.0.0.1:8099 (local only). The box at the bottom is the host talking to the room.
Other helpers can post with: curl -X POST -d "a line" http://127.0.0.1:8099/post/<name>
  python -m movie_night.couch"""
import http.server, json, socketserver, time, urllib.parse
from .common import FEED, load_config, post

PAGE = """<!doctype html><meta charset=utf-8><title>Movie night</title><body style="background:#14110e;color:#e8dcc8;font:17px/1.5 Georgia,serif;max-width:46em;margin:2em auto;padding:0 1em">
<h2 style="color:#e9b44c">Movie night</h2><div id=f></div><form onsubmit="say(event)" style="position:sticky;bottom:0;background:#14110e;padding:.6em 0"><input id=s placeholder="Say what you see, or anything..." style="width:80%;background:#221d17;color:#e8dcc8;border:1px solid #4a3f30;padding:.5em;font:inherit"> <button style="padding:.5em">send</button></form><script>
async function go(){const r=await fetch('/feed');const j=await r.json();const f=document.getElementById('f');const bottom=(innerHeight+scrollY)>=document.body.scrollHeight-80;
f.innerHTML=j.map(x=>{const c=x.kind=='guest'?'#e9b44c':x.kind=='helper'?'#c9a0dc':x.kind=='host'?'#e8dcc8':x.kind=='picture'?'#7f9fb8':x.kind=='card'?'#8fa9a0':'#a89f90';const t=x.film_t==null?'':Math.floor(x.film_t/60)+':'+String(Math.floor(x.film_t%60)).padStart(2,'0')+' ';
return `<p style="margin:.6em 0;color:${c}"><small>${t}</small><b>${x.kind=='card'?'':x.who+': '}</b>${x.text.replace(/</g,'&lt;')}</p>`}).join('');if(bottom)scrollTo(0,document.body.scrollHeight)}
async function say(e){e.preventDefault();const v=document.getElementById('s');if(!v.value)return;await fetch('/say',{method:'POST',body:v.value});v.value='';go()}
go();setInterval(go,3000)</script>"""


class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0)); t = self.rfile.read(n).decode("utf-8", "replace")[:600]
        kind, who = "host", "Host"
        if self.path.startswith("/post/"): kind, who = "helper", urllib.parse.unquote(self.path[6:])[:20] or "helper"
        post(kind, who, t); self.send_response(200); self.end_headers(); self.wfile.write(b"ok")

    def do_GET(self):
        if self.path == "/feed":
            rows = [json.loads(l) for l in FEED.read_text().splitlines()] if FEED.exists() else []
            b = json.dumps(rows[-400:]).encode(); self.send_response(200); self.send_header("Content-Type", "application/json")
        else:
            b = PAGE.encode(); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers(); self.wfile.write(b)

    def log_message(self, *a): pass


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    socketserver.TCPServer(("127.0.0.1", 8099), H).serve_forever()
