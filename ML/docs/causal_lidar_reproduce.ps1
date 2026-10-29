#requires -Version 7.4
# Run from D:\Code\ldiar. Choose NEW output/model/data paths for each repeat.
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
$evidence = 'docs/evidence/2026-10-22_causal_lidar_repeat'
$models = 'ML/models/causal_lidar_20261022_repeat'
$download = 'data/downloads/causal_lidar_20261022_repeat'
python -B -W error ML/src/public_lidar_audit.py baseline $evidence
python -B -W error ML/src/causal_public_lidar.py extract --input data/downloads/public_lidar_20261022/E01_lidar_gt.zip --output "$evidence/E01_cache"
python -B -W error ML/src/causal_public_lidar.py develop --input "$evidence/E01_cache/frames.npz" --output $evidence --models $models
python -B -W error ML/src/download_mmfi_environment.py --env E02 --evidence "$evidence/E02_download" --destination $download --freeze "$evidence/FREEZE.json"
python -B -W error ML/src/causal_public_lidar.py extract --input "$download/E02_lidar_gt.zip" --output "$evidence/E02_cache"
python -B -W error ML/src/causal_public_lidar.py external --input "$evidence/E02_cache/frames.npz" --output $evidence --models $models --freeze "$evidence/FREEZE.json"
python -B -W error ML/src/export_lidar_rf.py "$models/w30_final.joblib" "$models/w30_numpy.npz"
python -B -W error ML/src/replay_causal_lidar.py --session data/sessions/cap_20261018_110029 --model "$models/w30_numpy.npz" --output "$evidence/raw_replay"
python -B -W error ML/src/validate_lidar_export.py --models $models --evidence $evidence
python -B -W error ML/src/evaluate_external_baseline.py --evidence $evidence --models $models
python -B -W error ML/src/public_lidar_audit.py targets $evidence
python -B -W error ML/src/analyze_causal_results.py --evidence $evidence --models $models
python -B -W error -m unittest discover -s ML/src -p 'test*lidar.py' -v
python -B -W error -m unittest discover -s src/human_fall_detection/tests
python -B -W error -m unittest discover -s src/human_capture/tests
python -B -W error ML/src/finalize_causal_lidar.py --evidence $evidence --models $models
