"""Explicit local joint-recorder service; idle startup never accesses a device."""
import argparse
import json
from pathlib import Path
import sys
import threading

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'pc_apps/console'))
import joint_capture


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root',type=Path,required=True)
    args=parser.parse_args()
    if not args.output_root.is_absolute():parser.error('output root must be absolute')
    # This does not mkdir, open the camera page or start recording.
    server,recorder=joint_capture.start_server(args.output_root.resolve(),ROOT/'pc_apps/console/joint_capture.html',
        fetch_dir=ROOT/'pc_apps/human_replay')
    print(json.dumps(dict(url='http://127.0.0.1:%d/'%server.server_port,output_root=str(args.output_root),state='idle')),flush=True)
    try:threading.Event().wait()
    except KeyboardInterrupt:pass
    finally:
        recorder.close();server.shutdown();server.server_close()


if __name__=='__main__':main()
