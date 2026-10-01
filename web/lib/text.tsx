import { Fragment, type ReactNode } from "react";

/** Fill {placeholders} in copy from the database, e.g. "{name} has the keyboard". */
export function fill(template: string, vars: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (match, key: string) => (key in vars ? String(vars[key]) : match));
}

/** Render **bold** markers in copy as <strong>. Nothing else is interpreted, so it's safe for any text. */
export function Rich({ text }: { text: string }): ReactNode {
  return text.split("**").map((part, i) => (i % 2 ? <strong key={i}>{part}</strong> : <Fragment key={i}>{part}</Fragment>));
}
