import { useEffect, useState } from "react";
import { highlightLine } from "@/lib/highlight";
import { useHotkeys } from "@/lib/useHotkeys";
import { loadXray, type XrayRun, type XraySource } from "@/lib/xray";

const PLAY_MS = 1200;

/** X-ray mode: the real code behind a level, stepped through with the values it produced. */
export function XrayPanel({ level, onClose }: { level: number; onClose: () => void }) {
  const [data, setData] = useState<{ run: XrayRun; source: XraySource } | null>(null);
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    let alive = true;
    loadXray(level).then((d) => alive && setData(d));
    return () => {
      alive = false;
    };
  }, [level]);

  const last = (data?.run.steps.length ?? 1) - 1;

  useEffect(() => {
    if (!playing) return;
    if (step >= last) return setPlaying(false);
    const t = setTimeout(() => setStep((s) => s + 1), PLAY_MS);
    return () => clearTimeout(t);
  }, [playing, step, last]);

  const go = (to: number) => {
    setPlaying(false);
    setStep(Math.max(0, Math.min(last, to)));
  };

  useHotkeys((key) => {
    if (key === "escape") onClose();
    else if (key === "arrowright") go(step + 1);
    else if (key === "arrowleft") go(step - 1);
    else if (key === "p") setPlaying((p) => !p);
    else return false;
    return true;
  });

  return (
    <div className="xray-backdrop" role="dialog" aria-modal="true" aria-label="X-ray">
      <div className="xray">
        {!data ? (
          <p className="xray-loading">Running the real code (live levels call the model)…</p>
        ) : (
          <XrayBody data={data} step={step} onStep={go} />
        )}
        <footer className="xray-controls">
          <button className="btn-ghost" onClick={() => go(step - 1)} disabled={!data || step === 0}>
            Back <kbd>←</kbd>
          </button>
          <button className="btn" onClick={() => go(step + 1)} disabled={!data || step >= last} autoFocus>
            Step <kbd>→</kbd>
          </button>
          <button className="btn-ghost" onClick={() => setPlaying((p) => !p)} disabled={!data}>
            {playing ? "Pause" : "Play all"} <kbd>P</kbd>
          </button>
          <button className="btn-ghost xray-close" onClick={onClose}>
            Close <kbd>Esc</kbd>
          </button>
        </footer>
      </div>
    </div>
  );
}

function XrayBody({ data, step, onStep }: { data: { run: XrayRun; source: XraySource }; step: number; onStep: (i: number) => void }) {
  const { run, source } = data;
  const current = run.steps[step];
  const src = run.sources[current.fn];
  const lines = src.code.replace(/\n$/, "").split("\n");

  return (
    <>
      <header className="xray-head">
        <span className="chip">X-ray · tracing</span>
        <h2>{run.title}</h2>
        <span className={`badge badge-${source}`}>
          {source === "live" ? "Live run" : "Snapshot"} · {run.models.join(", ") || "no model"}
        </span>
      </header>

      <div className="xray-body">
        <div className="xray-code">
          <div className="xray-file">system.py · {current.fn}()</div>
          <pre>
            {lines.map((text, i) => {
              const lineNo = src.start + i;
              const hot = lineNo === current.line;
              return (
                <div
                  key={lineNo}
                  className={`code-line ${hot ? "code-hot" : ""}`}
                  ref={hot ? (el) => el?.scrollIntoView({ block: "center", behavior: "smooth" }) : undefined}
                >
                  <span className="ln">{lineNo}</span>
                  <code>
                    {highlightLine(text).map((t, j) => (
                      <span key={j} className={t.kind ? `tok-${t.kind}` : undefined}>
                        {t.text}
                      </span>
                    ))}
                  </code>
                </div>
              );
            })}
          </pre>
        </div>

        <div className="xray-trace">
          <ol className="xray-steps">
            {run.steps.map((s, i) => (
              <li key={i}>
                <button className={i === step ? "on" : i < step ? "done" : ""} onClick={() => onStep(i)}>
                  <span className="step-n">{i + 1}</span>
                  {s.label}
                </button>
              </li>
            ))}
          </ol>
          <div className="xray-values">
            <h3>Values at this step</h3>
            <pre>{JSON.stringify(current.values, null, 2)}</pre>
          </div>
        </div>
      </div>
    </>
  );
}
