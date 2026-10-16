// CSS de utilitarios do frontend (docs/specs/frontend-css-gerado.md). Gerado por scripts/gerar_css.ps1.
module.exports = {
    content: {
        relative: true,
        files: ["../../project/templates/**/*.html", "../../project/static/js/**/*.js"],
    },
    darkMode: "class",
    corePlugins: {
        // O reset completo zeraria as margens de paragrafos e titulos e mudaria o espacamento de
        // todas as telas. O reset usado fica em entrada.css.
        preflight: false,
    },
    theme: {
        extend: {
            // Opacidades usadas nos templates (bg-cyan-400/12, bg-white/88...) fora da escala do v3.
            opacity: { 12: "0.12", 18: "0.18", 88: "0.88" },
            boxShadow: { soft: "0 20px 50px rgba(15, 23, 42, 0.12)" },
        },
    },
};
