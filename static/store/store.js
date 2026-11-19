"use strict";

(() => {
  const header = document.querySelector(".site-header");
  const menuToggle = document.querySelector(".menu-toggle");
  const mobileBreakpoint = window.matchMedia("(max-width: 980px)");

  if (!header) {
    return;
  }

  const updateHeaderOnScroll = () => {
    header.classList.toggle("is-scrolled", window.scrollY > 8);
  };

  updateHeaderOnScroll();
  window.addEventListener("scroll", updateHeaderOnScroll, { passive: true });

  if (!menuToggle) {
    return;
  }

  const closeMenu = () => {
    header.classList.remove("is-menu-open");
    menuToggle.setAttribute("aria-expanded", "false");
    menuToggle.setAttribute("aria-label", "Abrir menú");
  };

  const openMenu = () => {
    header.classList.add("is-menu-open");
    menuToggle.setAttribute("aria-expanded", "true");
    menuToggle.setAttribute("aria-label", "Cerrar menú");
  };

  menuToggle.addEventListener("click", () => {
    if (header.classList.contains("is-menu-open")) {
      closeMenu();
    } else {
      openMenu();
    }
  });

  header.querySelectorAll(".main-nav a, .header-actions a").forEach((link) => {
    link.addEventListener("click", closeMenu);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeMenu();
    }
  });

  document.addEventListener("click", (event) => {
    if (!header.contains(event.target)) {
      closeMenu();
    }
  });

  mobileBreakpoint.addEventListener("change", (event) => {
    if (!event.matches) {
      closeMenu();
    }
  });
})();