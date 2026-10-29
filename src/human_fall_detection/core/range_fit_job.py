"""One bounded, cancellable spawn job for site fitting; child writes no files."""
import math
import multiprocessing
import time
import threading
import queue

from .range_site_ground import fit_site


def _fit_worker(connection, fitter):
    try:
        args = connection.recv()
        connection.send(fitter(*args))
    except Exception as exc:
        try:
            connection.send(dict(status='unavailable', reason='fit_worker_failed: '+repr(exc)))
        except (OSError, EOFError):
            pass
    finally:
        connection.close()


class GroundFitJob:
    def __init__(self, args, timeout_s=60., fitter=fit_site, clock=time.monotonic):
        if not math.isfinite(timeout_s) or timeout_s <= 0:
            raise ValueError('positive finite fit timeout required')
        context = multiprocessing.get_context('spawn')
        self.connection, writer = context.Pipe(duplex=True)
        self.process = context.Process(target=_fit_worker, args=(writer, fitter), daemon=True)
        self.clock, self.deadline = clock, clock()+timeout_s
        self.closed = False
        self.close_lock = threading.Lock()
        self.results = queue.Queue(maxsize=1)
        try:
            self.process.start()
        except Exception:
            writer.close();self.connection.close()
            raise
        writer.close()
        # Neither a large input pickle nor a partially sent report may block the
        # recognition worker. Each pipe direction has exactly one IO thread.
        self.sender = threading.Thread(target=self._send, args=(args,), daemon=True)
        self.receiver = threading.Thread(target=self._receive, daemon=True)
        self.sender.start();self.receiver.start()

    def _result(self, value):
        if not self.closed:
            try:self.results.put_nowait(value)
            except queue.Full:pass

    def _send(self, args):
        try:self.connection.send(args)
        except (OSError, EOFError, ValueError) as exc:
            self._result(dict(status='unavailable', reason='ground_fit_send_failed: '+repr(exc)))

    def _receive(self):
        try:self._result(self.connection.recv())
        except (OSError, EOFError, ValueError) as exc:
            self._result(dict(status='unavailable', reason='ground_fit_transport_failed: '+repr(exc)))

    def poll(self):
        if self.closed:
            return None
        if self.clock() >= self.deadline:
            self.close()
            return dict(status='unavailable', reason='ground_fit_timeout')
        try:result = self.results.get_nowait()
        except queue.Empty:return None
        else:
            self.close()
            return result

    def close(self):
        with self.close_lock:
            if self.closed:
                return
            self.closed = True
            if self.process.is_alive():
                self.process.terminate()
            self.process.join(.3)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(.3)
            self.connection.close()
            self.sender.join(.3)
            self.receiver.join(.3)
