"use client";

import { useEffect, useRef } from "react";
import useNeiraStore from "@/organism/store";
import { hexToRgba, toFiniteNumber } from "@/lib/utils";

function resizeCanvasToElement(canvas, ctx) {
  const rect = canvas.getBoundingClientRect();
  const dpr = Math.max(1, toFiniteNumber(window.devicePixelRatio, 1));
  const width = Math.max(1, Math.floor(rect.width * dpr));
  const height = Math.max(1, Math.floor(rect.height * dpr));

  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }

  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { width: rect.width, height: rect.height };
}

export default function Heart() {
  const canvasRef = useRef(null);
  const heartbeat = useNeiraStore((state) => state.heartbeat);

  const heartbeatRef = useRef(heartbeat);
  useEffect(() => {
    heartbeatRef.current = heartbeat;
  }, [heartbeat]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationFrame = 0;
    let phase = 0;
    let lastTime = performance.now();

    const draw = (now) => {
      const { width, height } = resizeCanvasToElement(canvas, ctx);

      const dt = Math.max(0, (now - lastTime) / 1000);
      lastTime = now;

      const current = heartbeatRef.current;
      const frequency = Math.max(0, toFiniteNumber(current?.frequency, 1));
      const amplitude = Math.max(0.1, toFiniteNumber(current?.amplitude, 1));
      const color = typeof current?.color === "string" ? current.color : "#4B7CB0";

      phase += dt * frequency * Math.PI * 2;

      ctx.clearRect(0, 0, width, height);

      const centerX = width / 2;
      const centerY = height / 2;
      const baseRadius = Math.min(width, height) * 0.18;
      const pulse = Math.sin(phase) * baseRadius * 0.12 * amplitude;
      const radius = Math.max(2, baseRadius + pulse);

      const gradient = ctx.createRadialGradient(
        centerX,
        centerY,
        radius * 0.3,
        centerX,
        centerY,
        radius,
      );

      gradient.addColorStop(0, hexToRgba(color, 1));
      gradient.addColorStop(0.5, hexToRgba(color, 0.55));
      gradient.addColorStop(1, hexToRgba(color, 0));

      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
      ctx.fill();

      animationFrame = requestAnimationFrame(draw);
    };

    animationFrame = requestAnimationFrame(draw);

    const onResize = () => {
      resizeCanvasToElement(canvas, ctx);
    };
    window.addEventListener("resize", onResize, { passive: true });

    return () => {
      if (animationFrame) cancelAnimationFrame(animationFrame);
      window.removeEventListener("resize", onResize);
    };
  }, []);

  return <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" />;
}
