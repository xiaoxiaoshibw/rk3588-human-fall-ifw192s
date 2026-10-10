Read-only review, no execution performed.

## Verdict

The direction is right: making the new Console server opt out of `SO_REUSEADDR` and falling back to an ephemeral port is the correct shape of the fix, and the regression test's use of a *real* occupied socket (rather than a mocked `OSError`) is the right call. But there are real, actionable defects — the most important being that `allow_reuse_address = False` is a weaker guarantee than it looks on Windows.

## Actionable defects

1. **`allow_reuse_address = False` ≠ "fail if the port is owned" on Windows (primary).** The whole fix rests on the Windows rule that a second `bind()` to an in-use port fails unless the *binding* socket sets `SO_REUSEADDR`. That is the documented asymmetric behavior, but it is exactly the scenario Windows is notorious for getting wrong, and the fix has no belt-and-suspenders. The robust primitive is `SO_EXCLUSIVEADDRUSE` (set on the socket before `bind`), which guarantees `WSAEADDRINUSE` when *any* listener owns the address regardless of the peer's options. `socketserver` never sets it. If the old Python service has `SO_REUSEADDR` (standard `HTTPServer` does), and the kernel ever honors the peer's flag, the new bind silently succeeds, `except OSError` never runs, and requests keep landing on the old service — the exact bug being fixed. Recommend: in `ReplayServer.server_bind`, call `TCPServer.server_bind`, but pre-set `SO_EXCLUSIVEADDRUSE` on the socket (`Windows`-only), keeping the port-0 fallback.

2. **`except OSError` is too broad.** It swallows *every* bind failure (bad address, bad `PORT`, permission, invalid socket) and silently degrades to a random port, masking misconfiguration. Narrow it to the address-in-use case (`getattr(e, "winerror", None) == 10048` / `errno.EADDRINUSE`); re-raise otherwise.

3. **The regression test only actually exercises the fix on Windows.** On POSIX, `SO_REUSEADDR` cannot steal a live listener, so the *pre-fix* code (reuse enabled) also fails to double-bind, the fallback still runs, and the assertion still passes. If CI runs this on Linux/macOS it gives false green and will not catch a future revert of the fix. Gate it to Windows (or assert the pre-condition that `H.ThreadingHTTPServer.allow_reuse_address` is truthy) so the test is a real guard only where it is meaningful.

4. **Behavior change on restart: 8901 is no longer reclaimed from `TIME_WAIT`.** With reuse disabled, restarting the Console shortly after exit will fail the 8901 bind (lingering `TIME_WAIT`) and fall back to a random port, where the old code reused 8901. Not incorrect per the "occupied → random port" requirement, but it means 8901 is only used on a truly cold start. Confirm nothing (bookmark, hardcoded iframe URL, operator docs) assumes 8901.

5. **Verify the caller consumes the returned port.** The function returns `srv.server_address[1]`, but if the Console iframe / any other code path hardcodes `http://127.0.0.1:8901`, the fallback silently points the UI at the old service. This is the integration seam where defect #1 would manifest as "requests route to the old service." Not visible in the excerpt — flag for confirmation.

6. **Brittle test assertions (minor).** `assertIn(b'"sessions": []', ...)` couples to exact JSON spacing; `/leveling.html` hard-fails if the asset/handler path changes. Prefer parsing JSON and asserting the empty list.

## Confirmed correct

- Subclassing to scope `allow_reuse_address = False` (instead of mutating the shared module class) is right.
- `TCPServer.__init__` closes the socket when the first `bind` raises, and `TrackedServer` only appends after `super().__init__` succeeds, so the failed first attempt leaks no socket and is not double-shut-down.
- `ReplayServer` forced-`False` overrides `TrackedServer`'s inherited `True`, so the test does fail if the subclass is reverted *on Windows* — the guard is real there.
- Binding the fallback to `("127.0.0.1", 0)` is safe against further collisions.

I did not run any tests or code.