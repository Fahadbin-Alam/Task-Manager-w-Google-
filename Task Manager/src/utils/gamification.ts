import type { CompletionLog } from "../types";
import { addDays, formatDateKey, lastNDays, parseDateKey } from "./date";

const RANKS = [
  "Novice Hunter",
  "Iron Hunter",
  "Shadow Hunter",
  "S-Rank Hunter",
  "Monarch Candidate",
  "Shadow Monarch"
];

export function levelFromXp(xp: number): number {
  return Math.max(1, Math.floor(Math.sqrt(xp / 100)) + 1);
}

export function xpFloorForLevel(level: number): number {
  return Math.max(0, Math.pow(level - 1, 2) * 100);
}

export function xpCeilForLevel(level: number): number {
  return Math.pow(level, 2) * 100;
}

export function progressToNextLevel(xp: number): {
  currentLevel: number;
  nextLevel: number;
  progressRatio: number;
  remainingXp: number;
} {
  const currentLevel = levelFromXp(xp);
  const floor = xpFloorForLevel(currentLevel);
  const ceil = xpCeilForLevel(currentLevel);
  const span = Math.max(1, ceil - floor);
  const progressRatio = Math.min(1, Math.max(0, (xp - floor) / span));
  return {
    currentLevel,
    nextLevel: currentLevel + 1,
    progressRatio,
    remainingXp: Math.max(0, ceil - xp)
  };
}

export function rankFromLevel(level: number): string {
  if (level < 4) return RANKS[0];
  if (level < 7) return RANKS[1];
  if (level < 10) return RANKS[2];
  if (level < 13) return RANKS[3];
  if (level < 16) return RANKS[4];
  return RANKS[5];
}

export function dailyCompletionCount(completions: CompletionLog[], dateKey: string): number {
  return completions.filter((entry) => entry.dateKey === dateKey).length;
}

export function currentStreak(completions: CompletionLog[], todayKey: string): number {
  const uniqueDays = new Set(completions.map((entry) => entry.dateKey));
  if (!uniqueDays.has(todayKey)) return 0;

  let streak = 0;
  let cursor = parseDateKey(todayKey);
  while (uniqueDays.has(formatDateKey(cursor))) {
    streak += 1;
    cursor = addDays(cursor, -1);
  }
  return streak;
}

export function weeklyCompletions(completions: CompletionLog[], today = new Date()): Array<{
  key: string;
  day: string;
  count: number;
}> {
  const days = lastNDays(7, today);
  return days.map((dayKey) => ({
    key: dayKey,
    day: parseDateKey(dayKey).toLocaleDateString(undefined, { weekday: "short" }),
    count: dailyCompletionCount(completions, dayKey)
  }));
}
