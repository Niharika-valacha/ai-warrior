import { useEffect, useState } from "react";

const LINE_MS = 550;

/** Reveals `lines` one at a time, like a terminal printing. Restarts whenever `key` changes. */
export function useReveal(lines: string[], key: string) {
  const [shown, setShown] = useState(0);
  const total = lines.length;

  useEffect(() => {
    setShown(0);
    const t = setInterval(() => setShown((n) => Math.min(n + 1, total)), LINE_MS);
    return () => clearInterval(t);
  }, [key, total]);

  return { shown, done: shown >= total, skip: () => setShown(total) };
}
