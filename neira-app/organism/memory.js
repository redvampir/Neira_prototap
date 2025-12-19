export const MEMORY_MAX_EVENTS = 100;

export function appendEvent(events, event, maxEvents = MEMORY_MAX_EVENTS) {
  const list = Array.isArray(events) ? events : [];
  if (event === null || event === undefined) return list.slice(-maxEvents);

  const max = Number.isFinite(maxEvents)
    ? Math.max(0, Math.floor(maxEvents))
    : MEMORY_MAX_EVENTS;

  return [...list, event].slice(-max);
}
