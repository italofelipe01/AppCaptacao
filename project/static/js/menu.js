function toggleMenu() {
    const sidebar = document.getElementById("sidebar");
    const labels = document.querySelectorAll(".menu-label");

    if (sidebar.classList.contains("w-72")) {
        sidebar.classList.remove("w-72");
        sidebar.classList.add("w-20");
        labels.forEach(label => label.classList.add("hidden"));
    } else {
        sidebar.classList.remove("w-20");
        sidebar.classList.add("w-72");
        labels.forEach(label => label.classList.remove("hidden"));
    }
}
