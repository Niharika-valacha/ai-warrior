import { useContent } from "@/components/ContentProvider";

export type PipelineProps = {
  built: number; // blocks built so far
  fresh?: boolean; // the last block was just added and should glow
  failed?: string; // a wrong pick shown as a broken step
  slot?: boolean; // show the empty "next block" step
};

/** "Your system": the blocks built so far, as a vertical pipeline. */
export function SystemPipeline({ built, fresh, failed, slot }: PipelineProps) {
  const { levels } = useContent();
  return (
    <section className="panel" aria-label="Your system">
      <h2 className="panel-title">Your system</h2>
      <ol className="pipeline">
        {levels.slice(0, built).map((l, i) => {
          const last = i === built - 1;
          return (
            <li key={l.block} className={`node ${last && fresh ? "node-new" : ""}`}>
              <span className="node-name">{l.block}</span>
              {last &&
                l.blockLines.map((t) => (
                  <span key={t} className="node-detail">
                    {t}
                  </span>
                ))}
            </li>
          );
        })}
        {failed && (
          <li className="node node-broken">
            <span className="node-name">{failed}</span>
            <span className="node-detail">Failed</span>
          </li>
        )}
        {slot && (
          <li className="node node-slot">
            <span className="node-name">Next block</span>
          </li>
        )}
      </ol>
    </section>
  );
}
