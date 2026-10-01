/** The `INC-4248  HALLUCINATION_DETECTED` header used on incident cards. */
export function IncidentTag({ id, alert }: { id: number; alert: string }) {
  return (
    <div className="incident-head">
      <span className="incident-id">INC-{id}</span>
      <span className="incident-alert">{alert}</span>
    </div>
  );
}
