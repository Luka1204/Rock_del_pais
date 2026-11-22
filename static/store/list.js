// store.js: JavaScript de todo el sitio.
// Se carga al final del <body> con "defer", así que el HTML ya existe cuando corre.

// 1) Menú del celular ------------------------------------------------------
// El CSS muestra el menú cuando el header tiene la clase "is-menu-open".
const header = document.querySelector(".site-header");
const menuButton = document.querySelector(".menu-toggle");

function setMenu(open) {
  header.classList.toggle("is-menu-open", open);
  menuButton.setAttribute("aria-expanded", open);
  menuButton.setAttribute("aria-label", open ? "Cerrar menú" : "Abrir menú");
}

if (header && menuButton) {
  // Click en el botón: abre o cierra
  menuButton.addEventListener("click", () => {
    setMenu(!header.classList.contains("is-menu-open"));
  });

  // Click en un link del menú: lo cierra
  header.querySelectorAll(".main-nav a").forEach((link) => {
    link.addEventListener("click", () => setMenu(false));
  });

  // Tecla Escape: lo cierra
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setMenu(false);
  });
}

// 2) Header más chico al hacer scroll --------------------------------------
// El CSS achica el header y le pone sombra con la clase "is-scrolled".
function updateHeader() {
  if (header) header.classList.toggle("is-scrolled", window.scrollY > 10);
}

window.addEventListener("scroll", updateHeader, { passive: true });
updateHeader(); // por si la página ya carga con scroll

// 3) Confirmar antes de eliminar -------------------------------------------
// Cualquier formulario con data-confirm="texto" pide confirmación al enviarse.
document.querySelectorAll("form[data-confirm]").forEach((form) => {
  form.addEventListener("submit", (event) => {
    if (!confirm(form.dataset.confirm)) {
      event.preventDefault(); // si dice que no, no se envía
    }
  });
});