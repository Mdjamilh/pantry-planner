// Small progressive enhancements. Everything works without this file.
(function () {
  "use strict";

  var root = document.documentElement;

  function currentTheme() {
    var set = root.getAttribute("data-theme");
    if (set) return set;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function syncToggle() {
    var btn = document.querySelector("[data-theme-toggle]");
    if (!btn) return;
    var dark = currentTheme() === "dark";
    btn.setAttribute("aria-pressed", dark ? "true" : "false");
    btn.setAttribute("title", dark ? "Switch to light theme" : "Switch to dark theme");
  }

  document.addEventListener("click", function (event) {
    var target = event.target;
    if (!(target instanceof Element)) return;

    var toggle = target.closest("[data-theme-toggle]");
    if (toggle) {
      var next = currentTheme() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try {
        localStorage.setItem("pp-theme", next);
      } catch (e) {
        /* ignore */
      }
      syncToggle();
      return;
    }

    var close = target.closest("[data-dismiss]");
    if (close) {
      var box = close.closest(".alert");
      if (box) box.remove();
      return;
    }

    var copy = target.closest("[data-copy]");
    if (copy) {
      var source = document.getElementById(copy.getAttribute("data-copy"));
      if (!source || !navigator.clipboard) return;
      navigator.clipboard.writeText(source.textContent || "").then(function () {
        var label = copy.textContent;
        copy.textContent = "Copied";
        window.setTimeout(function () {
          copy.textContent = label;
        }, 1500);
      });
      return;
    }

    var print = target.closest("[data-print]");
    if (print) {
      window.print();
    }
  });

  // Plain (non-htmx) forms that delete things ask first.
  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    var question = form.getAttribute("data-confirm");
    if (question && !window.confirm(question)) {
      event.preventDefault();
    }
  });

  // Every htmx request carries the CSRF token from the page's <meta> tag.
  document.addEventListener("htmx:configRequest", function (event) {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && event.detail && event.detail.headers) {
      event.detail.headers["X-CSRF-Token"] = meta.getAttribute("content");
    }
  });

  syncToggle();
})();
