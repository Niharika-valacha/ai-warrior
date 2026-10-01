// Shapes of the quiz content served by the API (GET /content). An option without `fail` is the right answer.

export type Option = { text: string; correct?: true; fail?: string[]; pun?: string };

export type Level = {
  id: number;
  icon: string;
  alert: string;
  block: string;
  blockLines: string[];
  situation: string[];
  question: string;
  options: Option[];
  run: string[];
  learn: string;
  concept: { name: string; term: string; parts: string; twist: string; line: string };
};

export type Branch = { name: string; unlocked: string[]; locked: string[] };


export type Sidekick = { id: string; name: string; role: string; move: string; think: string };

// On-screen text per screen. Strings may use {name}, {levels} and **bold** (see lib/text.tsx).
export type Copy = {
  intro: { title: string; lede: string; start: string };
  briefing: {
    title: string;
    incidentId: number;
    alert: string;
    problem: string;
    quotes: string[];
    job: string;
    rules: string[];
    start: string;
  };
  reactions: { fail: string; retry: string; shipped: string };
  boss: { taunts: string[]; decoy: string; answer: string };
  tree: { title: string; lede: string; footer: string };
  win: { title: string; lede: string; again: string };
  sidequest: {
    button: string;
    loading: string;
    askPlaceholder: string;
    builtWithTitle: string;
    builtWith: { name: string; what: string }[];
  };
};

export type Content = { levels: Level[]; skillTree: Branch[]; sidekicks: Sidekick[]; copy: Copy };
