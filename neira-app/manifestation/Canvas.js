"use client";

import Breath from "./Breath";
import Eye from "./Eye";
import Heart from "./Heart";

export default function Canvas() {
  return (
    <div className="relative h-dvh w-full overflow-hidden bg-[#f9f6f2]">
      <Breath>
        <Heart />
      </Breath>
      <Eye />
    </div>
  );
}
