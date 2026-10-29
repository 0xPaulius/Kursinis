// Maži DOM pagalbininkai (be importų, kad moduliai nesudarytų ciklų).

export function el(id) { return document.getElementById(id); }

export function setText(id, val) {
  const e = el(id);
  if (e) e.textContent = val;
}

export function setPlaceholder(id, val) {
  const e = el(id);
  if (e) e.placeholder = val;
}

// Dialogas: parodomas, fokusas — į pirmą matomą laukelį, o jei jo nėra — į pirmą mygtuką.
export function openDialog(id) {
  const d = el(id);
  if (!d) return;
  d.classList.remove("hidden");
  const items = [...d.querySelectorAll("input, select, textarea, button")]
    .filter(x => !x.disabled && x.getClientRects().length);
  (items.find(x => x.tagName !== "BUTTON") || items[0])?.focus();
}

export function closeDialog(id) {
  el(id)?.classList.add("hidden");
}
