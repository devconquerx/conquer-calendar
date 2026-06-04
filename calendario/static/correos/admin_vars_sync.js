(function () {
  'use strict';

  function init() {
    var toSelect   = document.getElementById('id_variables_to');
    var fromSelect = document.getElementById('id_variables_from');
    var textarea   = document.getElementById('id_cuerpo');

    if (!toSelect || !textarea) return;

    // Track which options are currently in the "chosen" list
    var prevChosen = new Set(Array.from(toSelect.options).map(function (o) { return o.value; }));

    function insertAtCursor(text) {
      var s = textarea.selectionStart != null ? textarea.selectionStart : textarea.value.length;
      var e = textarea.selectionEnd   != null ? textarea.selectionEnd   : textarea.value.length;
      textarea.value = textarea.value.slice(0, s) + text + textarea.value.slice(e);
      textarea.selectionStart = textarea.selectionEnd = s + text.length;
      textarea.focus();
    }

    var observer = new MutationObserver(function () {
      var currentChosen = new Set(Array.from(toSelect.options).map(function (o) { return o.value; }));

      // Newly added → insert into textarea
      currentChosen.forEach(function (val) {
        if (!prevChosen.has(val)) {
          insertAtCursor(val);
        }
      });

      // Removed → strip from textarea
      prevChosen.forEach(function (val) {
        if (!currentChosen.has(val)) {
          textarea.value = textarea.value.split(val).join('');
        }
      });

      prevChosen = currentChosen;
    });

    observer.observe(toSelect, { childList: true });

    // Double-click on "available" list also inserts
    if (fromSelect) {
      fromSelect.addEventListener('dblclick', function () {
        Array.from(fromSelect.selectedOptions).forEach(function (o) {
          insertAtCursor(o.value);
        });
      });
    }
  }

  // FilteredSelectMultiple JS loads after DOMContentLoaded, so defer slightly
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { setTimeout(init, 200); });
  } else {
    setTimeout(init, 200);
  }
})();
