#!/usr/bin/env python3
"""Print one state message from a ROS1 topic as JSON (for status/health checks).

Used by ``deploy_human_fall.sh status|health``: it answers "is the node actually
producing a fresh state, and what does it say" without the browser. It is a
read-only subscriber and publishes nothing.

Exit codes: 0 = message received, 3 = timeout, 2 = ROS unavailable.
"""

import argparse
import json
import sys
import time


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--topic', required=True)
    parser.add_argument('--timeout', type=float, default=5.0)
    args = parser.parse_args(argv)

    try:
        import rospy
        from std_msgs.msg import String
    except ImportError as exc:
        sys.stderr.write('ROS1 rospy/std_msgs required: %s\n' % exc)
        return 2

    received = {}

    def on_state(msg):
        received['at'] = time.time()
        received['data'] = msg.data

    rospy.init_node('hf_state_probe', anonymous=True, disable_signals=True)
    rospy.Subscriber(args.topic, String, on_state, queue_size=1)
    deadline = time.time() + max(0.5, args.timeout)
    while time.time() < deadline and not received:
        time.sleep(0.05)
    rospy.signal_shutdown('probe done')
    if not received:
        print(json.dumps({'ok': False, 'reason': 'no_message',
                          'topic': args.topic, 'timeout_s': args.timeout}))
        return 3
    try:
        payload = json.loads(received['data'])
    except ValueError as exc:
        print(json.dumps({'ok': False, 'reason': 'invalid_json', 'detail': str(exc),
                          'topic': args.topic}))
        return 3
    print(json.dumps({'ok': True, 'topic': args.topic,
                      'received_wall': received['at'], 'state': payload},
                     ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())