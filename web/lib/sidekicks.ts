// Sidekick images live in public/avatars/{id}-{mood}.jpg; their names and lines come from the API.
import type { Phase } from "./quiz";
import type { Copy, Sidekick } from "./types";

export type Mood = "idle" | "fail" | "win";

const MOODS: Mood[] = ["idle", "fail", "win"];

export const sidekickImage = (id: string, mood: Mood) => `/avatars/${id}-${mood}.jpg`;

export const allSidekickImages = (sidekicks: Sidekick[]) => sidekicks.flatMap((s) => MOODS.map((m) => sidekickImage(s.id, m)));

/** How the sidekick reacts to each phase of a level. */
export function reaction(sidekick: Sidekick, phase: Phase, lines: Copy["reactions"]): { mood: Mood; line: string } {
  switch (phase) {
    case "fail":
      return { mood: "fail", line: lines.fail };
    case "retry":
      return { mood: "idle", line: lines.retry };
    case "run":
    case "learn":
      return { mood: "win", line: sidekick.move };
    default:
      return { mood: "idle", line: sidekick.think };
  }
}
