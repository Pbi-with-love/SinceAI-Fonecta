export type Hours = { closed: true } | { closed: false; open: string; close: string };

const pad = (n: number) => String(n).padStart(2, "0");

function toTime(h: number, m: number) {
  return `${pad(h)}:${pad(m)}`;
}

/** Parse natural language like "mở 10 tới 2", "10:00 - 14:00", "closed", "suljettu". */
export function parseHours(input: string): Hours | null {
  const s = input.toLowerCase().trim();
  if (!s) return null;
  if (
    /(đóng|dong|closed|close all|suljettu|kiinni|stängt|stengt|nghỉ|nghi)/.test(s) &&
    !/\d/.test(s)
  ) {
    return { closed: true };
  }
  const nums = [...s.matchAll(/(\d{1,2})(?:[:.h](\d{2}))?/g)].map((m) => ({
    h: parseInt(m[1] ?? "0", 10),
    m: m[2] ? parseInt(m[2], 10) : 0,
  }));
  if (nums.length < 2) return null;
  const a = nums[0]!;
  let b = nums[1]!;
  if (a.h > 23 || b.h > 23 || a.m > 59 || b.m > 59) return null;
  // "10 to 2" -> afternoon close
  if (b.h < a.h && b.h <= 12) b = { ...b, h: b.h + 12 };
  if (b.h * 60 + b.m <= a.h * 60 + a.m) return null;
  return { closed: false, open: toTime(a.h, a.m), close: toTime(b.h, b.m) };
}

export function formatHours(h: Hours) {
  return h.closed ? "Closed" : `${h.open} – ${h.close}`;
}
