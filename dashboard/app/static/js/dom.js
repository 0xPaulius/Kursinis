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
