"""Shared strict numeric-array validation (HF pure layer, no ROS).

Only :func:`strict_numeric_array` lives here: it is needed by both
``core.calibration`` (ground-derived blocks) and ``core.ground`` (ground-plane
records), and putting it in either would create an import cycle.
"""


def strict_numeric_array(values, shape, field, error_cls=ValueError):
    """Return a float64 array, rejecting bool/string/non-finite *before* NumPy.

    ``np.asarray`` silently coerces ``True`` to ``1.0`` and strings that parse;
    a validator that converts first can therefore never see a mixed-bool
    identity matrix. Every element is checked first, then converted, then the
    shape and finiteness are double-checked. Sequences, NumPy arrays and
    scalars are all enumerated element-wise.
    """
    import numpy as np

    if values is None:
        raise error_cls(field + " is required")
    flat = []

    def _collect(item, trail):
        if isinstance(item, (list, tuple)):
            for index, entry in enumerate(item):
                _collect(entry, trail + "." + str(index))
            return
        if isinstance(item, np.ndarray):
            if item.ndim == 0:
                _collect(item.item(), trail)
            else:
                for index, entry in enumerate(item):
                    _collect(entry, trail + "." + str(index))
            return
        if isinstance(item, bool) or isinstance(item, np.bool_) \
                or not isinstance(item, (int, float, np.integer, np.floating)):
            raise error_cls(
                field + trail + " must be a real number (bool/string rejected)")
        value = float(item)
        if not np.isfinite(value):
            raise error_cls(field + trail + " must be finite")
        flat.append(value)

    _collect(values, "")
    try:
        array = np.asarray(values, dtype=np.float64)
    except (TypeError, ValueError):
        raise error_cls(field + " must be numeric") from None
    if array.shape != shape:
        raise error_cls("{} must have shape {}".format(field, shape))
    if len(flat) != int(np.prod(shape)):
        raise error_cls(field + " has inconsistent dimensions")
    return array
