// ==UserScript==
// @name         LeetCode: jk to Escape
// @namespace    daniel.practice.jk
// @version      1.0
// @description  In the LeetCode code editor, typing "jk" quickly in insert mode leaves insert mode, like Vim's `inoremap jk <Esc>`. Needs Vim keybindings on in LeetCode's editor settings.
// @match        https://leetcode.com/*
// @grant        none
// @run-at       document-start
// ==/UserScript==
(function () {
  "use strict";
  const WINDOW_MS = 400; // "j" then "k" within this many ms counts as Escape; type slower to write "jk" literally.
  let pending = null;    // {at, editor, version} after a "j" that was actually inserted (so we are in insert mode)

  function editorFor(textarea) {
    const m = window.monaco;
    const editors = m && m.editor && m.editor.getEditors ? m.editor.getEditors() : [];
    return editors.find((ed) => ed.getDomNode() && ed.getDomNode().contains(textarea)) || null;
  }

  function key(target, k, code) {
    target.dispatchEvent(new KeyboardEvent("keydown", { key: k, code, keyCode: code === "Escape" ? 27 : 8, which: code === "Escape" ? 27 : 8, bubbles: true, cancelable: true }));
    target.dispatchEvent(new KeyboardEvent("keyup", { key: k, code, keyCode: code === "Escape" ? 27 : 8, which: code === "Escape" ? 27 : 8, bubbles: true, cancelable: true }));
  }

  document.addEventListener("keydown", (e) => {
    const ta = e.target;
    if (!(ta instanceof HTMLTextAreaElement) || !ta.closest(".monaco-editor")) return;
    if (e.ctrlKey || e.metaKey || e.altKey || e.isComposing) { pending = null; return; }

    if (e.key === "j") {
      const editor = editorFor(ta);
      const model = editor && editor.getModel();
      const before = model ? model.getAlternativeVersionId() : null;
      // Decide after Monaco handles the key: only an inserted "j" (version changed) means insert mode.
      setTimeout(() => {
        const inserted = model ? model.getAlternativeVersionId() !== before : true;
        pending = inserted ? { at: Date.now(), editor, model } : null;
      }, 0);
      return;
    }

    if (e.key === "k" && pending && Date.now() - pending.at < WINDOW_MS) {
      const { editor, model } = pending;
      pending = null;
      e.preventDefault();
      e.stopImmediatePropagation();
      if (editor && model) {
        // Remove the "j" before the cursor, then leave insert mode.
        const pos = editor.getPosition();
        const col = pos.column;
        if (col > 1 && model.getValueInRange({ startLineNumber: pos.lineNumber, startColumn: col - 1, endLineNumber: pos.lineNumber, endColumn: col }) === "j") {
          editor.executeEdits("jk-escape", [{ range: { startLineNumber: pos.lineNumber, startColumn: col - 1, endLineNumber: pos.lineNumber, endColumn: col }, text: "" }]);
        }
      } else {
        key(ta, "Backspace", "Backspace");
      }
      key(ta, "Escape", "Escape");
      return;
    }
    pending = null;
  }, true);
})();
