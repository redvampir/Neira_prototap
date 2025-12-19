export const HEART_MODES = ["reflective", "active", "uncertain"];

export function isHeartMode(value) {
  return typeof value === "string" && HEART_MODES.includes(value);
}

export function modeToColor(mode) {
  const colors = {
    reflective: "#4B7CB0",
    active: "#C94F3D",
    uncertain: "#7A5FA0",
  };

  if (typeof mode !== "string") return colors.reflective;
  return colors[mode] || colors.reflective;
}
