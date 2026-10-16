// Modais das telas de Usuários e Operações. O foco entra no modal ao abrir e volta para quem o
// abriu; Tab fica dentro do modal; Esc e clique fora fecham só o modal de cima e, se algo foi
// digitado, perguntam antes de descartar.
const modaisAbertos = [];

function estadoDoModal(modal) {
    return JSON.stringify(Array.from(modal.querySelectorAll("input, select, textarea")).map((campo) => (
        campo.type === "checkbox" || campo.type === "radio" ? campo.checked : campo.value
    )));
}

function focaveisDoModal(modal) {
    return Array.from(modal.querySelectorAll("a[href], button, input, select, textarea, [tabindex]")).filter((el) => (
        !el.disabled && el.type !== "hidden" && el.tabIndex >= 0 && el.getClientRects().length > 0
    ));
}

function abrirModal(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    const jaAberto = modaisAbertos.find((item) => item.modal === modal);
    modal.classList.remove("hidden");
    modal.classList.add("flex");
    document.body.classList.add("modal-open");
    if (jaAberto) {
        jaAberto.estado = estadoDoModal(modal);
        return;
    }
    modaisAbertos.push({ modal, origem: document.activeElement, estado: estadoDoModal(modal) });
    const corpo = modal.querySelector(".app-modal-body");
    const primeiro = (corpo && focaveisDoModal(corpo)[0]) || focaveisDoModal(modal)[0];
    primeiro?.focus();
}

function fecharModal(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    modal.classList.add("hidden");
    modal.classList.remove("flex");
    if (!document.querySelector(".app-modal-overlay.flex")) {
        document.body.classList.remove("modal-open");
    }
    const indice = modaisAbertos.findIndex((item) => item.modal === modal);
    if (indice < 0) return;
    const [fechado] = modaisAbertos.splice(indice, 1);
    if (fechado.origem instanceof HTMLElement && fechado.origem.isConnected) fechado.origem.focus();
}

function fecharModalDeCima() {
    const topo = modaisAbertos[modaisAbertos.length - 1];
    if (!topo) return;
    const alterado = estadoDoModal(topo.modal) !== topo.estado;
    if (alterado && !window.confirm("Descartar o que foi digitado?")) return;
    fecharModal(topo.modal.id);
}

document.addEventListener("keydown", (event) => {
    const topo = modaisAbertos[modaisAbertos.length - 1];
    if (!topo) return;
    if (event.key === "Escape") {
        event.preventDefault();
        fecharModalDeCima();
        return;
    }
    if (event.key !== "Tab") return;
    const focaveis = focaveisDoModal(topo.modal);
    if (!focaveis.length) return;
    const primeiro = focaveis[0];
    const ultimo = focaveis[focaveis.length - 1];
    if (!topo.modal.contains(document.activeElement)) {
        event.preventDefault();
        primeiro.focus();
    } else if (event.shiftKey && document.activeElement === primeiro) {
        event.preventDefault();
        ultimo.focus();
    } else if (!event.shiftKey && document.activeElement === ultimo) {
        event.preventDefault();
        primeiro.focus();
    }
});

document.addEventListener("click", (event) => {
    const topo = modaisAbertos[modaisAbertos.length - 1];
    if (topo && event.target === topo.modal) fecharModalDeCima();
});
