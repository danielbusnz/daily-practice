// ==UserScript==
// @name         LeetCode + Codewars: jk to Escape
// @namespace    daniel.practice.jk
// @version      1.1
// @description  In the LeetCode (Monaco) and Codewars (CodeMirror) code editors, typing "jk" quickly in insert mode leaves insert mode, like Vim's `inoremap jk <Esc>`. Needs Vim keybindings on in each site's editor settings.
// @match        https://leetcode.com/*
// @match        https://www.codewars.com/*
// @grant        none
// @run-at       document-start
// ==/UserScript==
(function () {
  "use strict";
  const WINDOW_MS = 400; // "j" then "k" within this many ms counts as Escape; type slower to write "jk" literally.
  let pending = null;    // set after a "j" that was actually inserted (so we are in insert mode)

  function key(target, k, code) {
    const kc = code === "Escape" ? 27 : 8;
    target.dispatchEvent(new KeyboardEvent("keydown", { key: k, code, keyCode: kc, which: kc, bubbles: true, cancelable: true }));
    target.dispatchEvent(new KeyboardEvent("keyup", { key: k, code, keyCode: kc, which: kc, bubbles: true, cancelable: true }));
  }

  // --- LeetCode: Monaco editor (vim via monaco-vim) ---
  function monacoEditorFor(textarea) {
    const m = window.monaco;
    const editors = m && m.editor && m.editor.getEditors ? m.editor.getEditors() : [];
    return editors.find((ed) => ed.getDomNode() && ed.getDomNode().contains(textarea)) || null;
  }

  function monacoJ(ta) {
    const editor = monacoEditorFor(ta);
    const model = editor && editor.getModel();
    const before = model ? model.getAlternativeVersionId() : null;
    // Decide after Monaco handles the key: only an inserted "j" (version changed) means insert mode.
    setTimeout(() => {
      const inserted = model ? model.getAlternativeVersionId() !== before : true;
      pending = inserted ? { at: Date.now(), kind: "monaco", ta, editor, model } : null;
    }, 0);
  }

  function monacoEscape(p) {
    const { ta, editor, model } = p;
    if (editor && model) {
      // Remove the "j" before the cursor, then leave insert mode.
      const pos = editor.getPosition();
      const col = pos.column;
      const range = { startLineNumber: pos.lineNumber, startColumn: col - 1, endLineNumber: pos.lineNumber, endColumn: col };
      if (col > 1 && model.getValueInRange(range) === "j") editor.executeEdits("jk-escape", [{ range, text: "" }]);
    } else {
      key(ta, "Backspace", "Backspace");
    }
    key(ta, "Escape", "Escape");
  }

  // --- Codewars: CodeMirror 5 (vim via its built-in vim keymap) ---
  function cmFor(textarea) {
    const wrap = textarea.closest(".CodeMirror");
    return (wrap && wrap.CodeMirror) || null;
  }

  function cmJ(ta) {
    const cm = cmFor(ta);
    const vim = cm && cm.state && cm.state.vim;
    // Only insert mode counts; in normal mode "j" just moves down.
    pending = vim && vim.insertMode ? { at: Date.now(), kind: "cm", ta, cm } : null;
  }

  function cmEscape(p) {
    const { ta, cm } = p;
    const cur = cm.getCursor();
    if (cur.ch > 0 && cm.getRange({ line: cur.line, ch: cur.ch - 1 }, cur) === "j") {
      cm.replaceRange("", { line: cur.line, ch: cur.ch - 1 }, cur, "+jk-escape");
    }
    const Vim = cm.constructor && cm.constructor.Vim;
    if (Vim && Vim.exitInsertMode) Vim.exitInsertMode(cm);
    else key(ta, "Escape", "Escape");
  }

  document.addEventListener("keydown", (e) => {
    const ta = e.target;
    if (!(ta instanceof HTMLTextAreaElement)) return;
    const kind = ta.closest(".monaco-editor") ? "monaco" : ta.closest(".CodeMirror") ? "cm" : null;
    if (!kind) return;
    if (e.ctrlKey || e.metaKey || e.altKey || e.isComposing) { pending = null; return; }

    if (e.key === "j") {
      (kind === "monaco" ? monacoJ : cmJ)(ta);
      return;
    }

    if (e.key === "k" && pending && pending.ta === ta && Date.now() - pending.at < WINDOW_MS) {
      const p = pending;
      pending = null;
      e.preventDefault();
      e.stopImmediatePropagation();
      (p.kind === "monaco" ? monacoEscape : cmEscape)(p);
      return;
    }
    pending = null;
  }, true);
})();
