// Modal component - handles HTMX modal interactions

htmx.on("htmx:afterSwap", (e) => {
    // Response targeting #dialog => show the modal
    if (e.detail.target.id === "dialog") {
        var modalEl = document.getElementById("modal");
        var modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
    }
});

htmx.on("htmx:beforeSwap", (e) => {
    // Empty response targeting #dialog => hide the modal
    if (e.detail.target.id === "dialog" && !e.detail.xhr.response) {
        var modalEl = document.getElementById("modal");
        var modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) {
            modal.hide();
        }
        document.body.classList.remove('modal-open');
        document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
        e.detail.shouldSwap = false;
        document.body.style.overflow = "auto";
    }
});

// Clean up modal when hidden
document.addEventListener('hidden.bs.modal', (e) => {
    if (e.target.id === 'modal') {
        document.getElementById('dialog').innerHTML = '';
        document.body.classList.remove('modal-open');
        document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
        document.body.style.overflow = "auto";
    }
});

// Custom event to close modal programmatically
htmx.on("closeModal", () => {
    var modalEl = document.getElementById("modal");
    var modal = bootstrap.Modal.getInstance(modalEl);
    if (modal) {
        modal.hide();
    }
});
