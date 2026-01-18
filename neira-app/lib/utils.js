export function toFiniteNumber(value, fallback) {
  const numberValue = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numberValue) ? numberValue : fallback;
}

export function clamp(value, min, max) {
  const numberValue = toFiniteNumber(value, min);
  const minValue = toFiniteNumber(min, 0);
  const maxValue = toFiniteNumber(max, minValue);
  if (minValue > maxValue) return minValue;
  return Math.min(maxValue, Math.max(minValue, numberValue));
}

export function clamp01(value) {
  return clamp(value, 0, 1);
}

export function lerp(a, b, t) {
  const aValue = toFiniteNumber(a, 0);
  const bValue = toFiniteNumber(b, 0);
  const tValue = clamp01(t);
  return aValue + (bValue - aValue) * tValue;
}

export function hexToRgba(hex, alpha) {
  const a = clamp01(alpha);
  if (typeof hex !== "string") return `rgba(0,0,0,${a})`;

  const raw = hex.trim().replace(/^#/, "");
  if (raw.length === 3) {
    const r = Number.parseInt(raw[0] + raw[0], 16);
    const g = Number.parseInt(raw[1] + raw[1], 16);
    const b = Number.parseInt(raw[2] + raw[2], 16);
    if ([r, g, b].some((v) => !Number.isFinite(v))) return `rgba(0,0,0,${a})`;
    return `rgba(${r},${g},${b},${a})`;
  }

  if (raw.length === 6) {
    const r = Number.parseInt(raw.slice(0, 2), 16);
    const g = Number.parseInt(raw.slice(2, 4), 16);
    const b = Number.parseInt(raw.slice(4, 6), 16);
    if ([r, g, b].some((v) => !Number.isFinite(v))) return `rgba(0,0,0,${a})`;
    return `rgba(${r},${g},${b},${a})`;
  }

  return `rgba(0,0,0,${a})`;
}
