## Independent Code Review — Session Entry Selection & Backend Eligibility

Verdict: **No high/critical functional defect found.** Core selection, eligibility, dedup, sort, fallback and lifecycle wiring are correct. Two low-severity items and one packaging verification item below.

### Requirements traceability (all verified)
- **Latest-if-no-sid**: `choose()` filters, then descending sort (`a.sid < b.sid ? 1 : …`), returns `list[0]` → newest. `cap_YYYYMMDD_HHMMSS` is fixed-width so lexicographic == chronological. Correct.
- **Honor valid explicit sid**: `found = valid_sid(query) && list.some(s.sid === query)`; only honored when present in the *filtered* (locally loadable) list. Correct.
- **Notice + safe fallback on illegal/unavailable sid**: `explicit && !found` emits "指定 sid 不合法或本地不可用：…" plus "已回退到本地最新会话：…" when a fallback exists. Correct.
- **Backend eligibility** (`human_replay_lib.py:_local_sessions`): `_is_ready_for_load` (meta.json + points.bin both required → excludes meta-only), `not frames` (empty frames), `not size` (empty points), `size % 28` (misaligned binary), `except (OSError, ValueError, TypeError, AttributeError)` (bad JSON → `JSONDecodeError` ⊂ `ValueError`). All four exclusion classes covered. Correct.
- **Duplicate load handlers**: old `els.session` change listener + `refresh_sessions()`/deep-link interval removed from `human_detect.js`; old `sessSel` change listener + `load_local_sessions` + `handle_query_sid` removed from `human_track.html`. Single `SESSION_SELECTION.start` registration per page; programmatic `select.value = sid` does not fire `change`, so no double-load. Correct.
- **Stable sort**: dedup by `seen` guarantees unique sids, so the comparator never ties; ordering is total and deterministic. Correct.
- **Async failure/empty**: `select.disabled = true` set before fetch and only cleared to `!picked.list.length` on success; fetch/format failures hit `.catch` → visible "本地会话发现失败"; empty list → disabled + "没有本地完整可用会话"; `load()` has its own `.catch` → "会话 … 载入失败" (runtime loader errors visible per stated integrity limit). Correct.

### Findings

1. **Low (cosmetic / UX) — `session_selection.js:choose`, empty explicit query.**
   `explicit = query !== null` treats `?sid=` (present, empty string) as an explicit-but-illegal sid, producing the malformed notice `指定 sid 不合法或本地不可用：。` (empty value after the colon).
   *Repro:* open `human_track.html?sid=` (or `human_detect.html?sid=`); notice shows the dangling colon even though the user supplied no sid. No functional impact (fallback still works). Fix: treat `query` falsy as non-explicit (`var explicit = !!query;`).

2. **Low (potential regression) — `human_track.html` load closure `function(sid){ return window.__load_session_sid(sid); }`.**
   The removed `handle_query_sid` polled with `setInterval` for `window.__load_session_sid` to exist before invoking it; the new path invokes it directly from the fetch callback with no readiness guard. If `replay.js` exposes `__load_session_sid` only after async init (the reason the old poll existed), a cold-start `?sid=<valid>` would reject and surface "载入失败：window.__load_session_sid is not a function", with **no automatic retry** (user must reselect).
   *Repro (conditional):* cold-load `human_track.html?sid=<valid local sid>` on a slow init path where the function is not yet defined at fetch resolution. Not confirmable from the pasted evidence (replay.js not shown); if `__load_session_sid` is assigned synchronously at replay.js top level, this is a non-issue. Verify replay.js exposure timing.

3. **Packaging verification (not confirmable from evidence) — add `session_selection.js` to the EXE bundle.**
   Both HTML files now reference `<script src="session_selection.js">`. If the rebuild/publish manifest uses an explicit file list rather than a directory glob, omission causes a 404; because `human_track.html` calls `SESSION_SELECTION.start(...)` *before* binding `detectBtn`, the inline script would throw and disable the remaining UI. No build manifest was provided, so this is a verification item, not a confirmed defect. Also confirm B2 `replay.load` is packaged unmodified (it is not touched by this diff).

### Informational (not defects)
- Backend accepts any `name.startswith("cap_")`, frontend re-validates with strict `^cap_\d{8}_\d{6}$`; malformed dirs are silently dropped by the frontend. Intentional defense-in-depth.
- `_local_sessions` values omit `sid` (keyed dict); rely on the endpoint to inject `sid`/`local` — pre-existing behavior unchanged by this diff.
- `s.error` filter is now effectively dead (backend no longer emits error entries). Harmless.
- Placeholder label differs ("请选择…" initial vs "— 选本地会话 —" after reset) — cosmetic.