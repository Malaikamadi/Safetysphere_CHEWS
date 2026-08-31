/**
 * CHEWS — dark / light appearance (persists to localStorage).
 * Basemaps use OpenStreetMap (no API key). Dark mode inverts the tile pane only.
 */
(function () {
  const STORAGE_KEY = "chews-theme";
  const listeners = [];

  const TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
  const TILE_OPTS = {
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    subdomains: "abc",
    maxZoom: 19,
  };

  function currentTheme() {
    return document.documentElement.getAttribute("data-theme") === "light"
      ? "light"
      : "dark";
  }

  function onChange(cb) {
    listeners.push(cb);
    return function () {
      const i = listeners.indexOf(cb);
      if (i >= 0) listeners.splice(i, 1);
    };
  }

  function notify(theme) {
    listeners.forEach(function (cb) {
      try {
        cb(theme);
      } catch (_) {}
    });
  }

  function syncAria() {
    const dark = currentTheme() === "dark";
    document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
      btn.setAttribute(
        "aria-label",
        dark ? "Switch to light mode" : "Switch to dark mode"
      );
      btn.title = dark ? "Light mode" : "Dark mode";
    });
  }

  function setTheme(next) {
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch (_) {}
    syncAria();
    notify(next);
  }

  function attachBasemap(map, extraOpts) {
    if (!map || !window.L) return null;
    const opts = Object.assign({}, TILE_OPTS, extraOpts || {});
    if (opts.maxZoom > 19) opts.maxZoom = 19;
    return L.tileLayer(TILE_URL, opts).addTo(map);
  }

  window.chewsTheme = {
    current: currentTheme,
    set: setTheme,
    onChange: onChange,
    attachBasemap: attachBasemap,
    tileUrl: TILE_URL,
    tileOpts: TILE_OPTS,
  };

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
      btn.addEventListener("click", () => {
        setTheme(currentTheme() === "dark" ? "light" : "dark");
      });
    });
    syncAria();
  });
})();
