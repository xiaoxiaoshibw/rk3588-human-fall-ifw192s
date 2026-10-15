"""Direct XYZ point-part learner. Requires human-reviewed labels; no geometry pseudo-labels."""
import json
from pathlib import Path

import numpy as np
import torch
import yaml
from sklearn.metrics import confusion_matrix
from torch import nn

from core import PARTS, R, T
from run import HERE, OUT, ROOT, dump, sha
from server import validate_review


class PointPartNet(nn.Module):
    """Small PointNet-style local features + symmetric global max, not official reproduction."""
    def __init__(self):
        super().__init__()
        self.local = nn.Sequential(nn.Conv1d(3, 32, 1), nn.ReLU(), nn.Conv1d(32, 64, 1), nn.ReLU())
        self.part = nn.Sequential(nn.Conv1d(128, 64, 1), nn.ReLU(), nn.Conv1d(64, len(PARTS), 1))

    def forward(self, x):
        local = self.local(x)
        global_feature = local.amax(dim=2, keepdim=True).expand_as(local)
        return self.part(torch.cat([local, global_feature], dim=1))


def main():
    cfg = yaml.safe_load((HERE/'config.yaml').read_text(encoding='utf-8'))
    path = HERE/'labels/human_parts.jsonl'
    if not path.exists():
        dump(OUT/'part_model_status.json', {'status': 'BLOCKED', 'reason': 'NO_HUMAN_ANATOMICAL_POINT_LABELS',
                                           'classes': PARTS, 'training_started': False, 'labels_generated_from_geometry': False})
        print('Part training BLOCKED: no human-reviewed anatomical point labels')
        return
    catalog = json.loads((OUT/'catalog.json').read_text(encoding='utf-8'))
    grouped = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        row = json.loads(line)
        frame = json.loads((OUT/row['session_id']/f"{row['frame_index']:04d}.json").read_text(encoding='utf-8'))
        validate_review(row, catalog, frame)
        key = (row['session_id'], row['frame_index'], row['object_scope'], row['object_id'])
        if key not in grouped:
            obj = next(o for o in frame[row['object_scope']] if o['id'] == row['object_id'])
            grouped[key] = {'obj': obj, 'labels': {}}
        for index in row['source_indices']:
            grouped[key]['labels'][index] = PARTS.index(row['part_class'])
    sessions = sorted({k[0] for k in grouped})
    known_classes = {v for g in grouped.values() for v in g['labels'].values() if v != 0}
    if len(sessions) < 2 or len(known_classes) < 2:
        dump(OUT/'part_model_status.json', {'status': 'BLOCKED', 'reason': 'NEED_TWO_SESSION_GROUPS_AND_TWO_REVIEWED_PART_CLASSES',
                                           'sessions': sessions, 'known_classes': list(known_classes), 'training_started': False})
        print('Part training BLOCKED: insufficient reviewed session/class coverage')
        return
    test_session = sessions[-1]
    examples = []
    for (sid, fi, _, _), g in grouped.items():
        meta = json.loads((ROOT/'captures/remote'/sid/'meta.json').read_text(encoding='utf-8'))
        rec = next(s for s in catalog['sessions'] if s['session_id'] == sid)
        if sha(ROOT/'captures/remote'/sid/'meta.json') != rec['source_sha256']['meta'] or sha(ROOT/'captures/remote'/sid/'points.bin') != rec['source_sha256']['points']:
            raise ValueError('Source drift before part training')
        raw = np.memmap(ROOT/'captures/remote'/sid/'points.bin', dtype='u1', mode='r')
        xyz = np.ndarray((meta['total_points'], 3), dtype='<f4', buffer=raw, strides=(28, 4))
        ids = np.array(g['obj']['source_indices'], dtype=int)
        # Keep all reviewed points, then sample unlabelled context; unknown means ignore, not background.
        labelled = np.array([i for i in ids if g['labels'].get(int(i), 0) != 0], dtype=int)
        context = np.setdiff1d(ids, labelled)
        capacity = max(0, cfg['part_train_max_points']-len(labelled))
        if len(context) > capacity:
            context = context[np.linspace(0, len(context)-1, capacity, dtype=int)]
        ids = np.r_[labelled, context]
        points = xyz[meta['frames'][fi]['offset_points']+ids].astype('f4') @ R.T + T
        points -= points.mean(axis=0)
        targets = np.array([g['labels'].get(int(i), 0) or -100 for i in ids], dtype='i8')
        if np.any(targets != -100):
            examples.append((sid, torch.tensor(points.T, dtype=torch.float32)[None], torch.from_numpy(targets)[None]))
    train = [e for e in examples if e[0] != test_session]
    test = [e for e in examples if e[0] == test_session]
    if not train or not test:
        raise ValueError('No disjoint supervised train/test examples')
    torch.set_num_threads(2)
    torch.manual_seed(cfg['seed'])
    model = PointPartNet()
    opt = torch.optim.Adam(model.parameters(), lr=cfg['part_train_lr'])
    loss = nn.CrossEntropyLoss(ignore_index=-100)
    model.train()
    for _ in range(cfg['part_train_epochs']):
        for _, x, y in train:
            opt.zero_grad()
            error = loss(model(x), y)
            error.backward()
            opt.step()
    model.eval()
    labels, preds = [], []
    with torch.no_grad():
        for _, x, y in test:
            keep = y[0].numpy() != -100
            labels.extend(y[0].numpy()[keep].tolist())
            preds.extend(model(x).argmax(dim=1)[0].numpy()[keep].tolist())
    torch.save(model.state_dict(), OUT/'pointpart_shadow.pt')
    dump(OUT/'part_model_status.json', {'status': 'SHADOW_TRAINED', 'label_sha256': sha(path),
                                       'classes': PARTS, 'training_sessions': sessions[:-1], 'test_session': test_session,
                                       'confusion_matrix': confusion_matrix(labels, preds, labels=list(range(len(PARTS)))).tolist(),
                                       'annotated_test_points': len(labels), 'unknown_points_excluded': True,
                                       'limits': 'Grouped development check; no new-person/new-scene anatomical accuracy claim'})


if __name__ == '__main__':
    main()
