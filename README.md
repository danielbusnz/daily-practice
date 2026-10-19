# Daily Practice

My daily practice page: typing, Vim, flashcards, coding, math, chess, plus a Handshake job-search button.

- **Any PC:** open the GitHub Pages site. The links work everywhere.
- **Mac with the helper:** `server.py` serves the page at http://127.0.0.1:5910 and adds Mac timers (notification + alert), opens Anki, and the Jobs button opens Claude Code in Terminal with the `handshake` skill. It starts at login via `com.daniel.practicetimer.plist` (copy to `~/Library/LaunchAgents/`, fix the path, then `launchctl load` it).
- **Tampermonkey:** `practice-timer.user.js` shows a countdown pill on the practice sites.
