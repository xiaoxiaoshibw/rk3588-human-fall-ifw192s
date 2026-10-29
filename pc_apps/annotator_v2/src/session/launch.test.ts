import { describe, expect, it } from 'vitest';
import { parseLaunch } from './launch.ts';

describe('console session links', () => {
  it('keeps sid and source frame, defaulting to the first frame', () => {
    expect(parseLaunch('?sid=cap_123&frame=105')).toEqual({ sid: 'cap_123', frame: 105 });
    expect(parseLaunch('?sid=cap_123')).toEqual({ sid: 'cap_123', frame: 0 });
  });
  it('rejects paths, fractional/negative indices and unsafe integers', () => {
    for (const q of ['', '?sid=../cap', '?sid=cap&frame=-1', '?sid=cap&frame=1.5', '?sid=cap&frame=9007199254740992']) {
      expect(parseLaunch(q)).toBeNull();
    }
  });
});
