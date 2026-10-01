type Props = {
  failed: boolean;
  status: string;
  lines: string[]; // only the lines revealed so far
};

/** Dark terminal panel that prints the fail script or the run log. */
export function RunTerminal({ failed, status, lines }: Props) {
  return (
    <div className={`terminal ${failed ? "terminal-fail" : ""}`} aria-live="polite">
      <p className={failed ? "status-fail" : "status-ok"}>{status}</p>
      {lines.map((line, i) => (
        <pre key={i}>{line}</pre>
      ))}
    </div>
  );
}
