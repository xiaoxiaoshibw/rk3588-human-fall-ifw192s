# GL-P01 additive `coordinate.ground` message contract

Status: R1 software. Additive to the v1 `candidate_snapshot`; no existing field
changes meaning, no new top-level block. Consumed by the existing
`parseGroundRender` in `webui/human_fall_preview/human_fall_lib.js`.

## Producer

`build_snapshot` publishes `snapshot.coordinate.ground`:

- `null` when no strictly validated embedded `ground_derived` is bound to the
  actual producing frame (legacy/none/ground-only/foreign-frame/damaged
  artifact). Never a `normal`-derived or identity fallback.
- otherwise a whitelist projection of the canonical block:
  `kind="coordinate_ground"`, `schema_version=1` (owns the key),
  `from_frame`, `to_frame="ground_local"`, `units="m"`,
  `calibration_id`, `geometry_schema_version`, `ground_derived_id`,
  `R` (fresh 3x3 list), `t` (fresh 3-list). No artifact evidence/region/source
  fields are copied.

The `R`/`t` lists are newly built per snapshot; the validated artifact
(`_validated_ground_derived` re-validates a deepcopy) and the cached selection
snapshot are never mutated by projection. `project_snapshot_for_ros` keeps its
existing nested shallow-copy and only drops per-candidate `evidence_indices`.

## Support

`snapshot.ground` (only when a ground summary exists) carries
`support_polygon=null`, `support_polyline=null` and a non-empty
`support_reason`. An auto AABB / trusted ROI is deliberately **not** promoted to
a support outline; the preview reports `support.status="unavailable"`.

## Consumer qualification

`parseGroundRender` reads `coordinate.ground` (authoritative) and requires:
`kind` in `{coordinate_ground, ground_render}`, `schema_version=1`,
`from_frame==source.frame_id==coordinate.source_frame`, `to_frame="ground_local"`,
`units="m"`, orthonormal `R` with det +1, triple `t`,
`calibration.schema_version=1`, `calibration_id` match, `ground_derived_id`
match against `coordinate` and `calibration`, optional `geometry_schema_version`
match, and `ground_status="valid"`. Otherwise `unavailable`/`invalid`/
`unqualified`/`unsupported` — never a fabricated transform.
