import { clamp01, toFiniteNumber } from "../lib/utils.js";

export function calculateAttention({ x, y, viewportWidth, viewportHeight }) {
  const xValue = toFiniteNumber(x, Number.NaN);
  const yValue = toFiniteNumber(y, Number.NaN);
  const widthValue = toFiniteNumber(viewportWidth, 0);
  const heightValue = toFiniteNumber(viewportHeight, 0);

  if (!Number.isFinite(xValue) || !Number.isFinite(yValue)) return 0;
  if (!(widthValue > 0) || !(heightValue > 0)) return 0;

  const centerX = widthValue / 2;
  const centerY = heightValue / 2;

  const dx = xValue - centerX;
  const dy = yValue - centerY;
  const distance = Math.sqrt(dx * dx + dy * dy);

  const maxDistance = Math.sqrt(centerX * centerX + centerY * centerY);
  if (!(maxDistance > 0)) return 0;

  return clamp01(1 - distance / maxDistance);
}
