"use client";

import { useEffect, useRef } from "react";
import useNeiraStore from "@/organism/store";
import { toFiniteNumber } from "@/lib/utils";

export default function Breath({ children }) {
  const rhythm = useNeiraStore((state) => state.breath.rhythm);
  const tempo = useNeiraStore((state) => state.breath.tempo);

  const containerRef = useRef(null);
  const rhythmRef = useRef(rhythm);
  const tempoRef = useRef(tempo);

  useEffect(() => {
    rhythmRef.current = rhythm;
  }, [rhythm]);

  useEffect(() => {
    tempoRef.current = tempo;
  }, [tempo]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let animationFrame = 0;
    let phase = 0;
    let lastTime = performance.now();

    const animate = (now) => {
      const dt = Math.max(0, (now - lastTime) / 1000);
      lastTime = now;

      const tempoValue = toFiniteNumber(tempoRef.current, 1);
      phase += dt * tempoValue * Math.PI * 2 * 0.35;

      const currentRhythm = rhythmRef.current;
      let scale = 1;

      switch (currentRhythm) {
        case "legato":
          scale = 1 + Math.sin(phase) * 0.06;
          break;
        case "staccato":
          scale = 1 + (Math.sin(phase) > 0.75 ? 0.1 : 0);
          break;
        case "syncopated":
          scale = 1 + Math.sin(phase * 1.3) * Math.sin(phase * 0.7) * 0.06;
          break;
        default:
          scale = 1;
      }

      container.style.transform = `scale(${scale})`;
      animationFrame = requestAnimationFrame(animate);
    };

    animationFrame = requestAnimationFrame(animate);

    return () => {
      if (animationFrame) cancelAnimationFrame(animationFrame);
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className="absolute inset-0 will-change-transform"
      style={{ transformOrigin: "center center" }}
    >
      {children}
    </div>
  );
}
