import type { Option } from "@/lib/types";

const KEYS = ["A", "B", "C", "D"];

type Props = {
  options: Option[];
  onlyCorrect: boolean; // retry mode: fade out every wrong option
  onPick: (index: number) => void;
};

export function OptionList({ options, onlyCorrect, onPick }: Props) {
  return (
    <ol className="options">
      {options.map((o, i) => {
        const gone = onlyCorrect && !o.correct;
        return (
          <li key={o.text}>
            <button
              className={`opt ${gone ? "opt-gone" : ""} ${onlyCorrect && o.correct ? "opt-glow" : ""}`}
              disabled={gone}
              onClick={() => onPick(i)}
            >
              <kbd>{KEYS[i]}</kbd>
              <span>{o.text}</span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
