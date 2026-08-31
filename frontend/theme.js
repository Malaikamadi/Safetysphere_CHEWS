/**
 * CHEWS — dark / light appearance (persists to localStorage).
 * Also swaps CARTO basemaps so maps follow the theme.
 */
(function () {
  const STORAGE_KEY = "chews-theme";
  const listeners = [];

  const TILE = {
    dark: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
    light: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
  };
  const ATTRIB =
    '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/attributions">CARTO</a>';

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
    const opts = Object.assign(
      { attribution: ATTRIB, subdomains: "abcd", maxZoom: 19 },
      extraOpts || {}
    );
    let layer = L.tileLayer(TILE[currentTheme()], opts).addTo(map);
    onChange(function (theme) {
      if (!map) return;
      map.removeLayer(layer);
      layer = L.tileLayer(TILE[theme], opts).addTo(map);
      if (typeof layer.bringToBack === "function") layer.bringToBack();
    });
    return layer;
  }

  window.chewsTheme = {
    current: currentTheme,
    set: setTheme,
    onChange: onChange,
    attachBasemap: attachBasemap,
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
