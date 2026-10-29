import tempfile
import time
import unittest
import sys
from pathlib import Path
import queue
import threading
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.range_fit_job import GroundFitJob
from core.range_service import acquire_service_lock


def never_finishes():
    time.sleep(30)


def derived_result():
    return dict(status='unavailable', reason='synthetic_fit_result')


class FitJobTests(unittest.TestCase):
    def test_partial_report_receive_never_blocks_primary_poll_or_timeout(self):
        clock=[0.];entered=threading.Event();release=threading.Event();alive=[True]
        job=GroundFitJob.__new__(GroundFitJob)
        def partial():
            entered.set();release.wait(2)
            return dict(status='geometry_accepted')
        job.connection=NS(recv=partial,close=release.set)
        job.process=NS(is_alive=lambda:alive[0],terminate=lambda:alive.__setitem__(0,False),join=lambda seconds:None)
        job.clock=lambda:clock[0];job.deadline=1.;job.closed=False;job.results=queue.Queue(1)
        job.close_lock=threading.Lock()
        job.sender=NS(join=lambda seconds:None)
        job.receiver=threading.Thread(target=job._receive,daemon=True);job.receiver.start()
        try:
            self.assertTrue(entered.wait(1))
            start=time.monotonic()
            self.assertIsNone(job.poll())
            self.assertLess(time.monotonic()-start,.1)
            clock[0]=2.
            self.assertEqual(job.poll()['reason'],'ground_fit_timeout')
            self.assertFalse(job.receiver.is_alive())
            self.assertTrue(job.results.empty(), 'late completed report cannot bypass the deadline')
        finally:
            release.set();job.close()

    def test_timeout_and_stop_reap_spawn_child_within_bounded_time(self):
        for timeout in (True, False):
            started = time.monotonic()
            job = GroundFitJob((), timeout_s=.15 if timeout else 60, fitter=never_finishes)
            try:
                if timeout:
                    result = None
                    while result is None and time.monotonic()-started < 3:
                        result = job.poll()
                        time.sleep(.01)
                    self.assertEqual(result['reason'], 'ground_fit_timeout')
                else:
                    job.close()
                self.assertFalse(job.process.is_alive())
                self.assertLess(time.monotonic()-started, 3)
            finally:
                job.close()

    def test_child_returns_only_derived_result(self):
        job = GroundFitJob((), timeout_s=10, fitter=derived_result)
        try:
            result = None
            while result is None:
                result = job.poll()
                time.sleep(.01)
            self.assertEqual(result['reason'], 'synthetic_fit_result')
        finally:
            job.close()

    def test_os_lease_rejects_second_instance_and_releases_on_close(self):
        with tempfile.TemporaryDirectory() as directory:
            with acquire_service_lock('/synthetic/state', directory):
                with self.assertRaisesRegex(RuntimeError, 'already running'):
                    acquire_service_lock('/synthetic/state', directory)
            with acquire_service_lock('/synthetic/state', directory):
                pass


if __name__ == '__main__':
    unittest.main()
