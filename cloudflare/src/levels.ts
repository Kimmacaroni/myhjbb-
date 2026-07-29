/**
 * 경험치 ↔ 레벨 변환 공식. Python 버전(levels.py)과 완전히 동일한 공식입니다.
 * 레벨 L에서 L+1로 올라가는 데 필요한 경험치: 5L² + 50L + 100
 */

export function xpToNextLevel(level: number): number {
  return 5 * level ** 2 + 50 * level + 100;
}

const totalXpCache = new Map<number, number>();

export function totalXpForLevel(level: number): number {
  const cached = totalXpCache.get(level);
  if (cached !== undefined) return cached;

  let total = 0;
  for (let lv = 0; lv < level; lv++) total += xpToNextLevel(lv);
  totalXpCache.set(level, total);
  return total;
}

export function levelFromXp(xp: number): number {
  let level = 0;
  let remaining = Math.max(0, xp);
  while (remaining >= xpToNextLevel(level)) {
    remaining -= xpToNextLevel(level);
    level += 1;
  }
  return level;
}

export interface Progress {
  level: number;
  earned: number;
  needed: number;
}

export function progress(xp: number): Progress {
  const level = levelFromXp(xp);
  const earned = Math.max(0, xp) - totalXpForLevel(level);
  return { level, earned, needed: xpToNextLevel(level) };
}

export function progressBar(earned: number, needed: number, width = 12): string {
  if (needed <= 0) return "▰".repeat(width);
  const filled = Math.min(width, Math.max(0, Math.round((width * earned) / needed)));
  return "▰".repeat(filled) + "▱".repeat(width - filled);
}
