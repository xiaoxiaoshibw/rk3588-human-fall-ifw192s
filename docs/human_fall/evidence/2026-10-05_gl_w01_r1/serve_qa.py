import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[4]/'pc_apps/human_replay'))
import human_replay_lib as H
H.ThreadingHTTPServer(('127.0.0.1',8902),H.Handler).serve_forever()
