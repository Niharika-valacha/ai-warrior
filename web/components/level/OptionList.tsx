import type { Option } from "@/lib/types";

const KEYS = ["A", "B", "C", "D"];

type Props = {
  options: Option[];
  onlyCorrect: boolean; // retry mode: fade out every wrong option
  onPick: (index: number) => void;
  votes?: number[]; // multiplayer: live votes per option, drawn as bars
  locked?: boolean; // multiplayer: the room is voting, so the host can't pick
};

export function OptionList({ options, onlyCorrect, onPick, votes, locked }: Props) {
  const most = votes ? Math.max(1, ...votes) : 1;
  return (
    <ol className="options">
      {options.map((o, i) => {
        const gone = onlyCorrect && !o.correct;
        const count = votes?.[i] ?? 0;
        return (
          <li key={o.text}>
            <button
              className={`opt ${gone ? "opt-gone" : ""} ${onlyCorrect && o.correct ? "opt-glow" : ""} ${votes ? "opt-voting" : ""}`}
              disabled={gone || locked}
              onClick={() => onPick(i)}
            >
              {votes && <span className="opt-bar" style={{ width: `${(count / most) * 100}%` }} aria-hidden="true" />}
              <kbd>{KEYS[i]}</kbd>
              <span>{o.text}</span>
              {votes && (
                <span className="opt-count" aria-label={`${count} votes`}>
                  {count}
                </span>
              )}
            </button>
          </li>
        );
      })}
    </ol>
  );
}
