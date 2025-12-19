export const BREATH_RHYTHMS = ["legato", "staccato", "syncopated"];

export function isBreathRhythm(value) {
  return typeof value === "string" && BREATH_RHYTHMS.includes(value);
}

export function getRhythmTempo(rhythm) {
  const tempos = {
    legato: 0.8,
    staccato: 1.5,
    syncopated: 1.2,
  };

  if (typeof rhythm !== "string") return 1.0;
  return tempos[rhythm] ?? 1.0;
}
