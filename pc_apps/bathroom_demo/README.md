# bathroom_demo — IFW192S range-image + tracking + HMM fall state

Standalone PC demo for the bathroom small-scene direction. It does **not** import
ROS, does not touch the production pipeline, and does not claim a bathroom
result. Its purpose is to make the algorithm inspectable before the first
bathroom capture.

## What it does

```
PointCloud2 / points.bin (x,y,z,intensity,ring,timestamp)
  → fixed 192×240 range image
  → per-ray background (median/MAD from an empty prefix)
  → residual foreground + depth-edge suppression
  → 2D components with depth-continuity (not a fixed metric voxel)
  → 3D lift, range-adaptive fragment merge
  → constant-velocity tracker
  → per-track height / span / inclination / count / range
  → rule state machine + 5-state causal HMM
```

The HMM is intentionally small: 5 states (`upright`, `sitting`, `descending`,
`lying`, `recovering`) and factorised categorical emissions over height, span,
vertical velocity and inclination. It can run with hand-set priors; `fit_hmm`
only counts transitions/emissions with Laplace smoothing. That is the
"geometric features + Markov model" baseline, not a point-cloud network.

## Run

```powershell
python -B pc_apps/bathroom_demo/make_demo.py `
  --session data/sessions/cap_20261018_110029 `
  --transform docs/human_fall/evidence/2026-10-18_hfus_project_dev_r1/leveling_02/TRANSFORM.json `
  --out docs/evidence/2026-10-23_bathroom_demo
```

Open `docs/evidence/2026-10-23_bathroom_demo/index.html` directly (file://
works; no server). It has two players:

1. **Real session** — `cap_20261018_110029`, 386 frames, person at ~2 m. No
   fall. Shows range image, foreground, target, BEV trail, rule state, HMM state
   and `p(lying)`.
2. **Synthetic capsule fall** — real empty background + a crude capsule body
   rotated to the floor. This is an algorithm test, **not a human and not a
   capture**. It shows a fall candidate and long-lie candidate firing.

Tests:

```powershell
python -B -W error -m unittest discover -s pc_apps/bathroom_demo -p "test_*.py"
```

## Measured on this demo (not bathroom performance)

| | real session | synthetic capsule |
|---|---:|---:|
| frames | 386 | 120 |
| target present | 281 (72.8%) | 119 (99.2%) |
| target points (median) | 2,423 | 394 |
| target range (median) | 2.028 m | 1.817 m |
| rule state | 259 upright, 12 low_support, 0 fall | fall ~34–35, long lie ~81–85 |
| HMM state | 260 upright, 0 fall, 0 long lie | fall ~34–35, long lie ~81–85 |
| HMM `p(lying)` false alarm | 0 | — |
| front-end latency (PC) | P50 16.7 ms / P95 23.9 ms | P50 14.9 ms / P95 20.1 ms |

The real session's target (2,423 points at 2.03 m) matches the existing
production chain's 2,385 points at 2.01 m within ~2%. That is the useful
sanity check: the range front-end does not throw the person away at 2 m.

## Why the real session has no fall

It contains a person moving/standing, then leaving; there is no fall. The rule
and HMM both stay upright/low-support. At the end, only a 570-point partial
fragment remains; the visible-ratio gate marks it `low_support` instead of
inventing a fall. That behavior is deliberate.

## What this proves / does not prove

**Proves (software/geometry):**

- the fixed 192×240 grid and per-ray background are implementable in NumPy;
- the front-end keeps the 2 m target at production-comparable density;
- the tracker and both state layers run causally at ~20 ms/frame on PC;
- a known height collapse (capsule) produces `fall_suspected` and
  `long_lie_suspected`, while the real no-fall session produces neither.

**Does not prove:**

- bathroom recall or false-alarm rate: there is **no bathroom capture** here;
- human fall detection: the fall is a capsule, not a person;
- that the hand-set HMM priors transfer to another bathroom/person;
- board latency: numbers are PC, Python 3.12, not RK3588/Python 3.8.

The existing 21 sessions are a 2 m room, not a bathroom. The bathroom
background/fixture/curtain/steam template must be captured separately
(see [BATHROOM_FALL_CAPTURE_PROTOCOL.md](../../docs/BATHROOM_FALL_CAPTURE_PROTOCOL.md)).

## Files

| file | role |
|---|---|
| `range_pipeline.py` | grid, background, foreground, components, tracker, rule state, synthetic scenes |
| `fall_hmm.py` | 5-state causal HMM, hand priors, count-fit, save params |
| `make_demo.py` | render frames, HTML player, metrics, contact sheet |
| `test_range_pipeline.py` | 14 unit tests (grid, residual, depth split, tracker, HMM, ground) |
| `docs/evidence/2026-10-23_bathroom_demo/` | generated demo, `SUMMARY.json`, `metrics_*.csv`, contact sheet |

## Next steps (software, before/with the bathroom pilot)

1. Replace the fixed `1.40, 1.20` capsule placement with a per-bathroom ROI and
   fixture mask (toilet / tub / curtain / glass).
2. Capture the bathroom empty template (curtain open/closed) and measure
   invalid-return / edge rates with water and steam.
3. Run the same front-end on the bathroom pilot; fit the HMM transitions/
   emissions from the 3-person pilot (`fit_hmm`), then test on held-out people.
4. Keep the rule state and HMM as two challengers; do not promote either to
   `confirmed` without independent bathroom events and a long-term ADL run.

## Relationship to the W1 front-end

The repo's W1 front-end (`src/human_fall_detection/core/range_image.py`,
`docs/RANGE_FRONTEND_W1.md`) uses the calibrated **192×256** direction table and
keeps per-cell source rows. This demo uses a **192×240 equal-angle
approximation** for speed and simple visualisation. It is not the production
measurement core; at 2 m the difference is small (2,423 vs W1's ~2,402 median
points), but the tracker/HMM must be ported onto W1 frames before deployment.
The W1 `ScanGrid`, `RayBackground`, `denoise`, `label_components` files were not
modified by this demo.

## Honest boundary

A small HMM reduces data needs; it does not remove the need for independent
bathroom events and long-term false-alarm validation. The pilot budget
(3 people / 18 falls / 60 negatives) is a budget, not a reliability guarantee.