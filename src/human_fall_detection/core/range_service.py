"""ROS-free service lifecycle. One recognition writer, bounded input/preview slots.

Subscribers and UI clients never own the engine lifecycle or background.
"""
import copy
import base64
import hashlib
import io
import threading
import time
import struct
import os
from pathlib import Path
import tempfile
from collections import deque

from .node_runtime import LatestFrameQueue
from .range_live import preview_rgb
from .range_png import png
from .range_skeleton import estimate, project_regions

PROTOCOL = 'range_recognition/1'


class RangeService:
    def __init__(self, engine, release_id='development', preview=True, clock=time.monotonic):
        self.engine, self.release_id, self.preview, self.clock = engine, release_id, preview, clock
        self.queue, self.previews = LatestFrameQueue(1), LatestFrameQueue(1)
        self.lock = threading.Lock()
        self.clear_pending = threading.Event()
        self.last_received = self.last_completed = None
        self.result_received = None
        self.processing_since = self.publish_started = self.last_published = None
        self.overwritten_headers = deque(maxlen=128)
        self.overwritten_overflow = 0
        self.history_revision = 0
        self.history_invalid = False
        self.discarded_after_invalidation = 0
        self.received = self.processed = self.published = self.source_gaps = 0
        self.previous_seq = None
        self.callback_ms = self.publish_ms = 0.
        self.state = dict(engine.invalid('waiting_for_cloud'), target_mode='range_service_automatic')
        self.ground_binding = None
        self.preview_expired = 0
        self.preview_ttl_expired = self.preview_superseded = 0
        self.compute_over_500 = self.source_age_over_500 = 0
        self.preview_computed = self.preview_compute_over_500 = 0
        self.last_compute_ms = self.last_preview_ms = None
        # Publisher wake-up: a preview-augmented state must reach subscribers before
        # the next recognition result replaces it; 20 Hz polling loses that window.
        self.updated = threading.Event()

    def submit(self, msg):
        with self.lock:
            # The callback clock, counters and slot commit share one order.
            # Releasing here before put lets an older callback overwrite a newer one.
            start = self.clock()
            self.received += 1
            self.last_received = start
            # Only store a reference; no serialization, fitting or decode here.
            self.queue.put((start, msg))
            self.callback_ms = (self.clock()-start)*1000

    def process_latest(self):
        item = self.queue.take()
        if item is None:
            return None
        received, msg = item
        with self.lock:
            self.processing_since = self.clock()
            dropped = self.queue.drain_overwritten()
            self.overwritten_overflow += dropped['overflow'] + max(0,
                len(self.overwritten_headers)+len(dropped['headers'])-self.overwritten_headers.maxlen)
            self.overwritten_headers.extend(dropped['headers'])
            revision = self.history_revision
            clear = self.clear_pending.is_set()
            self.clear_pending.clear()
        if clear:
            self.engine.clear_history()
        start = self.clock()
        try:
            # genpy serialization preserves the received header, fields, strides,
            # padding and data. Never hash packed ROW_DTYPE inference rows.
            if len(msg.data) > 32*1024*1024 or len(msg.fields) > 128:
                raise ValueError('oversized ROS cloud')
            stream = io.BytesIO()
            msg.serialize(stream)
            fingerprint = hashlib.sha256(stream.getvalue()).hexdigest()
            serialized = self.clock()
            result = self.engine.process(msg, received, wire_sha256=fingerprint, preview=False)
            if result.get('source'):
                seq = result['source']['seq']
                if self.previous_seq is not None and seq > self.previous_seq:
                    self.source_gaps += max(0, seq-self.previous_seq-1)
                self.previous_seq = seq
            result.setdefault('performance', {}).update(
                queue_age_ms=(start-received)*1000, serialize_hash_ms=(serialized-start)*1000)
        except (ValueError, TypeError, AttributeError, OverflowError, struct.error) as exc:
            self.engine.invalidate('invalid_ros_message_requires_rebind: '+str(exc))
            result = self.engine.invalid(self.engine.disabled)
        result['target_mode'] = 'range_service_automatic'
        compute_ms = (self.clock()-start)*1000
        result.setdefault('performance', {})['service_compute_ms'] = compute_ms
        # Only the recognition writer reads engine ground. The publisher reads
        # the committed copy, including when recognition evidence is discarded.
        ground = copy.deepcopy(getattr(self.engine, 'ground_status', None))
        runtime = getattr(self.engine, 'runtime', None)
        if (getattr(self.engine, 'disabled', None) or not runtime
                or not runtime.ground or not runtime.ground_sha
                or not ground or ground.get('sha256') != runtime.ground_sha
                or not ground.get('displayPlane')):
            ground = None
        with self.lock:
            if revision != self.history_revision or (result.get('source') and self.clock()-received > .5):
                # A heartbeat may invalidate history while inference is running.
                # Never commit that in-flight evidence into the new valid period.
                self.engine.clear_history()
                performance = result.get('performance')
                result = dict(self.engine.invalid('history_invalidated_during_processing'),
                              target_mode='range_service_automatic', performance=performance)
                self.discarded_after_invalidation += 1
            self.last_compute_ms = compute_ms
            self.compute_over_500 += int(compute_ms > 500)
            self.source_age_over_500 += int((self.clock()-received)*1000 > 500)
            self.processed += 1
            self.processing_since = None
            self.state, self.last_completed = result, self.clock()
            self.ground_binding = ground
            self.result_received = received if result.get('source') else None
            self.history_invalid = not bool(result.get('source'))
            self.updated.set()
        if self.preview and result.get('source'):
            self.previews.put((received, self.engine.ground_frame, result))
        return result

    def process_preview(self):
        item = self.previews.take()
        if item is None:
            return False
        received, frame, original = item
        start = self.clock()
        if start-received > .5:
            with self.lock:
                self.preview_expired += 1
                self.preview_ttl_expired += 1
            return False
        result = dict(original)
        bundle = result['local_range'] = dict(original['local_range'])
        rows = result['target_source_rows']
        encoded = png(preview_rgb(frame))
        bundle['preview'] = base64.b64encode(encoded).decode('ascii')
        bundle['depth'] = dict(bundle['depth'], previewSha256=hashlib.sha256(encoded).hexdigest())
        bundle['skeleton'] = project_regions(estimate(frame.xyz[rows] if rows else [], rows), frame)
        result['performance'] = dict(result['performance'], preview_ms=(self.clock()-start)*1000)
        with self.lock:
            self.last_preview_ms = result['performance']['preview_ms']
            self.preview_computed += 1
            self.preview_compute_over_500 += int(self.last_preview_ms > 500)
            # A delayed auxiliary result cannot restore invalid state, replace a
            # newer source, or cross a service epoch. No waiting in recognition.
            if self.state is not original or self.clock()-received > .5:
                self.preview_expired += 1
                if self.clock()-received > .5:self.preview_ttl_expired += 1
                else:self.preview_superseded += 1
                return False
            self.state = result
            self.updated.set()
        return True

    def snapshot(self, subscription=None):
        now = self.clock()
        with self.lock:
            state = self.state
            age = now-self.last_received if self.last_received is not None else None
            result_age = now-self.last_completed if self.last_completed is not None else None
            source_age = now-self.result_received if self.result_received is not None else None
            processing_age = None if self.processing_since is None else now-self.processing_since
            publish_age = None if self.last_published is None else now-self.last_published
            publishing_age = None if self.publish_started is None else now-self.publish_started
            if (age is None or age > .5 or result_age is None or result_age > .5
                    or (state.get('source') and (source_age is None or source_age > .5))):
                reason = 'waiting_for_cloud' if age is None else 'required_cloud_stale' if age > .5 else 'recognition_result_stale'
                if not self.history_invalid:
                    self.history_revision += 1
                    self.clear_pending.set()
                    self.history_invalid = True
                # Construct from the last published identity, never concurrently
                # read/mutate the worker's tracker or invent epoch=0.
                state = dict(state, source=None, track_id=None, track_status='unselected',
                    observability='invalid', bbox_observed=False, target_source_rows=[],
                    fall_status='unknown', acquisition=dict(reason=reason), local_range=None)
                self.state = state
            result = copy.copy(state)
            result['groundBinding'] = copy.deepcopy(self.ground_binding)
            if result['groundBinding'] is not None:
                # The plane remains bound; the last support check is not a
                # current observation once recognition loses its source.
                result['groundBinding']['supportCurrent'] = bool(state.get('source'))
            result['service'] = dict(protocol=PROTOCOL, version=1, releaseId=self.release_id,
                instanceId=state['session_id'], publisherRole='board_recognition',
                capabilities=['source_wire_sha256', 'source_rows', 'range_runtime', 'ground_monitor',
                              'height', 'dynamic_evidence', 'ground_alert_v1', 'horizontal_low_posture_v1', 'heartbeat',
                              'independent_ground_binding']
                             + (['async_preview'] if self.preview else []),
                ttlMs=500, confirmedEnabled=False, body='unavailable')
            result['health'] = dict(received=self.received, processed=self.processed,
                published=self.published, overwritten=self.queue.dropped, sourceGaps=self.source_gaps,
                previewOverwritten=self.previews.dropped, previewExpired=self.preview_expired,
                previewTtlExpired=self.preview_ttl_expired, previewSuperseded=self.preview_superseded,
                inputAgeMs=None if age is None else age*1000,
                resultAgeMs=None if result_age is None else result_age*1000,
                resultSourceAgeMs=None if source_age is None else source_age*1000,
                invalidationRevision=self.history_revision,
                discardedAfterInvalidation=self.discarded_after_invalidation,
                callbackMs=self.callback_ms, publishEnqueueMs=self.publish_ms, subscription=subscription,
                computeOver500=self.compute_over_500, sourceAgeOver500=self.source_age_over_500,
                lastComputeMs=self.last_compute_ms, previewComputed=self.preview_computed,
                previewComputeOver500=self.preview_compute_over_500, lastPreviewMs=self.last_preview_ms,
                inputStatus='waiting' if age is None else 'silent' if age>.5 else 'receiving',
                recognitionStatus='processing_stalled' if processing_age is not None and processing_age>.5
                    else 'no_progress' if age is not None and age<=.5 and (result_age is None or result_age>.5)
                    else 'processing' if processing_age is not None else 'idle',
                publicationStatus='publishing_stalled' if publishing_age is not None and publishing_age>.5
                    else 'not_started' if publish_age is None else 'silent' if publish_age>.5 else 'enqueuing',
                processingAgeMs=None if processing_age is None else processing_age*1000,
                publishAgeMs=None if publish_age is None else publish_age*1000,
                publishingAgeMs=None if publishing_age is None else publishing_age*1000,
                overwrittenHeaders=list(self.overwritten_headers), overwrittenHeaderOverflow=self.overwritten_overflow,
                latencyScope='local monotonic receive/compute/enqueue; not physical or GPU display latency')
            return result

    def clear_ground_binding(self):
        # Called by the recognition writer before replacing or rejecting a plane.
        with self.lock:
            self.ground_binding = None
            self.updated.set()

    def note_publish_started(self):
        with self.lock:self.publish_started = self.clock()

    def note_published(self, milliseconds):
        with self.lock:
            self.published += 1
            self.publish_ms = milliseconds
            self.last_published = self.clock()
            self.publish_started = None


def assert_single_publisher(publishers, topic, own_name):
    others = [n for t, names in publishers if t == topic for n in names if n != own_name]
    if others:
        raise RuntimeError('canonical state publisher already exists: '+', '.join(others))


def acquire_service_lock(topic, directory=None):
    """OS-owned lease, held for the process lifetime; no stale PID-file deletion."""
    path = Path(directory or tempfile.gettempdir())/('ldiar_recognition_'+hashlib.sha256(topic.encode()).hexdigest()[:20]+'.lock')
    handle = path.open('a+b')
    try:
        if os.name == 'nt':
            import msvcrt
            if handle.tell() == 0:
                handle.write(b'\0');handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        raise RuntimeError('recognition service already running for '+topic) from exc
    return handle
