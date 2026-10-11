export function stripCorrectPrefix(
  explanation: string,
  isCorrect: boolean,
  isSelected: boolean,
): string {
  if (isCorrect && !isSelected) {
    return explanation.replace(/^Correct — /, "");
  }
  return explanation;
}
