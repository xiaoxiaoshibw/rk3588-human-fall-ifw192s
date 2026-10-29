// Console deep links keep the immutable sid and the requested source frame together.
export function parseLaunch(search: string): { sid: string; frame: number } | null {
  const query = new URLSearchParams(search);
  const sid = query.get('sid');
  const raw = query.get('frame') ?? '0';
  if (!sid || !/^[A-Za-z0-9_-]{1,128}$/.test(sid) || !/^\d+$/.test(raw)) return null;
  const frame = Number(raw);
  return Number.isSafeInteger(frame) ? { sid, frame } : null;
}
