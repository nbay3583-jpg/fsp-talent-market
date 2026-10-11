import { useSyncExternalStore } from "react";

/** Active cabinet tab, published by Shell so the helper can offer page-specific questions. Display-only. */
let page: string | null = null;
const subs = new Set<() => void>();

export function setAssistantPage(next: string | null) {
  if (next === page) return;
  page = next;
  subs.forEach((f) => f());
}

export function useAssistantPage(): string | null {
  return useSyncExternalStore((cb) => { subs.add(cb); return () => { subs.delete(cb); }; }, () => page, () => null);
}
