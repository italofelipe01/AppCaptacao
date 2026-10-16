// O estado inicial (salvo ou, sem nada salvo, recolhido em telas de ate 860 px) e aplicado pelo
// script logo apos o <aside> em components/menu.html, antes da primeira pintura.
const SIDEBAR_STORAGE_KEY = "app-sidebar-collapsed";

function atualizarDicasDoMenu() {
    const sidebar = document.getElementById("sidebar");
    if (!sidebar) return;
    const recolhido = sidebar.classList.contains("is-collapsed");
    sidebar.querySelectorAll(".sidebar-nav a, .sidebar-footer :is(a, button)").forEach((item) => {
        const rotulo = item.querySelector(".menu-label")?.textContent.trim() || "";
        if (recolhido && rotulo) item.setAttribute("title", rotulo);
        else item.removeAttribute("title");
    });
}

function setMenuCollapsed(collapsed, persist = true) {
    const sidebar = document.getElementById("sidebar");
    const toggle = document.getElementById("sidebar-toggle");

    if (!sidebar || !toggle) return;

    sidebar.classList.toggle("is-collapsed", collapsed);
    toggle.setAttribute("aria-expanded", String(!collapsed));
    toggle.setAttribute("aria-label", collapsed ? "Expandir menu" : "Recolher menu");
    toggle.setAttribute("title", collapsed ? "Expandir menu" : "Recolher menu");
    atualizarDicasDoMenu();

    if (persist) {
        localStorage.setItem(SIDEBAR_STORAGE_KEY, String(collapsed));
    }
}

function toggleMenu() {
    const sidebar = document.getElementById("sidebar");
    if (sidebar) setMenuCollapsed(!sidebar.classList.contains("is-collapsed"));
}

document.addEventListener("DOMContentLoaded", () => {
    const sidebar = document.getElementById("sidebar");
    if (sidebar) setMenuCollapsed(sidebar.classList.contains("is-collapsed"), false);
});
