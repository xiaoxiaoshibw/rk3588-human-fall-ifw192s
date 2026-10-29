"""Recover disconnected ROS subscribers without restarting a node or its algorithm.

The factory owns ROS details; this guard only checks transport connections.
It does not treat slow computation or missing measurements as permission to reset
healthy connections, and never changes sensor/driver/network configuration.
"""


class SubscriptionGuard:
    def __init__(self, factory, now, retry_s=10.0, watch_messages=False):
        self.factory = factory
        self.retry_s = retry_s
        self.subscriber = factory()
        self.next_retry = now + retry_s
        self.reconnects = 0
        self.last_error = None
        self.watch_messages = watch_messages
        self.last_message = now
        self.reconnect_reason = None

    def note_message(self, now):
        self.last_message = now

    def poll(self, now):
        connected = self.subscriber is not None and self.subscriber.get_num_connections() > 0
        silent = self.watch_messages and now-self.last_message >= self.retry_s
        if connected and not silent:
            self.next_retry = (self.last_message if self.watch_messages else now) + self.retry_s
            return
        if now < self.next_retry:
            return
        self.next_retry = now + self.retry_s
        self.reconnect_reason = 'callbacks_stale' if connected else 'no_transport_connections'
        try:
            if self.subscriber is not None:
                self.subscriber.unregister()
                self.subscriber = None
            self.subscriber = self.factory()
            self.reconnects += 1
            self.last_error = None
        except Exception as exc:  # transport diagnostics must not kill the node
            self.last_error = "%s: %s" % (type(exc).__name__, exc)

    def report(self):
        subscriber = self.subscriber  # publication can run while the main loop reconnects
        return {"connections": subscriber.get_num_connections()
                if subscriber is not None else 0,
                "reconnects": self.reconnects, "last_error": self.last_error,
                "reconnect_reason": self.reconnect_reason, "last_message_mono_s": self.last_message}
