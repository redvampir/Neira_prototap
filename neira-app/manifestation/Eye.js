"use client";

import { useEffect, useRef } from "react";
import useNeiraStore from "@/organism/store";

export default function Eye() {
  const see = useNeiraStore((state) => state.see);
  const unfocus = useNeiraStore((state) => state.unfocus);
  const focus = useNeiraStore((state) => state.eye.focus);
  const attention = useNeiraStore((state) => state.eye.attention);

  const pendingRef = useRef(null);
  const frameRef = useRef(0);

  useEffect(() => {
    const flush = () => {
      frameRef.current = 0;
      const payload = pendingRef.current;
      pendingRef.current = null;
      if (payload) see(payload);
    };

    const schedule = (payload) => {
      pendingRef.current = payload;
      if (frameRef.current) return;
      frameRef.current = requestAnimationFrame(flush);
    };

    const onPointerMove = (e) => {
      schedule({
        x: e.clientX,
        y: e.clientY,
        viewportWidth: window.innerWidth,
        viewportHeight: window.innerHeight,
      });
    };

    const onLeave = () => {
      pendingRef.current = null;
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
      frameRef.current = 0;
      unfocus();
    };

    window.addEventListener("pointermove", onPointerMove, { passive: true });
    window.addEventListener("mouseleave", onLeave, { passive: true });
    window.addEventListener("blur", onLeave, { passive: true });

    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("mouseleave", onLeave);
      window.removeEventListener("blur", onLeave);
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    };
  }, [see, unfocus]);

  if (!focus || attention < 0.1) return null;

  return (
    <div
      className="pointer-events-none fixed z-20 h-4 w-4 rounded-full bg-white"
      style={{
        left: focus.x,
        top: focus.y,
        transform: "translate(-50%, -50%)",
        opacity: attention,
        boxShadow: `0 0 ${attention * 20}px rgba(255,255,255,${attention})`,
      }}
    />
  );
}
