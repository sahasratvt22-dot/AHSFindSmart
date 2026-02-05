// Accessible dropdown: click + keyboard support + click-outside close
(function () {
  const dropdown = document.querySelector(".nav-dropdown");
  if (!dropdown) return;

  const btn = dropdown.querySelector(".nav-dropbtn");
  const menu = dropdown.querySelector(".nav-dropdown-menu");
  const items = dropdown.querySelectorAll(".nav-dd-item");

  function openMenu() {
    menu.classList.add("open");
    btn.setAttribute("aria-expanded", "true");
  }
  function closeMenu() {
    menu.classList.remove("open");
    btn.setAttribute("aria-expanded", "false");
  }
  function toggleMenu() {
    if (menu.classList.contains("open")) closeMenu();
    else openMenu();
  }

  btn.addEventListener("click", (e) => {
    e.preventDefault();
    toggleMenu();
  });

  btn.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      toggleMenu();
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      openMenu();
      items[0]?.focus();
    }
    if (e.key === "Escape") {
      closeMenu();
      btn.focus();
    }
  });

  items.forEach((a) => {
    a.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        closeMenu();
        btn.focus();
      }
    });
  });

  document.addEventListener("click", (e) => {
    if (!dropdown.contains(e.target)) closeMenu();
  });
})();

// Mobile menu toggle
(function () {
  const toggle = document.querySelector(".nav-toggle");
  const menu = document.querySelector(".nav-mobile");
  if (!toggle || !menu) return;

  function closeMenu() {
    menu.classList.remove("open");
    toggle.setAttribute("aria-expanded", "false");
  }

  toggle.addEventListener("click", () => {
    const open = menu.classList.toggle("open");
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
  });

  document.addEventListener("click", (e) => {
    if (!menu.contains(e.target) && !toggle.contains(e.target)) closeMenu();
  });
})();

// Donut chart on home page
(function () {
  const canvas = document.getElementById("donutChart");
  if (!canvas || !window.__DONUT_DATA__) return;

  const found = Number(window.__DONUT_DATA__.found || 0);
  const lost = Number(window.__DONUT_DATA__.lost || 0);

  // No forced colors (Chart.js will pick defaults). Keep it clean.
  new Chart(canvas, {
    type: "doughnut",
    data: {
      labels: ["Items Found (Posts)", "Items Lost (Claims)"],
datasets: [{
  data: [found, lost],
  backgroundColor: [
    "#77102b",  // Found (burgundy)
    "#ac495d"   // Lost (lighter burgundy/rose)
  ],
  borderColor: "#ffffff",
  borderWidth: 2
}]

    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom" }
      },
      cutout: "65%"
    }
  });
})();

// Map pins -> right panel list
(function () {
  const data = window.__MAP_ITEMS__;
  if (!data) return;

  const pins = document.querySelectorAll(".map-pin");
  const title = document.getElementById("panelTitle");
  const sub = document.getElementById("panelSub");
  const list = document.getElementById("itemsList");
  const empty = document.getElementById("emptyMsg");
  const floatBox = document.getElementById("mapFloat");
  const closeBtn = document.querySelector(".map-float-close");

  function positionFloat(pinEl) {
    if (!floatBox || !pinEl) return;
    const mapRect = pinEl.closest(".map-wrap")?.getBoundingClientRect();
    const pinRect = pinEl.getBoundingClientRect();
    if (!mapRect) return;

    const boxWidth = floatBox.offsetWidth;
    const boxHeight = floatBox.offsetHeight;
    const offsetX = 18;
    const offsetY = -12;

    let left = pinRect.left - mapRect.left + offsetX;
    let top = pinRect.top - mapRect.top + offsetY;

    const maxLeft = mapRect.width - boxWidth - 12;
    const maxTop = mapRect.height - boxHeight - 12;
    if (left < 12) left = 12;
    if (top < 12) top = 12;
    if (left > maxLeft) left = maxLeft;
    if (top > maxTop) top = maxTop;

    floatBox.style.left = `${left}px`;
    floatBox.style.top = `${top}px`;
    floatBox.style.right = "auto";
    floatBox.style.bottom = "auto";
  }

  function render(locId, locName, pinEl) {
    title.textContent = locName;
    sub.textContent = "Items reported in this location:";
    list.innerHTML = "";

    const items = data[locId] || [];

    if (items.length === 0) {
      empty.textContent = "No items reported here yet.";
      empty.style.display = "block";
      if (floatBox) floatBox.style.display = "block";
      positionFloat(pinEl);
      return;
    }

    empty.style.display = "none";
    if (floatBox) floatBox.style.display = "block";
    positionFloat(pinEl);

    items.forEach((it) => {
      const li = document.createElement("li");
      li.className = "map-item";
      li.innerHTML = `
        <div><strong>${it.title}</strong></div>
        <div class="muted tiny">${it.category || ""} • ${it.date_found || ""}</div>
        <div class="muted tiny">${it.location_found || ""}</div>
        <a class="tiny" href="/browse?q=${encodeURIComponent(it.title)}">View in Browse</a>
      `;
      list.appendChild(li);
    });
  }

  pins.forEach((pin) => {
    pin.addEventListener("click", () => {
      render(pin.dataset.locId, pin.dataset.locName, pin);
    });
  });

  if (closeBtn) {
    closeBtn.addEventListener("click", () => {
      if (floatBox) floatBox.style.display = "none";
    });
  }
})();

// (home how-to slider removed in favor of static cards)

// Browse item details modal
(function () {
  const modal = document.querySelector(".item-modal");
  if (!modal) return;

  const buttons = document.querySelectorAll(".js-item-details");
  const closeBtn = modal.querySelector(".modal-close");
  const titleEl = modal.querySelector("#itemModalTitle");
  const descEl = modal.querySelector("[data-modal-description]");
  const categoryEl = modal.querySelector("[data-modal-category]");
  const locationEl = modal.querySelector("[data-modal-location]");
  const dateEl = modal.querySelector("[data-modal-date]");
  const statusEl = modal.querySelector("[data-modal-status]");
  const claimEl = modal.querySelector("[data-modal-claim]");
  const imgEl = modal.querySelector(".item-modal-img");
  const placeholderEl = modal.querySelector(".item-modal-placeholder");

  function setStatus(status) {
    if (!statusEl) return;
    statusEl.textContent = status || "";
    statusEl.setAttribute("data-status", status || "");
  }

  function setImage(src, title) {
    if (src) {
      imgEl.src = src;
      imgEl.alt = `Photo of ${title}`;
      imgEl.style.display = "block";
      placeholderEl.style.display = "none";
    } else {
      imgEl.removeAttribute("src");
      imgEl.alt = "";
      imgEl.style.display = "none";
      placeholderEl.style.display = "flex";
    }
  }

  function openModal(data) {
    titleEl.textContent = data.title || "Item details";
    descEl.textContent = data.description || "";
    categoryEl.textContent = data.category || "—";
    locationEl.textContent = data.location || "—";
    dateEl.textContent = data.date || "—";
    setStatus(data.status || "");
    claimEl.href = data.claimUrl || "#";
    setImage(data.image, data.title || "item");

    modal.classList.add("open");
    modal.setAttribute("aria-hidden", "false");
    document.body.classList.add("modal-open");
  }

  function closeModal() {
    modal.classList.remove("open");
    modal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("modal-open");
  }

  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const data = {
        title: btn.dataset.title,
        description: btn.dataset.description,
        location: btn.dataset.location,
        date: btn.dataset.date,
        category: btn.dataset.category,
        status: btn.dataset.status,
        claimUrl: btn.dataset.claimUrl,
        image: btn.dataset.image
      };
      openModal(data);
    });
  });

  closeBtn?.addEventListener("click", closeModal);
  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeModal();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modal.classList.contains("open")) {
      closeModal();
    }
  });
})();

// Report Found upload filename display
(function () {
  const input = document.getElementById("photo");
  const label = document.getElementById("uploadFilename");
  if (!input || !label) return;

  function updateLabel() {
    const file = input.files && input.files[0];
    label.textContent = file ? file.name : "No file selected";
  }

  input.addEventListener("change", updateLabel);
})();

// (hero parallax removed)
