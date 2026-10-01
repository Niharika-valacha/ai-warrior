import snapshot from "@/data/content-snapshot.json";
import type { Content } from "./types";

const API_URL = process.env.API_URL ?? "http://localhost:8400";
const TIMEOUT_MS = 3000;

/**
 * Server-side: quiz content from the API, fresh on every page load so edits show up on refresh.
 * If the API is down, the game still works from the last exported snapshot.
 */
export async function loadContent(): Promise<{ content: Content; live: boolean }> {
  try {
    const res = await fetch(`${API_URL}/content`, { cache: "no-store", signal: AbortSignal.timeout(TIMEOUT_MS) });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return { content: (await res.json()) as Content, live: true };
  } catch {
    return { content: snapshot as unknown as Content, live: false };
  }
}
