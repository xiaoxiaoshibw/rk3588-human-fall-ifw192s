# GL-I04 offline diagnostic

physical_verified=false; recording extrinsic unknown.
Source XYZ projections and oriented model residuals; high/low tails have no physical identity.
Actual frozen fit, independent replay and posthoc holdout are separate JSON fields.

| hypothesis | native status/reason | sample | native validation | PCA angle |
|---|---|---|---|---|
| approved | invalid / ground_degenerate | 1193 | False | 52.281327 |
| WHAT_IF_negative_X | orientation_unverified / ground_competition_unresolved | 1214 | False | 0.316787 |
| WHAT_IF_FIT_PCA_normal | orientation_unverified / ground_competition_unresolved | 1214 | False | 0.000000 |

## Full fixed-box temporal observations

```json
{
  "FIT": {
    "frames": 89,
    "nonempty_frames": 89,
    "signed_median_std_m": 0.0003110996273260611
  },
  "v1": {
    "frames": 89,
    "nonempty_frames": 89,
    "signed_median_std_m": 0.00043510260457397225
  },
  "v2": {
    "frames": 89,
    "nonempty_frames": 89,
    "signed_median_std_m": 0.0009513174889822207
  },
  "v3": {
    "frames": 89,
    "nonempty_frames": 89,
    "signed_median_std_m": 0.0005428366208185939
  }
}
```

No pooled fit or residual filtering of validation. All selected rows are in source_indices.jsonl.
Display stride indices and full statistics are separately recorded. Inspect local_source.svg point titles.
