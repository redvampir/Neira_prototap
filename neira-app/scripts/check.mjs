import assert from "node:assert/strict";

import { getRhythmTempo } from "../organism/breath.js";
import { computeHeartbeat } from "../organism/derived.js";
import { calculateAttention } from "../organism/eye.js";
import { modeToColor } from "../organism/heart.js";
import useNeiraStore from "../organism/store.js";

function approxEqual(actual, expected, eps = 1e-9) {
  assert.ok(Math.abs(actual - expected) <= eps, `ожидалось ~${expected}, получено ${actual}`);
}

function run() {
  assert.equal(modeToColor("reflective"), "#4B7CB0");
  assert.equal(modeToColor("active"), "#C94F3D");
  assert.equal(modeToColor("uncertain"), "#7A5FA0");
  assert.equal(modeToColor("???"), "#4B7CB0");

  approxEqual(getRhythmTempo("legato"), 0.8);
  approxEqual(getRhythmTempo("staccato"), 1.5);
  approxEqual(getRhythmTempo("syncopated"), 1.2);
  approxEqual(getRhythmTempo("???"), 1.0);

  approxEqual(calculateAttention({ x: 50, y: 50, viewportWidth: 100, viewportHeight: 100 }), 1);
  approxEqual(calculateAttention({ x: 0, y: 0, viewportWidth: 100, viewportHeight: 100 }), 0);
  approxEqual(calculateAttention({ x: 100, y: 100, viewportWidth: 100, viewportHeight: 100 }), 0);
  approxEqual(calculateAttention({ x: 50, y: 50, viewportWidth: 0, viewportHeight: 100 }), 0);

  const store = useNeiraStore.getState();
  store.reset();

  store.setResonance(2);
  assert.equal(useNeiraStore.getState().heart.resonance, 1);

  store.setResonance(-1);
  assert.equal(useNeiraStore.getState().heart.resonance, 0);

  store.setResonance(0.25);
  store.setMode("active");
  store.breathe("staccato");

  const { heart, breath, heartbeat, isAlive } = useNeiraStore.getState();
  assert.equal(isAlive, true);
  approxEqual(heartbeat.frequency, 1 + heart.resonance);
  approxEqual(heartbeat.amplitude, breath.tempo);
  assert.equal(heartbeat.color, "#C94F3D");

  const derived = computeHeartbeat(heart, breath);
  approxEqual(derived.frequency, heartbeat.frequency);
  approxEqual(derived.amplitude, heartbeat.amplitude);
  assert.equal(derived.color, heartbeat.color);

  for (let i = 0; i < 150; i += 1) {
    store.see({ x: i % 100, y: i % 100, viewportWidth: 100, viewportHeight: 100 });
  }

  const after = useNeiraStore.getState();
  assert.ok(Array.isArray(after.memory.events));
  assert.ok(after.memory.events.length <= 100);
  assert.ok(after.eye.lastSeen !== null);
  assert.ok(after.eye.focus !== null);

  store.unfocus();
  assert.equal(useNeiraStore.getState().eye.focus, null);
  assert.equal(useNeiraStore.getState().eye.attention, 0);
}

try {
  run();
  console.log("OK: organism-проверка пройдена");
} catch (err) {
  console.error("FAIL: organism-проверка не пройдена");
  console.error(err);
  process.exitCode = 1;
}
