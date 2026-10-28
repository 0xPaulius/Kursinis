// Grafikų spalvos pagal temą (css/theme.css kintamieji); perjungus temą kviečiama applyTheme().

const live = new Set();

export function token(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

// Temos spalvos grafikams yra #RRGGBB, todėl permatomumą pridedame rgba() forma.
export function withAlpha(hex, alpha) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

export function themeOptions() {
  return {
    text: token("--text-muted"),
    grid: token("--line-weak"),
    tooltipBg: token("--panel"),
    tooltipText: token("--text"),
    tooltipBorder: token("--line"),
    font: { family: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace", size: 10.5 },
  };
}

// Ašys, tinklelis ir patarimo langas — bendri visiems linijiniams grafikams.
export function applyAxes(chart, o = themeOptions()) {
  for (const axis of Object.values(chart.options.scales || {})) {
    axis.grid = { ...(axis.grid || {}), color: o.grid };
    axis.border = { ...(axis.border || {}), color: o.grid };
    axis.ticks = { ...(axis.ticks || {}), color: o.text, font: o.font };
  }
  Object.assign(chart.options.plugins.tooltip, {
    backgroundColor: o.tooltipBg,
    titleColor: o.tooltipText,
    bodyColor: o.tooltipText,
    borderColor: o.tooltipBorder,
    borderWidth: 1,
  });
}

// Linijos užpildas: vertikalus gradientas; spalva skaitoma piešiant, todėl seka temą.
export function areaFill(colorToken, top = 0.2) {
  return (ctx) => {
    const color = token(colorToken);
    const { ctx: c, chartArea } = ctx.chart;
    if (!chartArea) return withAlpha(color, top / 2);
    const g = c.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
    g.addColorStop(0, withAlpha(color, top));
    g.addColorStop(1, withAlpha(color, 0));
    return g;
  };
}

export function track(chart, restyle) {
  live.add({ chart, restyle });
  return chart;
}

export function forget(chart) {
  for (const item of live) if (item.chart === chart) live.delete(item);
}

export function applyTheme() {
  const o = themeOptions();
  for (const { chart, restyle } of live) {
    restyle(chart, o);
    chart.update("none");
  }
}

export function sparkline(svg, values, color) {
  const NS = "http://www.w3.org/2000/svg";
  while (svg.firstChild) svg.removeChild(svg.firstChild);
  if (values.length < 2) return;
  const [, , w, h] = svg.getAttribute("viewBox").split(" ").map(Number);
  const max = Math.max(...values) || 1;
  const pts = values.map((v, i) => `${(i * w / (values.length - 1)).toFixed(1)},${(h - h * v / max).toFixed(1)}`);
  const area = document.createElementNS(NS, "polygon");
  area.setAttribute("points", `0,${h} ${pts.join(" ")} ${w},${h}`);
  area.setAttribute("fill", withAlpha(color, 0.18));
  const line = document.createElementNS(NS, "polyline");
  line.setAttribute("points", pts.join(" "));
  line.setAttribute("fill", "none");
  line.setAttribute("stroke", color);
  line.setAttribute("stroke-width", "1.5");
  line.setAttribute("vector-effect", "non-scaling-stroke");
  svg.append(area, line);
}
