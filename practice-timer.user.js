// ==UserScript==
// @name         Daily Practice Timer
// @namespace    daniel.practice.timer
// @version      1.0
// @description  Shows a countdown on practice sites: Typing 5 min, Vim 5 min, Coding 60 min, Math 60 min. Counts only while a tab is visible; resets each day.
// @match        https://monkeytype.com/*
// @match        https://www.typingtom.com/*
// @match        https://www.vim-hero.com/*
// @match        https://vim-hero.com/*
// @match        https://leetcode.com/*
// @match        https://neetcode.io/*
// @match        https://codingbat.com/*
// @match        https://www.codewars.com/*
// @match        https://claude.ai/artifact/5EeSfFvAAFvs1VCKUZ12qx*
// @match        https://www.deep-ml.com/*
// @match        https://www.compscilib.com/*
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_addValueChangeListener
// @grant        GM_notification
// @noframes
// @run-at       document-idle
// ==/UserScript==

(function () {
  'use strict';

  // Edit minutes here.
  const GROUPS = {
    typing: { label: 'Typing', minutes: 5,  hosts: ['monkeytype.com', 'www.typingtom.com'] },
    vim:    { label: 'Vim',    minutes: 5,  hosts: ['www.vim-hero.com', 'vim-hero.com'] },
    coding: { label: 'Coding', minutes: 60, hosts: ['leetcode.com', 'neetcode.io', 'codingbat.com', 'www.codewars.com', 'claude.ai'] },
    math:   { label: 'Math',   minutes: 60, hosts: ['www.deep-ml.com', 'www.compscilib.com'] },
  };

  const groupKey = Object.keys(GROUPS).find((k) => GROUPS[k].hosts.includes(location.hostname));
  if (!groupKey) return;
  const group = GROUPS[groupKey];
  const KEY = 'timer:' + groupKey;
  const totalMs = group.minutes * 60 * 1000;

  const today = () => new Date().toLocaleDateString('en-CA'); // YYYY-MM-DD, local time
  function load() {
    const s = GM_getValue(KEY, null);
    if (!s || s.date !== today()) return { date: today(), used: 0, lastTick: 0, paused: false, notified: false };
    return s;
  }
  const save = (s) => GM_setValue(KEY, s);

  // ---- Widget (shadow DOM so site CSS can't touch it) ----
  const host = document.createElement('div');
  host.style.cssText = 'position:fixed;right:16px;bottom:16px;z-index:2147483647;';
  const root = host.attachShadow({ mode: 'open' });
  root.innerHTML = `
    <style>
      .pill { display:flex; align-items:center; gap:8px; font:600 13px/1 -apple-system, system-ui, sans-serif;
              background:#18202b; color:#e4e8ee; border-radius:999px; padding:8px 10px 8px 14px;
              box-shadow:0 4px 14px rgba(0,0,0,.25); opacity:.92; user-select:none; }
      .pill.done { background:#1f8a5b; }
      .pill.paused .time { opacity:.55; }
      .time { font-variant-numeric: tabular-nums; min-width:3.6em; text-align:right; }
      .bar { width:56px; height:4px; border-radius:2px; background:rgba(255,255,255,.18); overflow:hidden; }
      .bar i { display:block; height:100%; background:#7db7e0; }
      .done .bar i { background:#fff; }
      button { all:unset; cursor:pointer; padding:2px 5px; border-radius:6px; color:inherit; opacity:.75; font-size:12px; }
      button:hover { opacity:1; background:rgba(255,255,255,.12); }
      .min .bar, .min .ctl { display:none; }
    </style>
    <div class="pill" id="pill" title="Click the time to shrink or expand">
      <span id="label"></span>
      <span class="bar"><i id="fill"></i></span>
      <span class="time" id="time"></span>
      <span class="ctl"><button id="pause" tabindex="-1">Pause</button><button id="reset" tabindex="-1" title="Restart today's timer">Reset</button></span>
    </div>`;
  document.documentElement.appendChild(host);
  const $ = (id) => root.getElementById(id);
  $('label').textContent = group.label;

  // Keep keyboard focus in the page so Vim/Vimium keys keep working.
  root.addEventListener('mousedown', (e) => e.preventDefault());
  $('time').addEventListener('click', () => $('pill').classList.toggle('min'));
  $('pause').addEventListener('click', () => { const s = load(); s.paused = !s.paused; s.lastTick = 0; save(s); paint(s); });
  $('reset').addEventListener('click', () => { save({ date: today(), used: 0, lastTick: 0, paused: false, notified: false }); paint(load()); });

  const fmt = (ms) => { const t = Math.max(0, Math.ceil(ms / 1000)); return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`; };

  function paint(s) {
    const left = totalMs - s.used;
    const done = left <= 0;
    $('pill').classList.toggle('done', done);
    $('pill').classList.toggle('paused', !!s.paused && !done);
    $('time').textContent = done ? 'Done' : fmt(left);
    $('fill').style.width = Math.min(100, (s.used / totalMs) * 100) + '%';
    $('pause').textContent = s.paused ? 'Resume' : 'Pause';
    $('pause').style.display = done ? 'none' : '';
  }

  // ---- Ticking: only while this tab is visible. Shared across tabs of the same group. ----
  function tick() {
    const s = load();
    const now = Date.now();
    if (!document.hidden && !s.paused && s.used < totalMs) {
      const gap = now - s.lastTick;
      if (gap >= 900) {                       // another visible tab may have just ticked
        s.used = Math.min(totalMs, s.used + Math.min(gap, 1500));
        s.lastTick = now;
        if (s.used >= totalMs && !s.notified) {
          s.notified = true;
          try { GM_notification({ title: `${group.label} time is up`, text: `${group.minutes} minutes done for today.`, timeout: 10000 }); } catch (_) {}
        }
        save(s);
      }
    }
    paint(s);
  }

  // A fresh visible tab shouldn't count the time since the last tick elsewhere.
  document.addEventListener('visibilitychange', () => { if (!document.hidden) { const s = load(); s.lastTick = Date.now(); save(s); } });
  GM_addValueChangeListener(KEY, (_k, _o, s) => { if (s) paint(s); });

  const s0 = load(); s0.lastTick = Date.now(); save(s0); paint(s0);
  setInterval(tick, 1000);
})();
