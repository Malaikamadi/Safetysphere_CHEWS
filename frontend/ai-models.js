/**
 * CHEWS v3.0 — AI Models catalog page
 * Filter chips, expandable model cards, live model count from backend /health.
 */
const API = (typeof window !== "undefined" && window.CHEWS_API) || "http://127.0.0.1:8000";

// Mobile menu
const mt = document.getElementById("menu-toggle"), sb = document.getElementById("sidebar");
if (mt && sb) {
  mt.addEventListener("click", () => sb.classList.toggle("sidebar--open"));
}

// Roadmap link guard (shared convention with other pages)
document.querySelectorAll("a.nav-link--soon").forEach((a) =>
  a.addEventListener("click", (e) => e.preventDefault())
);

// ---------------- Filter chips ----------------
const cards = Array.from(document.querySelectorAll(".model-card"));
const chips = Array.from(document.querySelectorAll(".models-filter__chip"));

function applyFilter(filter) {
  cards.forEach((card) => {
    const family = card.dataset.family;
    const status = card.dataset.status;
    let visible = false;
    if (filter === "all") visible = true;
    else if (filter === "roadmap") visible = status === "roadmap";
    else visible = family === filter && status !== "roadmap";
    card.classList.toggle("model-card--hidden", !visible);
  });

  // Hide section headings whose grids are now empty
  document.querySelectorAll(".models-section__heading").forEach((heading) => {
    const grid = heading.nextElementSibling;
    if (!grid || !grid.classList.contains("model-grid")) return;
    const anyVisible = Array.from(grid.querySelectorAll(".model-card")).some(
      (c) => !c.classList.contains("model-card--hidden")
    );
    heading.style.display = anyVisible ? "" : "none";
    grid.style.display = anyVisible ? "" : "none";
  });
}

chips.forEach((chip) => {
  chip.addEventListener("click", () => {
    chips.forEach((c) => c.classList.remove("is-active"));
    chip.classList.add("is-active");
    applyFilter(chip.dataset.filter);
  });
});

// ---------------- Filter counts ----------------
function countFamily(family) {
  return cards.filter((c) =>
    family === "all"
      ? true
      : family === "roadmap"
      ? c.dataset.status === "roadmap"
      : c.dataset.family === family && c.dataset.status !== "roadmap"
  ).length;
}
document.querySelectorAll(".models-filter__chip-count").forEach((span) => {
  span.textContent = "· " + countFamily(span.dataset.count);
});

// ---------------- Expand model cards ----------------
document.querySelectorAll("[data-toggle]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const id = btn.getAttribute("data-toggle");
    const target = document.getElementById(id);
    if (!target) return;
    const open = target.classList.toggle("is-open");
    btn.textContent = open ? "Hide model card" : "View model card";
  });
});

// ---------------- Live KPI from /health ----------------
async function loadKpis() {
  const activeEl = document.getElementById("kpi-active");
  const subEl = document.getElementById("kpi-active-sub");
  try {
    const res = await fetch(`${API}/health`);
    if (!res.ok) throw new Error(`Status ${res.status}`);
    const data = await res.json();
    const models = data.models || [];
    const services = data.services || [];
    activeEl.textContent = models.length;
    subEl.textContent = `${services.length} services · v${data.version || "—"}`;
  } catch {
    // Fallback: count cards on the page
    const liveCount = cards.filter((c) => c.dataset.status === "live").length;
    activeEl.textContent = liveCount;
    subEl.textContent = "Backend offline · counting live cards";
  }
}
loadKpis();

// ---------------- Scroll-to-hash with offset ----------------
window.addEventListener("load", () => {
  if (location.hash) {
    const el = document.querySelector(location.hash);
    if (el) {
      const y = el.getBoundingClientRect().top + window.scrollY - 80;
      window.scrollTo({ top: y, behavior: "smooth" });
    }
  }
});
