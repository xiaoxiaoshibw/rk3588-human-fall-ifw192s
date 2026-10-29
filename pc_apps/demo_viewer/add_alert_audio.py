"""Add quiet beeps only within the displayed offline alert intervals."""
import argparse
import json
import math
import subprocess
import wave
from pathlib import Path
import numpy as np


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--video',type=Path,required=True)
    p.add_argument('--evidence',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    if args.out.exists(): raise FileExistsError(args.out)
    manifest=json.loads((args.evidence/'MANIFEST.json').read_text(encoding='utf8'))
    rows=[json.loads(line) for line in (args.evidence/'frames.jsonl').read_text(encoding='utf8').splitlines()]
    fps=manifest['fps']; rate=16000
    if rate%fps: raise ValueError('frame/sample rate must divide exactly')
    audio=np.zeros(manifest['total_video_frames']*(rate//fps),dtype=np.float64)
    starts=[]; prev=False; last=None
    for row in rows:
        active=row['active']
        if active and (not prev or row['session']!=last): starts.append(row['video_first_frame'])
        prev,last=active,row['session']
        if not active: continue
        start=row['video_first_frame']*(rate//fps); stop=start+row['repeats']*(rate//fps)
        age=np.arange(start,stop)/rate-starts[-1]/fps
        phase=np.mod(age,2.)
        on=((phase>=0)&(phase<.14))|((phase>=.23)&(phase<.37))
        envelope=np.minimum(1.,np.maximum(0.,np.minimum(np.mod(phase,.23), .14-np.mod(phase,.23)))*80)
        audio[start:stop]=on*envelope*np.sin(2*math.pi*880*np.arange(start,stop)/rate)*.12
    wav=args.evidence/'alert_audio.wav'
    with wave.open(str(wav),'wb') as stream:
        stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(rate)
        stream.writeframes((audio*32767).astype('<i2').tobytes())
    result=subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(args.video),'-i',str(wav),
        '-c:v','copy','-c:a','libvo_aacenc','-b:a','96k','-movflags','+faststart',str(args.out)],capture_output=True,check=False)
    (args.evidence/'audio_ffmpeg.log').write_bytes(result.stderr)
    if result.returncode: raise RuntimeError('audio mux failed')
    (args.evidence/'audio_events.json').write_text(json.dumps(dict(fps=fps,first_frames=starts,
        seconds=[x/fps for x in starts],max_abs=float(np.max(np.abs(audio)))),indent=2),encoding='utf8')


if __name__=='__main__': main()
