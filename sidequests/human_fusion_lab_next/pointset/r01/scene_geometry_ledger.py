"""Explicit cached-XYZ adapter; never impersonates missing original 28-byte files."""
from pathlib import Path
import numpy as np
from actions import HERE, OUT, ROOT, read, sha
from core import R, T


class GeometryLedger:
    def __init__(self, folder):
        self.folder = Path(folder).resolve()
        evidence = ROOT/'docs/human_fall/evidence/2026-10-14_hf_mainline_points_r1'
        reproduction = read(evidence/'BASELINE_REPRODUCTION.json')
        if not reproduction['members_equal'] or reproduction['baseline_id'] != self.folder.name:
            raise ValueError('Geometry ledger does not match saved baseline reproduction')
        self.frames = {(r['sid'], r['fi']): r for r in reproduction['frames']}
        self.bindings = read(evidence/'SOURCE_BINDINGS.json')
        catalog = read(OUT/'catalog.json')
        if self.bindings['sources'] != {s['session_id']:s['source_sha256'] for s in catalog['sessions']}:
            raise ValueError('Historical source bindings disagree with action catalog')
        self.prior = Path(read(OUT/'RUN_MANIFEST.json')['config']['background_experiment'])
        self.reference = catalog['background']['session']
        self.hashes = {}; self.registrations = {}

    def frame(self, sid, fi):
        base = read(OUT/sid/f'{fi:04d}.json'); f = base['source_frame']
        frozen = self.frames[(sid, fi)]
        if frozen['source_frame'] != f or frozen['count'] != f['count_points']:
            raise ValueError('Ledger source frame mismatch')
        file = self.folder/sid/f'{fi:04d}.npz'
        with np.load(file, allow_pickle=False) as a:
            q = a['raw_xyz'].astype(float); p = a['xyz'].astype(float)
            if q.shape != (f['count_points'],3) or p.shape != q.shape:
                raise ValueError('Geometry ledger shape mismatch')
            np.testing.assert_array_equal(a['local_index'],np.arange(len(q)))
            np.testing.assert_array_equal(a['global_row'],np.arange(len(q))+f['offset_points'])
            np.testing.assert_array_equal(a['baseline_target'],base['selection']['selected_source_indices'])
        expected = q @ R.T + T
        if sid != self.reference:
            if sid not in self.registrations: self.registrations[sid] = read(self.prior/(sid+'_registration.json'))
            reg = self.registrations[sid]
            if reg['gate']['status'] != 'PASS': raise ValueError('Rejected nominal registration')
            expected = expected @ np.array(reg['R']).reshape(3,3).T + reg['t']
        np.testing.assert_allclose(p,expected,atol=1e-10,rtol=0,equal_nan=True)
        self.hashes[str(file)] = sha(file)
        return q,p,base

    def provenance(self):
        return {'mode':'CACHED_XYZ_REGRESSION_NOT_ORIGINAL_RECORDING_REPLAY',
            'original_files_currently_available':False,'original_byte_sha_verified_now':False,
            'opaque_intensity_ring_timestamp_bytes_available':False,
            'historical_source_sha256':self.bindings['sources'],'ledger_sha256':self.hashes,
            'calibration':'FROZEN_PREVIOUS_CAL_ENVELOPE; NO_NEW_CAL_SOURCE_AVAILABLE',
            'source_frame_stamps':'FROM_SAVED_ORIGINAL_FRAME_LEDGER'}
