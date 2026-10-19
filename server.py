#!/usr/bin/env python3
"""Daily Practice helper: serves the practice page and runs desktop timers (macOS or Linux).

Runs at login via ~/Library/LaunchAgents/com.daniel.practicetimer.plist (Mac) or
the practicetimer.service systemd user unit (Linux) on http://127.0.0.1:5910. Clicking a site on the page POSTs /start?group=...,
which starts a timer for that group (if one isn't already running) and shows
a notification when it starts and an alert with a sound when it ends. Each task
has a check mark for the day (POST /done?task=...&done=1|0), stored in done.json.
"""

import json
import os
import shutil
import subprocess
import sys
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

MAC = sys.platform == "darwin"

# Apps the page can open (they have no web link). Mac name -> Linux command
# (native binary if installed, otherwise the Flathub package).
APPS = {"anki": {"mac": "Anki",
                 "linux": ["anki"] if shutil.which("anki") else ["flatpak", "run", "net.ankiweb.Anki"]}}

# The Jobs button opens a Claude Code session in a terminal that runs the job-search skill:
# /handshake on the Mac (~/.claude/skills/handshake), /jobhunt on Linux (~/.claude/skills/jobhunt).
CLAUDE = os.path.expanduser("~/.local/bin/claude")
# Where the Claude session runs: the Mac skill lives with the practice page; the Linux one reads ~/job_search.
PROJECT = os.path.dirname(HERE) if MAC else os.path.expanduser("~/job_search")
HANDSHAKE_PROMPT = (
    "/handshake Build a fresh SWE internship and new-grad shortlist, pre-select every resume-only Handshake role, and ask me once to submit them all."
    if MAC else "/jobhunt"
)
LINUX_SOUND = "/usr/share/sounds/freedesktop/stereo/complete.oga"
LINUX_TERMINAL = next((t for t in ("kitty", "alacritty", "foot", "gnome-terminal", "konsole") if shutil.which(t)), None)

# Local files the page links to (served only if present on this machine).
FILES = {"/latex-cheatsheet.pdf": (os.path.expanduser("~/upenn/5920/latex-symbols-cheatsheet.pdf"), "application/pdf")}

STATE = os.path.join(HERE, "timers.json")  # running timers, so restarts and reboots keep them
DONE = os.path.join(HERE, "done.json")  # today's check marks; they reset each day
TASKS = ["jobs"] + list(GROUPS)

timers = {}  # group -> {"end": epoch seconds, "cancel": threading.Event}
lock = threading.Lock()


def persist():
    # Call with lock held.
    with open(STATE, "w") as f:
        json.dump({k: t["end"] for k, t in timers.items()}, f)


def quiet(cmd):
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


def osascript(script):
    quiet(["osascript", "-e", script])


def play_sound():
    if MAC:
        quiet(["afplay", "/System/Library/Sounds/Glass.aiff"])
    elif shutil.which("pw-play"):
        quiet(["pw-play", LINUX_SOUND])
    elif shutil.which("paplay"):
        quiet(["paplay", LINUX_SOUND])


def notify(title, text):
    if MAC:
        osascript(f'display notification "{text}" with title "{title}" sound name "Glass"')
    else:
        quiet(["notify-send", "-a", "Daily Practice", title, text])
        play_sound()


def finish(group):
    g = GROUPS[group]
    play_sound()
    title, text = f'{g["label"]} time is up', f'{g["minutes"]} minutes done.'
    if MAC:
        osascript(f'display alert "{title}" message "{text}" giving up after 600')
    else:
        quiet(["notify-send", "-a", "Daily Practice", "-u", "critical", title, text])
        if shutil.which("zenity"):
            quiet(["zenity", "--info", "--timeout=600", f"--title={title}", f"--text={text}"])


def open_app(app):
    if MAC:
        quiet(["open", "-a", APPS[app]["mac"]])
    else:
        quiet(APPS[app]["linux"])


def open_handshake():
    if MAC:
        cmd = f"cd '{PROJECT}' && '{CLAUDE}' --chrome '{HANDSHAKE_PROMPT}'"
        osascript(f'tell application "Terminal"\nactivate\ndo script "{cmd}"\nend tell')
    elif LINUX_TERMINAL:
        if LINUX_TERMINAL == "kitty":
            cmd = ["kitty", "--title", "Job hunt", "--directory", PROJECT, CLAUDE, "--chrome", HANDSHAKE_PROMPT]
        else:
            cmd = [LINUX_TERMINAL, "-e", CLAUDE, "--chrome", HANDSHAKE_PROMPT]
        subprocess.Popen(cmd, cwd=PROJECT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


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


def today():
    return time.strftime("%Y-%m-%d")


def load_done():
    # Call with lock held. Check marks from a previous day are dropped.
    try:
        with open(DONE) as f:
            saved = json.load(f)
        if saved.get("date") == today():
            return [t for t in saved.get("done", []) if t in TASKS]
    except (OSError, ValueError, AttributeError):
        pass
    return []


def set_done(task, done):
    with lock:
        marks = load_done()
        if done and task not in marks:
            marks.append(task)
        if not done and task in marks:
            marks.remove(task)
        with open(DONE, "w") as f:
            json.dump({"date": today(), "done": marks}, f)


def status():
    now = time.time()
    with lock:
        return {
            "date": today(),
            "groups": {
                k: {
                    "label": g["label"],
                    "minutes": g["minutes"],
                    "remaining": max(0, int(timers[k]["end"] - now)) if k in timers else None,
                }
                for k, g in GROUPS.items()
            },
            "done": {t: t in load_done() for t in TASKS},
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
        elif path in FILES and os.path.exists(FILES[path][0]):
            with open(FILES[path][0], "rb") as f:
                self._send(200, f.read(), FILES[path][1])
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/open":
            app = parse_qs(u.query).get("app", [""])[0]
            if app not in APPS:
                return self._send(400, {"error": f"unknown app {app!r}"})
            open_app(app)
            return self._send(200, {"opened": app})
        if u.path == "/handshake":
            open_handshake()
            return self._send(200, {"opened": "handshake"})
        if u.path == "/done":
            q = parse_qs(u.query)
            task = q.get("task", [""])[0]
            if task not in TASKS:
                return self._send(400, {"error": f"unknown task {task!r}"})
            set_done(task, q.get("done", ["1"])[0] == "1")
            return self._send(200, status())
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
