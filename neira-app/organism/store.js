"use client";

import { create } from "zustand";
import { clamp, clamp01, toFiniteNumber } from "../lib/utils.js";
import { isBreathRhythm, getRhythmTempo } from "./breath.js";
import { computeHeartbeat, computeIsAlive } from "./derived.js";
import { calculateAttention } from "./eye.js";
import { isHeartMode } from "./heart.js";
import { appendEvent, MEMORY_MAX_EVENTS } from "./memory.js";

const TEMPO_MIN = 0.5;
const TEMPO_MAX = 2.0;

function getInitialState(nowMs = Date.now()) {
  const heart = { resonance: 0, mode: "reflective" };
  const breath = { rhythm: "legato", tempo: 1.0 };

  return {
    heart,
    breath,
    eye: {
      focus: null,
      attention: 0,
      lastSeen: null,
    },
    memory: {
      events: [],
      patterns: [],
      birthTime: nowMs,
    },
    heartbeat: computeHeartbeat(heart, breath),
    isAlive: computeIsAlive(heart),
  };
}

const initialState = getInitialState();

const useNeiraStore = create((set, get) => ({
  ...initialState,

  pulse: () => get().heartbeat,

  setResonance: (value) =>
    set((state) => {
      const resonance = clamp01(toFiniteNumber(value, state.heart.resonance));
      const heart = { ...state.heart, resonance };
      return {
        heart,
        heartbeat: computeHeartbeat(heart, state.breath),
        isAlive: computeIsAlive(heart),
      };
    }),

  setMode: (newMode) =>
    set((state) => {
      if (!isHeartMode(newMode)) return {};
      const heart = { ...state.heart, mode: newMode };
      return { heart, heartbeat: computeHeartbeat(heart, state.breath) };
    }),

  breathe: (newRhythm) =>
    set((state) => {
      const rhythm = isBreathRhythm(newRhythm) ? newRhythm : state.breath.rhythm;
      const breath = { rhythm, tempo: getRhythmTempo(rhythm) };
      return { breath, heartbeat: computeHeartbeat(state.heart, breath) };
    }),

  adjustTempo: (delta) =>
    set((state) => {
      const nextTempo = clamp(
        toFiniteNumber(state.breath.tempo, 1) + toFiniteNumber(delta, 0),
        TEMPO_MIN,
        TEMPO_MAX,
      );
      const breath = { ...state.breath, tempo: nextTempo };
      return { breath, heartbeat: computeHeartbeat(state.heart, breath) };
    }),

  see: (perception) =>
    set((state) => {
      const timestamp = Date.now();
      const x = toFiniteNumber(perception?.x, Number.NaN);
      const y = toFiniteNumber(perception?.y, Number.NaN);
      const viewportWidth = toFiniteNumber(perception?.viewportWidth, 0);
      const viewportHeight = toFiniteNumber(perception?.viewportHeight, 0);

      if (
        !Number.isFinite(x) ||
        !Number.isFinite(y) ||
        !(viewportWidth > 0) ||
        !(viewportHeight > 0)
      ) {
        return { eye: { ...state.eye, lastSeen: timestamp } };
      }

      const attention = calculateAttention({ x, y, viewportWidth, viewportHeight });

      const resonanceBefore = toFiniteNumber(state.heart.resonance, 0);
      const resonanceDelta = (attention - 0.5) * 0.01;
      const resonanceAfter = clamp01(resonanceBefore + resonanceDelta);

      const heart = { ...state.heart, resonance: resonanceAfter };
      const eye = { focus: { x, y }, attention, lastSeen: timestamp };

      const memoryEvent = {
        type: "interaction",
        timestamp,
        data: { x, y, attention },
        resonance: { before: resonanceBefore, after: resonanceAfter },
      };

      const events = appendEvent(state.memory.events, memoryEvent, MEMORY_MAX_EVENTS);
      const memory = { ...state.memory, events };

      return {
        heart,
        eye,
        memory,
        heartbeat: computeHeartbeat(heart, state.breath),
        isAlive: computeIsAlive(heart),
      };
    }),

  unfocus: () =>
    set((state) => ({
      eye: { ...state.eye, focus: null, attention: 0 },
    })),

  remember: (event) =>
    set((state) => ({
      memory: {
        ...state.memory,
        events: appendEvent(state.memory.events, event, MEMORY_MAX_EVENTS),
      },
    })),

  learnPattern: (pattern) =>
    set((state) => ({
      memory: {
        ...state.memory,
        patterns: [...state.memory.patterns, pattern],
      },
    })),

  forget: () =>
    set((state) => ({
      memory: { ...state.memory, events: [], patterns: [] },
    })),

  reset: () => set(() => getInitialState()),
}));

export default useNeiraStore;
export { getInitialState };
