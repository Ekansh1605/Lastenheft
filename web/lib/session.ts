// Tiny helper for the browser-side session ID — stays in localStorage so the
// sidebar history persists across page refreshes.

const KEY = "lastenheft.session_id";

export function getSessionId(): string {
  if (typeof window === "undefined") return "00000000-0000-0000-0000-000000000000";
  let id = window.localStorage.getItem(KEY);
  if (!id) {
    id = crypto.randomUUID();
    window.localStorage.setItem(KEY, id);
  }
  return id;
}

export function newSessionId(): string {
  if (typeof window === "undefined") return "00000000-0000-0000-0000-000000000000";
  const id = crypto.randomUUID();
  window.localStorage.setItem(KEY, id);
  return id;
}
