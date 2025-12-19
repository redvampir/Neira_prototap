import { toFiniteNumber } from "../lib/utils.js";
import { modeToColor } from "./heart.js";

export function computeHeartbeat(heart, breath) {
  const resonance = toFiniteNumber(heart?.resonance, 0);
  const tempo = toFiniteNumber(breath?.tempo, 1);
  const mode = typeof heart?.mode === "string" ? heart.mode : "reflective";

  return {
    frequency: 1 + resonance,
    color: modeToColor(mode),
    amplitude: tempo,
  };
}

export function computeIsAlive(heart) {
  const resonance = toFiniteNumber(heart?.resonance, 0);
  return resonance > 0;
}
