import useNeiraStore from "@/organism/store";

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

let birthPromise = null;

export function birth() {
  if (birthPromise) return birthPromise;

  birthPromise = (async () => {
    const store = useNeiraStore.getState();

    await wait(1000);

    store.setResonance(0.3);
    await wait(2000);

    store.breathe("legato");
    store.setResonance(0.5);
    await wait(2000);

    store.setMode("reflective");
    await wait(1000);

    return true;
  })();

  return birthPromise;
}
