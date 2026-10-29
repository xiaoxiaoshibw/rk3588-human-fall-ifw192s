import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.subscription_health import SubscriptionGuard


class Subscriber:
    connections = 0
    closed = False

    def get_num_connections(self):
        return self.connections

    def unregister(self):
        self.closed = True


class TestSubscriptionHealth(unittest.TestCase):
    def test_connected_but_silent_transport_recovers_without_inference_watchdog(self):
        created=[]
        def factory():
            sub=Subscriber(); sub.connections=1; created.append(sub); return sub
        guard=SubscriptionGuard(factory,0,watch_messages=True)
        for now in (5,10,50):
            guard.note_message(now); guard.poll(now)
        self.assertEqual(len(created),1)
        guard.poll(59); self.assertEqual(len(created),1)
        guard.poll(60); self.assertEqual(len(created),2)
        self.assertEqual(guard.report()['reconnect_reason'],'callbacks_stale')
        guard.poll(61); self.assertEqual(len(created),2)
        guard.note_message(65); guard.poll(65)
        self.assertEqual(len(created),2)

    def test_startup_grace_lost_connection_and_backoff(self):
        created = []

        def factory():
            sub = Subscriber()
            created.append(sub)
            return sub

        guard = SubscriptionGuard(factory, 0)
        guard.poll(9)
        self.assertEqual(len(created), 1)
        created[0].connections = 1
        guard.poll(10)
        guard.poll(100)  # slow computation does not reset a healthy transport
        self.assertEqual(len(created), 1)
        created[0].connections = 0
        guard.poll(109)
        guard.poll(110)
        self.assertTrue(created[0].closed)
        self.assertEqual(len(created), 2)
        guard.poll(111)
        self.assertEqual(len(created), 2)
        self.assertEqual(guard.report()['reconnects'], 1)

    def test_failed_factory_retries_and_reports_error(self):
        calls = []

        def factory():
            calls.append(1)
            if len(calls) == 2:
                raise OSError('transport unavailable')
            return Subscriber()

        guard = SubscriptionGuard(factory, 0)
        guard.poll(10)
        self.assertIn('transport unavailable', guard.report()['last_error'])
        self.assertEqual(guard.report()['connections'], 0)
        guard.poll(19)
        self.assertEqual(len(calls), 2)
        guard.poll(20)
        self.assertIsNone(guard.report()['last_error'])
        self.assertEqual(guard.report()['reconnects'], 1)
