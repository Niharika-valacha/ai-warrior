import { Avatar } from "@/components/Avatar";
import type { Mood } from "@/lib/sidekicks";
import type { Sidekick } from "@/lib/types";

/** The chosen sidekick, reacting to what just happened. */
export function Buddy({ sidekick, mood, line, size }: { sidekick: Sidekick; mood: Mood; line: string; size: number }) {
  return (
    <section className="buddy" aria-label="Your sidekick">
      <Avatar sidekick={sidekick} mood={mood} size={size} />
      <div className="buddy-text">
        <span className="buddy-name">{sidekick.name}</span>
        <p className="bubble">{line}</p>
      </div>
    </section>
  );
}
