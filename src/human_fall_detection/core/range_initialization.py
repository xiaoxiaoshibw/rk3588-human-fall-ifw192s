"""Shared site initialization for ROS and recorded-message service replay.

Only observe() mutates recognition state. Fit, report IO and validation run in
one worker; only a complete prepared result is installed by that same writer.
"""
import hashlib
import json
import queue
import threading

from .range_fit_job import GroundFitJob
from .range_site_ground import FIT_FRAMES, HELD_FRAMES, save_fit


class SiteInitialization:
    def __init__(self, service, *, declared_empty, output=None, site_id=None,
                 upstream='ros:/innolidar_points', timeout_s=60., stop=None,
                 job_factory=GroundFitJob, save=save_fit):
        if output is not None and (not declared_empty or not site_id):
            raise ValueError('site fit requires explicit empty-prefix declaration and site id')
        self.service, self.engine = service, service.engine
        self.output, self.site_id, self.upstream = output, site_id, upstream
        self.timeout_s, self.job_factory, self.save = timeout_s, job_factory, save
        self.stop = stop if stop is not None else threading.Event()
        self.status = dict(background='explicit_empty_prefix_50' if declared_empty else 'not_declared',
                           ground='pending_single_fit' if output is not None else 'not_loaded')
        self.samples, self.headers = [], []
        self.results = queue.Queue(maxsize=1)
        self.lock = threading.Lock()
        self.job, self.thread = None, None

    def _failed(self, reason):
        self.status['ground'] = 'fit_failed: '+str(reason)
        runtime = self.engine.runtime
        if runtime:
            runtime.ground = runtime.ground_sha = None
            runtime.config['ground_sha256'] = None
            runtime.config_sha = hashlib.sha256(json.dumps(runtime.config, sort_keys=True).encode()).hexdigest()
        self.engine.ground_status = dict(available=False, reason=self.status['ground'])
        self.engine.clear_history()

    def _finish(self, samples, headers, unavailable):
        job = None
        try:
            report = unavailable
            if report is None:
                job = self.job_factory((samples, headers,
                    dict(siteId=self.site_id, frameId=self.engine.frame_id, gridSha256=self.engine.grid.sha256),
                    dict(upstream=self.upstream, identity=dict(self.engine.identity))), timeout_s=self.timeout_s)
                with self.lock:
                    if not self.stop.is_set():
                        self.job = job
                if self.stop.is_set():
                    return
                while not self.stop.is_set():
                    report = job.poll()
                    if report is not None:
                        break
                    self.stop.wait(.02)
            if self.stop.is_set():
                return
            path = self.save(report, self.output)
            if path is None:
                outcome = (None, None, report.get('reason', 'fit_unavailable'))
            else:
                ground, sha = self.engine.prepare_ground(path, self.site_id)
                outcome = (ground, sha, None)
            if not self.stop.is_set():
                self.results.put_nowait(outcome)
        except Exception as exc:
            if not self.stop.is_set():
                self.results.put_nowait((None, None, repr(exc)))
        finally:
            if job is not None:
                job.close()
            with self.lock:
                if self.job is job:
                    self.job = None

    def _start(self, samples, headers, unavailable=None):
        self.status['ground'] = 'fitting' if unavailable is None else unavailable['reason']
        self.thread = threading.Thread(target=self._finish, args=(samples, headers, unavailable),
                                       name='ground-fit-completion', daemon=True)
        self.thread.start()

    def observe(self, result):
        """Called after process_latest(), even when no cloud was available."""
        if self.stop.is_set():
            return
        try:
            outcome = self.results.get_nowait()
        except queue.Empty:
            outcome = None
        if outcome is not None:
            self.service.clear_ground_binding()
            try:
                ground, sha, reason = outcome
                if reason:
                    self._failed(reason)
                elif not self.stop.is_set():
                    self.engine.install_prepared_ground(ground, sha, self.upstream)
                    self.status['ground'] = 'bound'
            except Exception as exc:
                self._failed(repr(exc))
        if (self.output is None or self.status['ground'] != 'pending_single_fit'
                or not result or not result.get('source')):
            return
        source = result['source']
        header = dict(seq=source['seq'], sec=source['stamp_secs'], nsec=source['stamp_nsecs'],
                      frame_id=source['frame_id'], wire_sha256=result['local_range']['wireSha256'])
        if self.headers and header['seq'] != self.headers[-1]['seq']+1:
            self._start([], [], dict(status='unavailable', reason='fit_source_discontinuous', headers=self.headers))
            self.samples, self.headers = [], []
            return
        frame = self.engine.ground_frame
        self.samples.append(frame.xyz[frame.source_rows[frame.valid]].copy())
        self.headers.append(header)
        if len(self.samples) == FIT_FRAMES+HELD_FRAMES:
            samples, headers = self.samples, self.headers
            self.samples, self.headers = [], []
            self._start(samples, headers)

    def close(self):
        self.stop.set()
        with self.lock:
            job, self.job = self.job, None
        if job is not None:
            job.close()
        if self.thread is not None:
            self.thread.join(2.)
