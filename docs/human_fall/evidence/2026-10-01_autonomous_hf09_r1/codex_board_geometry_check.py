import sys
import numpy as np
sys.path.insert(0, '/root/catkin_ws/hf07_verify_ws/src/human_fall_detection')
from core.node_runtime import FallNodeCore
def cloud():
    return np.random.RandomState(25).normal(size=(500,3))*[.06,.06,.25]+[3,0,-.3]
def selected():
    core=FallNodeCore('review')
    snapshot=core.process(cloud(),10,seq=1,stamp_secs=100,stamp_nsecs=0,frame_id='innolidar',now=10)['snapshot']
    request={'schema_version':1,'request_id':'select','action':'select','session_id':'review',
             'time_epoch':snapshot['time_epoch'],'snapshot_id':snapshot['snapshot_id'],
             'candidate_id':snapshot['candidates'][0]['candidate_id'],'selection_version':0}
    assert core.handle_request(request,10.01)['accepted']
    return core
core=selected()
state=core.process(cloud()+[4,0,0],14,seq=2,stamp_secs=104,stamp_nsecs=0,frame_id='innolidar',now=14)['state']
assert state['track_status']=='lost' and state['position_source_m'] is None
assert state['range_m'] is None and state['bbox_source_min_m'] is None and not state['bbox_observed']
core=selected()
state=core.process(cloud()+[4,0,0],10.1,seq=2,stamp_secs=100,stamp_nsecs=100000000,frame_id='innolidar',now=10.1)['state']
assert state['track_status']=='occluded' and state['position_predicted']
assert state['position_source_m'][0]<4 and not state['bbox_observed'] and state['range_m'] is None
print('BOARD_GEOMETRY_BOUNDARIES=2/2 PASS')
