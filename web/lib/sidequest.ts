// Side quests: researched + written by the API (Tavily + Groq), cached there after the first open.
import snapshot from "@/data/sidequests-snapshot.json";
import { apiUrl } from "./apiUrl";

export type Source = { n: number; title: string; url: string };

export type SideQuest = {
  oneLiner: string;
  story: { pain: string; idea: string; unlocked: string; origin: string };
  beforeAfter: { approach: string; how: string; breaks: string }[];
  production: { title: string; text: string }[];
  roles: { qa: string[]; frontend: string[]; backend: string[]; leadership: string[] };
  tools: { group: string; items: { name: string; what: string }[] }[];
  atScale: { lead: string; ops: { name: string; text: string }[]; modelShare: number; takeaway: string };
};

export type SideQuestRecord = { levelId: number; quest: SideQuest; sources: Source[]; model: string; generatedAt: string };

export type FollowUp = { question: string; answer: string; sources: Source[]; model: string };

const GENERATE_TIMEOUT_MS = 90_000; // first open researches and writes: ~10s, allow for slow networks
const ASK_TIMEOUT_MS = 45_000;

async function call<T>(path: string, init: RequestInit, timeoutMs: number): Promise<T> {
  const res = await fetch(`${apiUrl()}${path}`, { ...init, signal: AbortSignal.timeout(timeoutMs) });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `The API returned ${res.status}`);
  }
  return (await res.json()) as T;
}

/** The cached side quest, or generate it now. Falls back to the snapshot if the API can't be reached. */
export async function loadSideQuest(levelId: number): Promise<{ record: SideQuestRecord; offline: boolean }> {
  try {
    return { record: await call<SideQuestRecord>(`/side-quests/${levelId}`, {}, GENERATE_TIMEOUT_MS), offline: false };
  } catch (err) {
    const saved = (snapshot as unknown as SideQuestRecord[]).find((r) => r.levelId === levelId);
    if (saved) return { record: saved, offline: true };
    throw err;
  }
}

export const refreshSideQuest = (levelId: number) =>
  call<SideQuestRecord>(`/side-quests/${levelId}/refresh`, { method: "POST" }, GENERATE_TIMEOUT_MS);

export const askFollowUp = (levelId: number, question: string) =>
  call<FollowUp>(
    `/side-quests/${levelId}/ask`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question }) },
    ASK_TIMEOUT_MS,
  );
