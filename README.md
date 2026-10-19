# Daily Practice

My daily practice page: typing, Vim, flashcards, coding, math, chess, plus a Handshake job-search button.

- **Any PC:** open the GitHub Pages site. The links work everywhere.
- **Mac with the helper:** `server.py` serves the page at http://127.0.0.1:5910 and adds Mac timers (notification + alert), opens Anki, and the Jobs button opens Claude Code in Terminal with the `handshake` skill. It starts at login via `com.daniel.practicetimer.plist` (copy to `~/Library/LaunchAgents/`, fix the path, then `launchctl load` it).
- **Linux with the helper:** the same `server.py` uses notify-send, a freedesktop sound and zenity for the timers, launches Anki (native or the Flathub flatpak), and the Jobs button opens Claude Code in kitty with the `/jobhunt` skill. It starts at login via `practicetimer.service`: symlink it into `~/.config/systemd/user/` and run `systemctl --user enable --now practicetimer`.
- **Check marks:** each task has a checkbox for the day. With the helper they are stored in `done.json`; on GitHub Pages they live in the browser. Both reset at midnight.
- **Order:** drag the ⋮⋮ handle to reorder the tasks; the helper stores the order in `order.json`, the static site in the browser.
- **Tampermonkey:** `practice-timer.user.js` shows a countdown pill on the practice sites.
