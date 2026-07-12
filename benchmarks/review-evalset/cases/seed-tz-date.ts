export function fmt(isoDate: string) {
  return new Date(isoDate).toLocaleDateString("ru-RU");
}
