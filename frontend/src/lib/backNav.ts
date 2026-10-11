export interface BackNavState {
  from: string;
  label: string;
}

export function resolveBackNav(
  state: unknown,
  fallback: BackNavState,
): BackNavState {
  if (
    state &&
    typeof state === "object" &&
    "from" in state &&
    "label" in state
  ) {
    const candidate = state as { from: unknown; label: unknown };
    if (
      typeof candidate.from === "string" &&
      typeof candidate.label === "string"
    ) {
      return { from: candidate.from, label: candidate.label };
    }
  }
  return fallback;
}
