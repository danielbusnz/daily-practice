#!/usr/bin/env python3
"""Daily Practice helper: serves the practice page and runs Mac timers.

Runs at login via ~/Library/LaunchAgents/com.daniel.practicetimer.plist on
http://127.0.0.1:5910. Clicking a site on the page POSTs /start?group=...,
which starts a timer for that group (if one isn't already running) and shows
a macOS notification when it starts and an alert with a sound when it ends.
"""

import json
import os
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PORT = 5910
HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(HERE, "index.html")

# Edit minutes here; the page reads them from /status.
GROUPS = {
    "typing": {"label": "Typing", "minutes": 5},
    "vim": {"label": "Vim", "minutes": 5},
    "coding": {"label": "Coding", "minutes": 60},
    "math": {"label": "Math", "minutes": 60},
    "anki": {"label": "Flashcards", "minutes": 15},
    "chess": {"label": "Chess", "minutes": 30},
}

# Mac apps the page can open (they have no web link).
APPS = {"anki": "Anki"}

# The Jobs button opens a Claude Code session in Terminal that runs the handshake skill
# (~/.claude/skills/handshake): an agent builds the shortlist, then you pick what to apply to.
CLAUDE = os.path.expanduser("~/.local/bin/claude")
PROJECT = os.path.dirname(HERE)
HANDSHAKE_PROMPT = "/handshake Build a fresh SWE internship and new-grad shortlist, pre-select every resume-only Handshake role, and ask me once to submit them all."

STATE = os.path.join(HERE, "timers.json")  # running timers, so restarts and reboots keep them

timers = {}  # group -> {"end": epoch seconds, "cancel": threading.Event}
lock = threading.Lock()


def persist():
    # Call with lock held.
    with open(STATE, "w") as f:
        json.dump({k: t["end"] for k, t in timers.items()}, f)


def osascript(script):
    subprocess.Popen(["osascript", "-e", script],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def notify(title, text):
    osascript(f'display notification "{text}" with title "{title}" sound name "Glass"')


def finish(group):
    g = GROUPS[group]
    subprocess.Popen(["afplay", "/System/Library/Sounds/Glass.aiff"])
    osascript(
        f'display alert "{g["label"]} time is up" '
        f'message "{g["minutes"]} minutes done." giving up after 600'
    )


def run_timer(group, end, cancel):
    if not cancel.wait(max(0, end - time.time())):
        finish(group)
    with lock:
        if timers.get(group, {}).get("cancel") is cancel:
            del timers[group]
            persist()


def launch(group, end):
    # Call with lock held.
    cancel = threading.Event()
    timers[group] = {"end": end, "cancel": cancel}
    persist()
    threading.Thread(target=run_timer, args=(group, end, cancel), daemon=True).start()


def start(group):
    with lock:
        if group in timers:
            return False
        g = GROUPS[group]
        launch(group, time.time() + g["minutes"] * 60)
    notify("Practice timer started", f'{g["label"]}: {g["minutes"]} minutes')
    return True


def restore():
    # Resume timers saved before a restart. One that ended in the last 10 minutes fires now;
    # older ones (say, from before an overnight shutdown) are dropped.
    try:
        with open(STATE) as f:
            saved = json.load(f)
    except (OSError, ValueError):
        return
    with lock:
        for group, end in saved.items():
            if group in GROUPS and end > time.time() - 600:
                launch(group, end)
        persist()


def stop(group):
    with lock:
        t = timers.pop(group, None)
        persist()
    if t:
        t["cancel"].set()
    return bool(t)


def status():
    now = time.time()
    with lock:
        return {
            k: {
                "label": g["label"],
                "minutes": g["minutes"],
                "remaining": max(0, int(timers[k]["end"] - now)) if k in timers else None,
            }
            for k, g in GROUPS.items()
        }


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            with open(PAGE, "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")
        elif path == "/status":
            self._send(200, status())
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/open":
            app = parse_qs(u.query).get("app", [""])[0]
            if app not in APPS:
                return self._send(400, {"error": f"unknown app {app!r}"})
            subprocess.Popen(["open", "-a", APPS[app]])
            return self._send(200, {"opened": APPS[app]})
        if u.path == "/handshake":
            cmd = f"cd '{PROJECT}' && '{CLAUDE}' --chrome '{HANDSHAKE_PROMPT}'"
            osascript(f'tell application "Terminal"\nactivate\ndo script "{cmd}"\nend tell')
            return self._send(200, {"opened": "handshake"})
        group = parse_qs(u.query).get("group", [""])[0]
        if group not in GROUPS:
            return self._send(400, {"error": f"unknown group {group!r}"})
        if u.path == "/start":
            started = start(group)
        elif u.path == "/stop":
            started = not stop(group)
        else:
            return self._send(404, {"error": "not found"})
        self._send(200, {"started": started, "status": status()})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    restore()
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
