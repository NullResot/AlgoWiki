function normalizeDateKey(value) {
  return value ? String(value).slice(0, 10) : "";
}

/**
 * Sort championship schedule rows so ongoing/upcoming (`!is_past`) contests
 * always appear before ended (`is_past`) contests, preserving chronological order
 * within each group.
 */
export function sortScheduleRows(rows) {
  if (!Array.isArray(rows) || rows.length <= 1) {
    return Array.isArray(rows) ? [...rows] : [];
  }
  return [...rows].sort((a, b) => {
    const aPast = a?.is_past ? 1 : 0;
    const bPast = b?.is_past ? 1 : 0;
    if (aPast !== bPast) {
      return aPast - bPast;
    }

    const aStart = normalizeDateKey(a?.event_date);
    const bStart = normalizeDateKey(b?.event_date);
    if (aStart !== bStart) {
      if (!aStart) return 1;
      if (!bStart) return -1;
      return aStart.localeCompare(bStart);
    }

    const aEnd = normalizeDateKey(a?.end_date || a?.event_date);
    const bEnd = normalizeDateKey(b?.end_date || b?.event_date);
    if (aEnd !== bEnd) {
      if (!aEnd) return 1;
      if (!bEnd) return -1;
      return aEnd.localeCompare(bEnd);
    }

    return Number(a?.id || 0) - Number(b?.id || 0);
  });
}
