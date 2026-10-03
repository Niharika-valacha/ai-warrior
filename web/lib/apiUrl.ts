/**
 * The API's address as seen from this browser. On the laptop that's localhost; on a phone on the same
 * Wi-Fi it's the laptop's network address, which is whatever host this page was loaded from.
 * Set NEXT_PUBLIC_API_URL when the API lives elsewhere (e.g. once deployed).
 */
export function apiUrl(): string {
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;
  if (typeof window === "undefined") return "http://localhost:8400";
  return `${window.location.protocol}//${window.location.hostname}:8400`;
}
