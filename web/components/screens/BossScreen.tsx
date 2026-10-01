import { useState } from "react";
import { useContent } from "@/components/ContentProvider";

// Random spot inside the arena (in %), far enough from the current one that the cursor misses.
function nextSpot(from: { x: number; y: number }) {
  let x: number, y: number;
  do {
    x = 8 + Math.random() * 64;
    y = 12 + Math.random() * 76;
  } while (Math.abs(x - from.x) < 18 && Math.abs(y - from.y) < 25);
  return { x, y };
}

/** Final question. The decoy button runs away from the cursor and can never be clicked. */
export function BossScreen({ onAnswer }: { onAnswer: () => void }) {
  const { taunts, decoy, answer } = useContent().copy.boss;
  const [spot, setSpot] = useState({ x: 22, y: 50 });
  const [escapes, setEscapes] = useState(0);

  function runAway() {
    setSpot(nextSpot);
    setEscapes((n) => n + 1);
  }

  return (
    <main className="boss">
      <span className="chip">Final question</span>
      <h1>{taunts[Math.min(escapes, taunts.length - 1)]}</h1>
      <div className="arena">
        <button
          className="boss-btn boss-runner"
          style={{ left: `${spot.x}%`, top: `${spot.y}%` }}
          onPointerEnter={runAway}
          onFocus={runAway}
          onClick={runAway}
        >
          {decoy}
        </button>
        <button className="boss-btn boss-answer" onClick={onAnswer}>
          {answer}
        </button>
      </div>
    </main>
  );
}
