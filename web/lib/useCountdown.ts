import { useEffect, useState } from "react";

/** Seconds left until `deadline` (server clock, epoch ms), corrected by this device's clock offset. */
export function useCountdown(deadline: number | null, clockOffset: number): number {
  const remaining = () => (deadline ? Math.max(0, Math.ceil((deadline - (Date.now() + clockOffset)) / 1000)) : 0);
  const [left, setLeft] = useState(remaining);
  useEffect(() => {
    setLeft(remaining());
    if (!deadline) return;
    const t = setInterval(() => setLeft(remaining()), 250);
    return () => clearInterval(t);
  }, [deadline, clockOffset]); // eslint-disable-line react-hooks/exhaustive-deps
  return left;
}
