import { useEffect, useRef } from "react";

/**
 * Global keyboard shortcuts for the presenter. `handler` gets the lowercased key and
 * returns true when it handled it. Ignored while typing in a text field.
 */
export function useHotkeys(handler: (key: string) => boolean) {
  const ref = useRef(handler);
  useEffect(() => {
    ref.current = handler;
  });

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.metaKey || e.ctrlKey || e.altKey) return;
      if (ref.current(e.key.toLowerCase())) e.preventDefault();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
