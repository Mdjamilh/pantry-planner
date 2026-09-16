// Loaded in <head> without defer so the saved theme applies before first paint.
(function () {
  try {
    var saved = localStorage.getItem("pp-theme");
    if (saved === "light" || saved === "dark") {
      document.documentElement.setAttribute("data-theme", saved);
    }
  } catch (e) {
    /* storage blocked: fall back to the system preference */
  }
})();
