// Just enough Python highlighting to read code from the back of a room: comments, strings, keywords.
const TOKEN = /(#.*$)|("""[\s\S]*?"""|f?"(?:[^"\\]|\\.)*"|f?'(?:[^'\\]|\\.)*')|\b(def|return|if|elif|else|for|in|not|and|or|try|except|raise|with|import|from|class|None|True|False|while|is)\b/g;

export type Token = { text: string; kind?: "comment" | "string" | "keyword" };

export function highlightLine(line: string): Token[] {
  const out: Token[] = [];
  let last = 0;
  for (const m of line.matchAll(TOKEN)) {
    if (m.index! > last) out.push({ text: line.slice(last, m.index) });
    out.push({ text: m[0], kind: m[1] ? "comment" : m[2] ? "string" : "keyword" });
    last = m.index! + m[0].length;
  }
  if (last < line.length) out.push({ text: line.slice(last) });
  return out;
}
