import { sidekickImage, type Mood } from "@/lib/sidekicks";
import type { Sidekick } from "@/lib/types";

const MOOD_LABEL: Record<Mood, string> = { idle: "thinking", fail: "crying", win: "celebrating" };

export function Avatar({ sidekick, mood = "idle", size = 120 }: { sidekick: Sidekick; mood?: Mood; size?: number }) {
  return (
    // Plain img: tiny local JPEGs, preloaded by the game, no need for next/image.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={sidekickImage(sidekick.id, mood)}
      width={size}
      height={size}
      alt={`${sidekick.name}, ${MOOD_LABEL[mood]}`}
      className={`avatar avatar-${mood}`}
    />
  );
}
