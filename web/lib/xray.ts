import snapshot from "@/data/xray-snapshot.json";
import { apiUrl } from "./apiUrl";

export type XrayStep = { fn: string; line: number; label: string; values: Record<string, unknown> };

export type XrayRun = {
  level: number;
  title: string;
  models: string[]; // which model answered: a Groq model id, or "replay"
  output: unknown;
  steps: XrayStep[];
  sources: Record<string, { start: number; code: string }>;
};

export type XraySource = "live" | "snapshot";

const TIMEOUT_MS = 20_000; // live levels make several real model calls

/**
 * Runs the real code behind a level on the FastAPI backend. If the API is down or slow
 * (bad Wi-Fi on stage), falls back to the snapshot exported by api/export_xray.py.
 */
export async function loadXray(level: number): Promise<{ run: XrayRun; source: XraySource }> {
  try {
    const res = await fetch(`${apiUrl()}/xray/${level}`, { signal: AbortSignal.timeout(TIMEOUT_MS) });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return { run: (await res.json()) as XrayRun, source: "live" };
  } catch {
    return { run: (snapshot as unknown as XrayRun[])[level], source: "snapshot" };
  }
}
