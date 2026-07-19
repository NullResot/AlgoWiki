const DAY_MS = 24 * 60 * 60 * 1000;
const ANCHOR_UTC = Date.UTC(2026, 6, 20);
const PLANET_IDS = Object.freeze(["A", "B", "C"]);

function parseBusinessDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ""));
  if (!match) return null;

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const timestamp = Date.UTC(year, month - 1, day);
  const parsed = new Date(timestamp);

  if (
    parsed.getUTCFullYear() !== year ||
    parsed.getUTCMonth() !== month - 1 ||
    parsed.getUTCDate() !== day
  ) {
    return null;
  }
  return timestamp;
}

export function getDailyPlanetId(businessDate) {
  const timestamp = parseBusinessDate(businessDate);
  if (timestamp === null) return "A";

  const offset = Math.round((timestamp - ANCHOR_UTC) / DAY_MS);
  const index = ((offset % PLANET_IDS.length) + PLANET_IDS.length) % PLANET_IDS.length;
  return PLANET_IDS[index];
}
