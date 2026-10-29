"""持续低矮且水平伸展的实测几何提示；不证明人体或跌倒。"""
import math

SETTINGS = dict(median_m=.5, top_m=.7, extent_m=.5, max_gap_s=.3,
                suspected_s=1.5, sustained_s=3.0)


class DemoAlert:
    """Shared causal version of the four-session demo's two duration levels."""
    def __init__(self, settings=None):
        self.settings = dict(SETTINGS)
        if settings is not None:
            self.settings.update(settings)
        self.previous = None
        self.start = None
        self.duration = 0.0
        self.eligible = False

    def update(self, row):
        values = (row.get('hm'), row.get('ht'), row.get('sp'), row.get('t'))
        finite = all(isinstance(v, (int, float)) and not isinstance(v, bool)
                     and math.isfinite(v) for v in values)
        self.eligible = (finite and type(row.get('i')) is int and row.get('tid') is not None and row.get('n', 0) > 0
                         and values[0] <= self.settings['median_m']
                         and values[1] <= self.settings['top_m']
                         and values[2] >= self.settings['extent_m'])
        previous_time = self.previous.get('t') if self.previous is not None else None
        continuous = (self.previous is not None and type(row.get('i')) is int
                      and type(self.previous.get('i')) is int
                      and row.get('i') == self.previous['i'] + 1
                      and row.get('tid') == self.previous.get('tid')
                      and row.get('generation') == self.previous.get('generation')
                      and row.get('binding') == self.previous.get('binding')
                      and not row.get('reset') and finite
                      and isinstance(previous_time, (int, float)) and math.isfinite(previous_time)
                      and 0 < row['t'] - previous_time <= self.settings['max_gap_s'])
        if not self.eligible:
            self.start = None
        elif self.start is None or not continuous:
            self.start = row['t']
        self.previous = dict(row)
        self.duration = row['t'] - self.start if self.eligible and self.start is not None else 0.
        return (2 if self.duration >= self.settings['sustained_s'] - 1e-9 else
                1 if self.duration >= self.settings['suspected_s'] - 1e-9 else 0)
