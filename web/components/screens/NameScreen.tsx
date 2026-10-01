type Props = { name: string; onChange: (name: string) => void; onSubmit: () => void };

export function NameScreen({ name, onChange, onSubmit }: Props) {
  return (
    <form
      className="intro"
      onSubmit={(e) => {
        e.preventDefault();
        if (name.trim()) onSubmit();
      }}
    >
      <label className="intro-label" htmlFor="warrior">
        What should we call you, warrior?
      </label>
      <input
        id="warrior"
        className="name-input"
        value={name}
        maxLength={16}
        autoFocus
        autoComplete="off"
        placeholder="Your name"
        onChange={(e) => onChange(e.target.value)}
      />
      <button className="btn" type="submit" disabled={!name.trim()}>
        Continue
      </button>
    </form>
  );
}
