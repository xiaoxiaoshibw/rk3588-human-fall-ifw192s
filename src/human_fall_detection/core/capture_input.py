"""GL-I01 offline capture-input adaptation: source export -> numeric NPZ.

This module is pure stdlib + NumPy (Python 3.8, no ROS, no replay service, no
capture server import). It reads an existing ``human_capture_session`` export
(``meta.json`` + ``points.bin``) strictly read-only, rebuilds the canonical
source XYZ bytes and writes a *new* numeric NPZ holding exactly two arrays:

- ``points``: the raw little-endian ``<f4`` ``(N,3)`` source XYZ, and
- ``input_manifest``: a scalar Unicode JSON string describing the source
  identity, layout, ordered frames, deterministic per-frame group ids and the
  honest provenance flags.

Every declaration stays ``metadata_declared``; every physical flag stays
``false``. Nothing here fits a ground plane, selects an ROI or claims a unit or
installation. The original bag point index is unknown and never fabricated.
"""

import hashlib
import json
import os
import tempfile

import numpy as np

MANIFEST_KEY = "input_manifest"
FORMAT = "human_capture_session"
FORMAT_VERSION = 1
TOOL = "bag2session/0.1.0"
SCHEMA = 1
KIND = "capture_input_adaptation"
POINT_STRIDE_BYTES = 28
UNITS = "m"
ROW_DTYPE = np.dtype([
    ("x", "<f4"),
    ("y", "<f4"),
    ("z", "<f4"),
    ("intensity", "<f4"),
    ("ring", "<u2"),
    ("_pad1", "<u2"),
    ("timestamp", "<f4"),
    ("_pad2", "<f4"),
])
assert ROW_DTYPE.itemsize == POINT_STRIDE_BYTES
EXPECTED_LAYOUT = {
    "fields": ["x", "y", "z", "intensity", "ring", "timestamp"],
    "dtypes": ["<f4", "<f4", "<f4", "<f4", "<u2", "<f4"],
    "stride_bytes": POINT_STRIDE_BYTES,
    "endian": "little",
    "pad_offsets_bytes": [18, 24],
}
_FRAME_INT_KEYS = ("seq", "stamp_sec", "stamp_nanosec", "offset_points",
                   "count_points", "dropped_points")


class CaptureInputError(ValueError):
    """Any malformed/refused capture adaptation input."""


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_snapshot(path, name):
    """Read one file once; return ``(raw_bytes, sha256_hex)`` of the same bytes.

    Both the digest and any later parse must come from this single snapshot so
    a hash and a decode can never observe different file contents.
    """
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except OSError as exc:
        raise CaptureInputError("cannot read %s %s: %s" % (name, path, exc))
    return raw, hashlib.sha256(raw).hexdigest()


def _require(condition, message):
    if not condition:
        raise CaptureInputError(message)


def _strict_int(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        raise CaptureInputError(name + " must be an integer")
    return int(value)


def _load_json(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError) as exc:
        raise CaptureInputError("cannot read JSON " + str(path) + ": " + str(exc))


def _parse_json_bytes(raw, name):
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise CaptureInputError("cannot parse " + name + " JSON: " + str(exc))


def classify_npz(path):
    """Return ``"adapted"`` or ``"legacy"`` for an input path by *content*.

    Detection is on the archive keys, never the file name: ``np.load`` accepts
    a renamed ``.npy``/``.dat`` or a ``PathLike``, so a suffix guard would miss
    (or wrongly reject) real inputs. A file that carries the manifest key but
    is damaged is *never* silently treated as a legacy array: it raises so a
    caller cannot bypass the strict adapted route. A non-NPZ or manifest-free
    input is ordinary legacy input.
    """
    try:
        loaded = np.load(os.fspath(path), allow_pickle=False)
    except Exception:
        return "legacy"
    if not isinstance(loaded, np.lib.npyio.NpzFile):
        return "legacy"
    files = list(loaded.files)
    loaded.close()
    if MANIFEST_KEY not in files:
        return "legacy"
    return "adapted"


def _reject_extra_keys(files):
    _require(sorted(files) == sorted(("points", MANIFEST_KEY)),
             "adapted NPZ must contain exactly points and " + MANIFEST_KEY +
             ", got " + repr(sorted(files)))


def _read_manifest(npz_path):
    loaded = np.load(os.fspath(npz_path), allow_pickle=False)
    try:
        _reject_extra_keys(loaded.files)
        if MANIFEST_KEY not in loaded.files:
            raise CaptureInputError("NPZ has no " + MANIFEST_KEY + " key")
        raw = loaded[MANIFEST_KEY]
    finally:
        loaded.close()
    _require(raw.dtype == np.dtype("U") or raw.dtype.kind == "U",
             "input_manifest must be a Unicode string array")
    _require(raw.ndim == 0,
             "input_manifest must be a scalar Unicode string")
    try:
        manifest = json.loads(str(raw.reshape(()).item()))
    except ValueError as exc:
        raise CaptureInputError("input_manifest is not valid JSON: " + str(exc))
    _require(isinstance(manifest, dict), "input_manifest must decode to an object")
    return manifest


def _validate_layout(layout):
    _require(isinstance(layout, dict), "point_layout must be an object")
    for key, expected in EXPECTED_LAYOUT.items():
        _require(layout.get(key) == expected,
                 "point_layout.%s mismatch" % key)


def read_source_meta(meta_raw, declared_frame, declared_units):
    """Validate a source ``meta.json`` snapshot; return the dict.

    ``meta_raw`` are the exact bytes whose digest is bound into the manifest,
    so the declaration checks and the identity hash share one snapshot.
    """
    _require(isinstance(declared_frame, str) and declared_frame,
             "declared frame must be a non-empty string")
    _require(declared_units == UNITS,
             "declared units must be " + repr(UNITS) + " (no implicit mm)")
    meta = _parse_json_bytes(meta_raw, "meta.json")
    _require(isinstance(meta, dict), "meta.json must be an object")
    _require(meta.get("format") == FORMAT,
             "unsupported source format: " + repr(meta.get("format")))
    version = meta.get("format_version")
    _require(not isinstance(version, bool) and isinstance(version, (int, np.integer))
             and int(version) == FORMAT_VERSION,
             "unsupported source format_version")
    _validate_layout(meta.get("point_layout"))
    _require(meta.get("point_file") == "points.bin",
             "source point_file must be points.bin")
    stride = meta.get("point_stride_bytes")
    _require(not isinstance(stride, bool) and isinstance(stride, (int, np.integer))
             and int(stride) == POINT_STRIDE_BYTES,
             "source point_stride_bytes must be %d" % POINT_STRIDE_BYTES)
    sensor = meta.get("sensor")
    _require(isinstance(sensor, dict), "source sensor must be an object")
    frame_id = sensor.get("frame_id")
    _require(isinstance(frame_id, str) and frame_id,
             "source sensor.frame_id must be a non-empty string")
    _require(frame_id == declared_frame,
             "declared frame %r disagrees with source sensor.frame_id %r"
             % (declared_frame, frame_id))
    for container, label in ((sensor, "sensor.units"), (meta, "meta.units")):
        units = container.get("units")
        if units is not None:
            _require(units == declared_units,
                     "declared units disagree with a recorded source unit in "
                     + label)
    extraction = meta.get("extraction")
    _require(isinstance(extraction, dict), "source extraction must be an object")
    _require(extraction.get("tool") == TOOL,
             "unsupported extraction tool: " + repr(extraction.get("tool")))
    _require(extraction.get("point_step_bytes_src") == 26,
             "unexpected source point_step_bytes_src")
    time_domain = meta.get("time_domain")
    _require(isinstance(time_domain, str) and time_domain,
             "source time_domain must be a non-empty string")
    return meta


def validate_frames(meta):
    """Return the strictly-typed ordered frame list; reject any inconsistency."""
    frames = meta.get("frames")
    _require(isinstance(frames, list), "source frames must be a list")
    _require(frames, "source frames must not be empty")
    extraction = meta.get("extraction") or {}
    dropped_frames = _strict_int(extraction.get("dropped_frames"),
                                 "extraction.dropped_frames")
    _require(dropped_frames == 0, "source has dropped frames")
    total_dropped = _strict_int(meta.get("total_dropped_points"),
                                "total_dropped_points")
    _require(total_dropped == 0, "source reports dropped points")
    cleaned = []
    expected_offset = 0
    for index, frame in enumerate(frames):
        _require(isinstance(frame, dict), "frame %d must be an object" % index)
        values = {}
        for key in _FRAME_INT_KEYS:
            values[key] = _strict_int(frame.get(key), "frame %d.%s" % (index, key))
        _require(values["seq"] >= 0, "frame %d.seq must be non-negative" % index)
        _require(values["stamp_sec"] >= 0,
                 "frame %d.stamp_sec must be non-negative" % index)
        _require(0 <= values["stamp_nanosec"] < 1000000000,
                 "frame %d.stamp_nanosec must be in [0, 1e9)" % index)
        _require(values["count_points"] >= 0,
                 "frame %d.count_points must be non-negative" % index)
        _require(values["dropped_points"] == 0,
                 "frame %d has dropped points" % index)
        _require(values["offset_points"] == expected_offset,
                 "frame %d offset is not contiguous" % index)
        expected_offset += values["count_points"]
        bag_time = frame.get("bag_time_sec")
        _require(isinstance(bag_time, (int, float)) and not isinstance(bag_time, bool),
                 "frame %d.bag_time_sec must be numeric" % index)
        values["bag_time_sec"] = float(bag_time)
        cleaned.append(values)
    total_points = _strict_int(meta.get("total_points"), "total_points")
    _require(total_points == expected_offset,
             "source total_points disagrees with the frame counts")
    return cleaned


def canonical_source_xyz(frames, bin_raw):
    """Rebuild the canonical source XYZ from the bin bytes snapshot.

    Returns ``(points, raw_bytes)`` where ``points`` is ``(N,3) <f4`` in
    original frame/row order (zero returns kept) and ``raw_bytes`` are the
    exact little-endian ``<f4`` XYZ bytes used for the content digest. The
    digest and the decoded points therefore always come from the same snapshot.
    """
    expected_size = sum(frame["count_points"] for frame in frames) \
        * POINT_STRIDE_BYTES
    raw = np.frombuffer(bin_raw, dtype=np.uint8)
    _require(raw.size == expected_size,
             "points.bin size %d disagrees with the declared %d bytes"
             % (raw.size, expected_size))
    rows = raw.reshape(-1, POINT_STRIDE_BYTES)
    points = rows[:, 0:12].copy().view("<f4").reshape(-1, 3)
    _require(np.all(np.isfinite(points)),
             "actual source contains a non-finite XYZ row; a zero-drop "
             "bag2session/0.1.0 export is finite and is refused whole rather "
             "than silently filtered or reindexed")
    return points, points.tobytes()


def source_identity(meta_sha256, bin_sha256):
    """Path-independent source content identity."""
    return hashlib.sha256(
        (bin_sha256 + "|" + meta_sha256).encode("ascii")).hexdigest()


def frame_group_id(identity, ordinal, frame):
    payload = "|".join((identity, str(ordinal), str(frame["seq"]),
                        str(frame["stamp_sec"]), str(frame["stamp_nanosec"])))
    return "frame:" + hashlib.sha256(payload.encode("ascii")).hexdigest()[:24]


def build_manifest(meta, frames, meta_sha256, bin_sha256, bin_size_bytes,
                   points_sha256, frame, units):
    """Assemble the manifest dict from one consistent source snapshot set."""
    identity = source_identity(meta_sha256, bin_sha256)
    groups = {}
    for ordinal, fr in enumerate(frames):
        gid = frame_group_id(identity, ordinal, fr)
        start = fr["offset_points"]
        groups[gid] = {
            "ordinal": ordinal,
            "seq": fr["seq"],
            "stamp_sec": fr["stamp_sec"],
            "stamp_nanosec": fr["stamp_nanosec"],
            "rows": [start, start + fr["count_points"]],
        }
    return {
        "schema": SCHEMA,
        "kind": KIND,
        "source": {
            "format": FORMAT,
            "format_version": FORMAT_VERSION,
            "tool": TOOL,
            "meta_path": os.path.abspath(meta["_meta_path"]),
            "bin_path": os.path.abspath(meta["_bin_path"]),
            "meta_sha256": meta_sha256,
            "bin_sha256": bin_sha256,
            "bin_size_bytes": int(bin_size_bytes),
            "total_points": int(sum(fr["count_points"] for fr in frames)),
            "total_dropped_points": 0,
            "source_bag_sha256_declared":
                (meta.get("extraction") or {}).get("source_bag_sha256"),
            "source_bag_hash_verified": False,
        },
        "layout": dict(EXPECTED_LAYOUT),
        "frames": [dict({"ordinal": ordinal}, **fr)
                   for ordinal, fr in enumerate(frames)],
        "frame_groups": groups,
        "points": {
            "key": "points",
            "dtype": "<f4",
            "shape": [int(sum(fr["count_points"] for fr in frames)), 3],
            "sha256": points_sha256,
        },
        "declared": {
            "frame": frame,
            "frame_provenance": "metadata_declared",
            "units": units,
            "units_provenance": "metadata_declared",
            "time_domain": meta.get("time_domain"),
        },
        "provenance": {
            "point_index_domain": "capture_export_row",
            "original_bag_point_index": "unknown",
            "source_bag_hash_verified": False,
            "physical_verified": False,
        },
    }


def _canonical_json(value):
    """Type-stable canonical JSON so bool/float cannot equal an int."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def prepare_npz(source_dir, frame, units, output):
    """Build the adapted NPZ atomically (exclusive hard-link publish only)."""
    _require(os.path.isdir(source_dir),
             "source dir does not exist: " + str(source_dir))
    meta_path = os.path.join(source_dir, "meta.json")
    bin_path = os.path.join(source_dir, "points.bin")
    if os.path.islink(meta_path):
        meta_path = os.path.realpath(meta_path)
    if os.path.islink(bin_path):
        bin_path = os.path.realpath(bin_path)
    _require(os.path.isfile(meta_path), "source meta.json not found")
    _require(os.path.isfile(bin_path), "source points.bin not found")
    meta_raw, meta_sha256 = read_snapshot(meta_path, "meta.json")
    bin_raw, bin_sha256 = read_snapshot(bin_path, "points.bin")
    meta = read_source_meta(meta_raw, frame, units)
    meta["_meta_path"] = meta_path
    meta["_bin_path"] = bin_path
    frames = validate_frames(meta)
    points, raw_bytes = canonical_source_xyz(frames, bin_raw)
    points_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    manifest = build_manifest(meta, frames, meta_sha256, bin_sha256,
                              len(bin_raw), points_sha256, frame, units)
    _publish_npz(points, manifest, output)
    return manifest


def _publish_npz(points, manifest, output):
    link = getattr(os, "link", None)
    _require(callable(link),
             "atomic exclusive NPZ publish requires os.link (no fallback copy)")
    target = os.path.abspath(output)
    directory = os.path.dirname(target) or "."
    os.makedirs(directory, exist_ok=True)
    if os.path.exists(target):
        raise CaptureInputError("output already exists: " + target)
    handle = tempfile.NamedTemporaryFile(dir=directory, prefix=".gli01-",
                                         suffix=".npz", delete=False)
    temporary = handle.name
    handle.close()
    try:
        with open(temporary, "wb") as destination:
            np.savez(destination, points=points,
                     input_manifest=np.array(json.dumps(manifest, ensure_ascii=False,
                                                        allow_nan=False)))
            destination.flush()
            os.fsync(destination.fileno())
        try:
            link(temporary, target)
        except FileExistsError:
            raise CaptureInputError("output already exists: " + target) from None
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _strict_indices(values, name, limit):
    if isinstance(values, np.ndarray):
        if values.dtype.kind == "b" or values.dtype.kind not in "iu":
            raise CaptureInputError(name + " must be integer row indices")
        items = values.tolist()
    elif isinstance(values, (list, tuple)):
        items = list(values)
    else:
        raise CaptureInputError(name + " must be a 1-D integer index sequence")
    for item in items:
        if isinstance(item, bool) or not isinstance(item, (int, np.integer)):
            raise CaptureInputError(name + " must be integer row indices")
    array = np.asarray(items, dtype=np.int64)
    if array.ndim != 1:
        raise CaptureInputError(name + " must be a 1-D index array")
    if len(array) and (int(array.min()) < 0 or int(array.max()) >= limit):
        raise CaptureInputError(name + " contains an out-of-range row index")
    return np.unique(array)


def _load_source_snapshot(manifest):
    """Read the actual source once and rebuild the normative canonical manifest.

    The digest, declaration parse and XYZ decode all come from the same two
    byte snapshots, so a tampered bundle cannot self-rehash to a passing state.
    """
    source = manifest.get("source")
    _require(isinstance(source, dict), "manifest source must be an object")
    _require(source.get("format") == FORMAT, "manifest source format mismatch")
    _require(source.get("tool") == TOOL, "manifest source tool mismatch")
    meta_path, bin_path = source.get("meta_path"), source.get("bin_path")
    _require(isinstance(meta_path, str) and os.path.isfile(meta_path),
             "manifest source meta is unreachable")
    _require(isinstance(bin_path, str) and os.path.isfile(bin_path),
             "manifest source points.bin is unreachable")
    meta_raw, meta_sha256 = read_snapshot(meta_path, "meta.json")
    bin_raw, bin_sha256 = read_snapshot(bin_path, "points.bin")
    _require(meta_sha256 == source.get("meta_sha256"),
             "source meta.json changed since adaptation")
    _require(bin_sha256 == source.get("bin_sha256"),
             "source points.bin changed since adaptation")
    frame = (manifest.get("declared") or {}).get("frame")
    units = (manifest.get("declared") or {}).get("units")
    meta = read_source_meta(meta_raw, frame, units)
    meta["_meta_path"] = meta_path
    meta["_bin_path"] = bin_path
    frames = validate_frames(meta)
    points, raw_bytes = canonical_source_xyz(frames, bin_raw)
    points_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    canonical = build_manifest(meta, frames, meta_sha256, bin_sha256,
                               len(bin_raw), points_sha256, frame, units)
    return canonical, points, raw_bytes


def load_adapted(npz_path):
    """Load and fully verify an adapted NPZ against its actual source export.

    The whole normative manifest is recomputed from one actual-source snapshot
    and compared as type-stable canonical JSON (so a stored bool/float can never
    pass where the canonical int is expected). The NPZ ``points`` raw ``<f4``
    bytes must equal the actual source XYZ bytes and their digest; extra or
    contradictory metadata is refused. Any mismatch raises (never a legacy
    fallback).
    """
    manifest = _read_manifest(npz_path)
    _require(isinstance(manifest, dict), "manifest must decode to an object")
    canonical, source_points, raw_bytes = _load_source_snapshot(manifest)
    _require(_canonical_json(manifest) == _canonical_json(canonical),
             "manifest is not the canonical manifest of its actual source")
    loaded = np.load(os.fspath(npz_path), allow_pickle=False)
    try:
        _reject_extra_keys(loaded.files)
        points = loaded["points"]
    finally:
        loaded.close()
    _require(isinstance(points, np.ndarray) and points.dtype == np.dtype("<f4"),
             "NPZ points must be little-endian <f4")
    _require(points.ndim == 2 and points.shape == tuple(canonical["points"]["shape"]),
             "NPZ points shape disagrees with the manifest")
    _require(points.flags["C_CONTIGUOUS"], "NPZ points must be contiguous")
    points_bytes = points.tobytes()
    digest = hashlib.sha256(points_bytes).hexdigest()
    _require(digest == canonical["points"]["sha256"],
             "NPZ points digest disagrees with the manifest")
    _require(points_bytes == raw_bytes,
             "NPZ points bytes disagree with the actual source XYZ")
    _require(np.array_equal(points, source_points),
             "NPZ points values disagree with the actual source XYZ")
    return canonical, source_points


def check_declared_frame(manifest, declared_frame):
    """Refuse a CLI ``--frame`` that disagrees with the manifest declaration."""
    manifest_frame = (manifest.get("declared") or {}).get("frame")
    if declared_frame is not None and declared_frame != manifest_frame:
        raise CaptureInputError(
            "CLI frame %r disagrees with the adapted manifest frame %r"
            % (declared_frame, manifest_frame))
    return manifest_frame


def frame_of_row(manifest, rows):
    """Map pooled row indices to frame ordinal (half-open row ranges).

    The requested order and duplicates are preserved. Row ids must be strict
    integer indices in ``[0, total)``; bool/negative/out-of-range values are
    refused before NumPy indexing so negative ids cannot wrap from the end.
    """
    total = int(manifest["points"]["shape"][0])
    if isinstance(rows, np.ndarray):
        if rows.dtype.kind == "b" or rows.dtype.kind not in "iu":
            raise CaptureInputError("rows must be integer row indices")
        items = rows.tolist()
    elif isinstance(rows, (list, tuple)):
        items = list(rows)
    else:
        raise CaptureInputError("rows must be a 1-D integer row sequence")
    for item in items:
        if isinstance(item, bool) or not isinstance(item, (int, np.integer)):
            raise CaptureInputError("rows must be integer row indices")
    array = np.asarray(items, dtype=np.int64)
    if array.ndim != 1:
        raise CaptureInputError("rows must be a 1-D index array")
    if len(array) and (int(array.min()) < 0 or int(array.max()) >= total):
        raise CaptureInputError("rows contains an out-of-range row index")
    ordinal = np.full(total, -1, dtype=np.int64)
    for group in manifest["frame_groups"].values():
        start, end = int(group["rows"][0]), int(group["rows"][1])
        if end > start:
            ordinal[start:end] = int(group["ordinal"])
    mapped = ordinal[array]
    if np.any(mapped < 0):
        raise CaptureInputError("row does not belong to any declared frame")
    return mapped


def resolve_group(manifest, group_id):
    """Return ``(start, end)`` half-open member rows for a declared group id."""
    groups = manifest.get("frame_groups")
    if not isinstance(groups, dict) or not isinstance(group_id, str) \
            or group_id not in groups:
        raise CaptureInputError("unknown frame_group: " + repr(group_id))
    start, end = groups[group_id]["rows"]
    return int(start), int(end)


def _finite_bound(value, name):
    """Strict finite numeric bound (rejects bool/NaN/Inf), like ground.py."""
    if isinstance(value, bool) or not isinstance(value, (int, float,
                                                         np.integer, np.floating)):
        raise CaptureInputError(name + " must be a finite number")
    number = float(value)
    if not np.isfinite(number):
        raise CaptureInputError(name + " must be a finite number")
    return number


def select_group_region(points, manifest, region):
    """Group-first region selection over the declared member frame rows.

    Explicit pooled ``indices`` must all fall inside the declared group. Bounds
    are applied only to the group's own member rows, so a coordinate hit on a
    row outside the group is simply not counted (never an error), and the
    returned indices stay pooled original rows with no residual pre-filter.

    Every supplied selector is validated strictly *before* any group/empty-frame
    early return, so an empty member frame cannot skip a malformed bound and
    the original finite/bool/type guards still apply.
    """
    if not isinstance(region, dict):
        raise CaptureInputError("region must be an object")
    group_id = region.get("frame_group")
    present = [key for key in ("x_min_m", "x_max_m", "y_min_m", "y_max_m",
                               "z_min_m", "z_max_m") if key in region]
    if "indices" in region:
        if present:
            raise CaptureInputError("region must not mix indices and bounds")
    else:
        if not present:
            raise CaptureInputError("region needs indices or x/y/z bounds")
        if len(present) != 6:
            raise CaptureInputError("region bounds are incomplete")
    start, end = resolve_group(manifest, group_id)
    member = np.arange(start, end, dtype=np.int64)
    if "indices" in region:
        wanted = _strict_indices(region["indices"], "region.indices",
                                 int(manifest["points"]["shape"][0]))
        inside = wanted[(wanted >= start) & (wanted < end)]
        if len(inside) != len(wanted):
            raise CaptureInputError(
                "region indices leave the declared frame_group " + group_id)
        return inside
    bounds = []
    for key in ("x", "y", "z"):
        low = _finite_bound(region[key + "_min_m"], "region " + key + "_min_m")
        high = _finite_bound(region[key + "_max_m"], "region " + key + "_max_m")
        if low > high:
            raise CaptureInputError("region " + key + " bounds are inverted")
        bounds.append((low, high))
    if len(member) == 0:
        return member
    array = np.asarray(points, dtype=np.float64)[member]
    mask = np.ones(len(member), dtype=bool)
    for axis, (low, high) in enumerate(bounds):
        mask &= (array[:, axis] >= low) & (array[:, axis] <= high)
    return member[mask]


def gate_selection(points, manifest, fit_region, fit_indices, fit_frame_group,
                   validation_regions):
    """Enforce explicit group-first selectors and pairwise-disjoint frame sets.

    Returns ``(fit_rows, regions)`` where ``regions`` carries resolved pooled
    ``indices`` plus their ``region_id``/``frame_group`` for the existing
    constrained fitter. Missing selector/group, a cross-group explicit index,
    a frameset intersection or fewer than three validation regions is refused.
    """
    if fit_indices is not None:
        start, end = resolve_group(manifest, fit_frame_group)
        rows = _strict_indices(fit_indices, "fit_indices",
                               int(manifest["points"]["shape"][0]))
        if len(rows) != int(np.sum((rows >= start) & (rows < end))):
            raise CaptureInputError(
                "fit_indices leave the declared fit frame_group")
        fit_rows = rows
        fit_frames = set(frame_of_row(manifest, fit_rows).tolist())
    elif fit_region is not None:
        _require(fit_region.get("frame_group") == fit_frame_group,
                 "fit region frame_group must equal --fit-frame-group")
        fit_rows = select_group_region(points, manifest, fit_region)
        fit_frames = set(frame_of_row(manifest, fit_rows).tolist())
    else:
        raise CaptureInputError("an explicit fit selector is required")
    if not fit_frames:
        raise CaptureInputError("fit selection resolved to no frame members")

    regions = []
    seen_ids = set()
    seen_frames = []
    for region in (validation_regions or []):
        if not isinstance(region, dict):
            raise CaptureInputError("each validation region must be an object")
        region_id = region.get("region_id")
        if not isinstance(region_id, str) or not region_id:
            raise CaptureInputError("each validation region needs a region_id")
        if region_id in seen_ids:
            raise CaptureInputError("duplicate validation region_id " + region_id)
        seen_ids.add(region_id)
        rows = select_group_region(points, manifest, region)
        frames = set(frame_of_row(manifest, rows).tolist())
        if not frames:
            raise CaptureInputError("validation region " + region_id +
                                    " resolved to no frame members")
        if frames & fit_frames:
            raise CaptureInputError("validation region " + region_id +
                                    " shares a source frame with the fit set")
        for other in seen_frames:
            if frames & other:
                raise CaptureInputError(
                    "validation regions share a source frame")
        seen_frames.append(frames)
        regions.append({"region_id": region_id,
                        "frame_group": region["frame_group"],
                        "indices": [int(value) for value in rows]})
    if len(seen_frames) < 3:
        raise CaptureInputError("at least three explicit validation regions "
                                "are required")
    return np.asarray(fit_rows, dtype=np.int64), regions


def build_input_info(manifest, fit_region_path, fit_indices_path,
                     validation_path):
    source = manifest.get("source") or {}
    info = {
        "source": "capture_export",
        "constrained": True,
        "frame": (manifest.get("declared") or {}).get("frame"),
        "units": (manifest.get("declared") or {}).get("units"),
        "point_count": int(manifest["points"]["shape"][0]),
        "sha256": source.get("bin_sha256"),
        "input_manifest": {
            "schema": manifest.get("schema"),
            "kind": manifest.get("kind"),
            "source": source,
            "points": manifest.get("points"),
            "declared": manifest.get("declared"),
            "provenance": manifest.get("provenance"),
            "frame_groups": manifest.get("frame_groups"),
        },
    }
    if fit_region_path:
        info["fit_region"] = {"path": os.path.basename(fit_region_path),
                              "sha256": sha256_file(fit_region_path)}
    if fit_indices_path:
        info["fit_indices"] = {"path": os.path.basename(fit_indices_path),
                               "sha256": sha256_file(fit_indices_path)}
    if validation_path:
        info["validation_regions"] = {"path": os.path.basename(validation_path),
                                      "sha256": sha256_file(validation_path)}
    return info
