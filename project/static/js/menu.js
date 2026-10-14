const SIDEBAR_STORAGE_KEY = "app-sidebar-collapsed";

function setMenuCollapsed(collapsed, persist = true) {
    const sidebar = document.getElementById("sidebar");
    const toggle = document.getElementById("sidebar-toggle");

    if (!sidebar || !toggle) return;

    sidebar.classList.toggle("is-collapsed", collapsed);
    toggle.setAttribute("aria-expanded", String(!collapsed));
    toggle.setAttribute("aria-label", collapsed ? "Expandir menu" : "Recolher menu");
    toggle.setAttribute("title", collapsed ? "Expandir menu" : "Recolher menu");

    if (persist) {
        localStorage.setItem(SIDEBAR_STORAGE_KEY, String(collapsed));
    }
}

function toggleMenu() {
    const sidebar = document.getElementById("sidebar");
    if (sidebar) setMenuCollapsed(!sidebar.classList.contains("is-collapsed"));
}

document.addEventListener("DOMContentLoaded", () => {
    const savedState = localStorage.getItem(SIDEBAR_STORAGE_KEY);
    const compactViewport = window.matchMedia("(max-width: 860px)").matches;
    setMenuCollapsed(savedState === null ? compactViewport : savedState === "true", false);
});
