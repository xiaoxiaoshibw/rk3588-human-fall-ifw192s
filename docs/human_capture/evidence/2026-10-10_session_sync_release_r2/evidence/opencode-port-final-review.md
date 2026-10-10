## Remaining actionable defect

**`test_unrelated_socket_error_is_not_hidden_by_fallback` is vacuous — it cannot detect the regression it claims to guard.**

`InvalidServer` raises `OSError(EINVAL)` for *every* address. Consider removing the errno filter (the exact code under test):

- Default-port attempt raises `EINVAL` → caught →
- Fallback `ReplayServer(("127.0.0.1", 0))` also raises `EINVAL` →
- Propagates, `errno == EINVAL`.

The test still passes. So it proves nothing about whether unrelated errors are re-raised vs. hidden by fallback. The test must distinguish the two paths, e.g.:

- Make the invalid server raise only for the default port and **succeed on port 0**, then assert `assertRaises(OSError)` — a wrongful fallback would return normally (fail) instead of raising.
- Or count constructor invocations: assert exactly **one** attempt was made (plus a flag that the fallback would be observable).

Without this, a regression deleting `if ...: raise` (or broadening the allowlist) ships green.

## Minor / secondary

1. **Reuse assertion is only an attribute proxy.** `assertFalse(servers[0].allow_reuse_address)` checks the class attribute, not the socket. A regression that calls `setsockopt(SO_REUSEADDR, 1)` while leaving the attribute `False` (or a platform defaulting reuse on) would slip through. Assert the actual option: `getsockopt(SOL_SOCKET, SO_REUSEADDR) == 0` on the bound socket.

2. **Unused `origin`** from `replay_dir, origin = _replay_dir()` — dead binding; drop it or use it.

## Assessment of the production fix

Functionally sound for the stated goal:

- `SO_EXCLUSIVEADDRUSE` is set **before** `super().server_bind()` (which does the actual `bind`), and `allow_reuse_address = False` prevents the base from re-enabling `SO_REUSEADDR`. Correct ordering.
- The filter `errno not in (EADDRINUSE, EACCES) and winerror not in (10048, 10013)` correctly handles Windows WSA codes (where `.winerror` carries the raw `WSAEADDRINUSE`/`WSAEACCES`), including reserved/excluded-port denial (10013). EINVAL and other errors re-raise.
- Fallback to port 0, returning `srv.server_address[1]`, is consistent with the shell/HTML `replay_port` plumbing described.

No algorithmic/data changes; no execution claimed.

**Bottom line:** one blocking test defect (vacuous EINVAL test) plus two minor cleanups. The server-side logic itself has no remaining actionable defect.