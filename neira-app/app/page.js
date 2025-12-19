"use client";

import { useEffect, useRef } from "react";
import Canvas from "@/manifestation/Canvas";
import useNeiraStore from "@/organism/store";
import { birth } from "@/ritual/birth";

export default function Home() {
  const isAlive = useNeiraStore((state) => state.isAlive);
  const startedRef = useRef(false);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    void birth();
  }, []);

  return (
    <main className="relative h-dvh w-full overflow-hidden">
      <div
        className={[
          "pointer-events-none absolute inset-0 z-10 flex items-center justify-center bg-black",
          "transition-opacity duration-700",
          isAlive ? "opacity-0" : "opacity-100",
        ].join(" ")}
      >
        <p className="text-sm opacity-50">...</p>
      </div>
      <Canvas />
    </main>
  );
}
