import type { RoomVote } from "@/lib/room";
import { useCountdown } from "@/lib/useCountdown";

const KEYS = ["A", "B", "C", "D"];

export type Multiplayer = {
  vote: RoomVote | null; // only when it belongs to the level on screen
  clockOffset: number;
  openVote: () => void;
  closeVote: () => void;
};

/** Big screen, multiplayer: open the vote, watch it fill in, close it early, then see what the room picked. */
export function VoteBar({ vote, clockOffset, openVote, closeVote }: Multiplayer) {
  const left = useCountdown(vote?.open ? vote.closesAt : null, clockOffset);

  if (!vote) {
    return (
      <div className="votebar">
        <button className="btn" onClick={openVote}>
          Open the vote
        </button>
        <span className="hint">V</span>
        <span className="votebar-note">Everyone answers on their phone. 20 seconds.</span>
      </div>
    );
  }

  if (vote.open) {
    return (
      <div className="votebar votebar-open" role="status">
        <span className="votebar-timer" aria-label={`${left} seconds left`}>
          {left}s
        </span>
        <span className="votebar-count">
          <b>{vote.voters}</b> of {vote.eligible} voted
        </span>
        <span className="spacer" />
        <button className="btn-ghost" onClick={closeVote}>
          Close the vote now
        </button>
      </div>
    );
  }

  const r = vote.result;
  if (!r) return null;
  return (
    <div className="votebar votebar-done" role="status">
      {r.top === null ? (
        <span>Nobody voted. Pick for the room, or open the vote again.</span>
      ) : (
        <span>
          The room picked <b>{KEYS[r.top]}</b> · {r.voters} of {vote.eligible} voted ({Math.round(r.participation * 100)}%)
        </span>
      )}
    </div>
  );
}
