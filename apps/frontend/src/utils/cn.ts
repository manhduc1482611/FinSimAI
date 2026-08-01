/** Ghép nối các class names một cách an toàn (bỏ qua falsy values). */
export function cn(
  ...classes: Array<string | false | null | undefined>
): string {
  return classes.filter(Boolean).join(" ");
}
