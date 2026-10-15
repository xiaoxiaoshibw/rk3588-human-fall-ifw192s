"""CPU point/image/fusion operation graphs. Random graphs are resource probes only."""
import hashlib
import numpy as np
from scipy.spatial import cKDTree
import torch
from torch import nn
from torch.nn import functional as F


def state_sha(net):
    h = hashlib.sha256()
    for k, v in sorted(net.state_dict().items()):
        h.update(k.encode()); h.update(str(v.dtype).encode()); h.update(str(tuple(v.shape)).encode())
        h.update(v.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()


def point_inputs(xyz, risk=None):
    """5cm voxels and local16 neighborhoods; every original member returns via inverse."""
    q = np.asarray(xyz, dtype='f4')
    if q.ndim != 2 or q.shape[1] != 3 or not len(q) or not np.isfinite(q).all():
        raise ValueError('Finite nonempty source U required')
    _, inv = np.unique(np.floor(q/.05).astype('i4'), axis=0, return_inverse=True)
    counts = np.bincount(inv)
    centers = np.column_stack([np.bincount(inv, weights=q[:, i])/counts for i in range(3)])
    _, near = cKDTree(centers).query(centers, k=min(16, len(centers)))
    if near.ndim == 1: near = near[:, None]
    relative = centers[near]-centers[:, None]
    geometry = np.c_[centers, relative.mean(1), (relative**2).mean(1), np.log1p(counts)]
    risk_known = risk is not None
    risk = np.zeros(len(q), dtype='f4') if risk is None else np.asarray(risk, dtype='f4')
    if risk.shape != (len(q),) or not np.isfinite(risk).all(): raise ValueError('Risk schema')
    features = np.c_[q, np.linalg.norm(q, axis=1), risk, np.full(len(q), float(risk_known)), geometry[inv]]
    return torch.from_numpy(features.astype('f4'))


def image_inputs(raw, rows, projections, h, w):
    """Four independent range/axial K2 slots. Empty masks remain explicit."""
    images = np.zeros((1, 24, h*w), dtype='f4')
    mapping = np.full((len(raw), 4), -1, dtype='i8')
    for j, pr in enumerate(projections):
        for layer in range(2):
            k = j*2+layer; ids = pr['layers'][:, layer]; good = ids >= 0
            ids = ids[good]; pixels = pr['pixels'][good].astype('i8')
            depth = np.linalg.norm(raw[ids], axis=1) if j == 0 else raw[ids, 0]
            images[0, k*6:k*6+3, pixels] = raw[ids]
            images[0, k*6+3, pixels] = depth
            images[0, k*6+4, pixels] = 1
            images[0, k*6+5, pixels] = np.log1p(np.diff(pr['offsets'])[good])
            mapping[ids, k] = pixels
    return torch.from_numpy(images.reshape(1, 24, h, w)), torch.from_numpy(mapping[rows])


class Frontend(nn.Module):
    def __init__(self, family, wide=False):
        super().__init__()
        if family not in ['L3D', 'L2D', 'LFUSION']: raise ValueError('Unknown family')
        self.family = family
        width = 24 if wide else 16
        channels = [16, 32, 64, 128]+([128] if wide else [])
        if family != 'L2D':
            layers = []
            for a, b in zip(channels, channels[1:]): layers += [nn.Linear(a, b), nn.ReLU(), nn.Dropout(.1)]
            self.point = nn.Sequential(*layers)
        if family != 'L3D':
            self.enc = nn.Sequential(nn.Conv2d(24, width, 3, padding=1), nn.ReLU(),
                                     nn.Conv2d(width, width*2, 3, stride=2, padding=1), nn.ReLU())
            self.dec = nn.Sequential(nn.Conv2d(width*2, width, 3, padding=1), nn.ReLU(), nn.Conv2d(width, 32, 1))
            self.image = nn.Linear(32*4+4, 128)
        self.fuse = nn.Linear(256, 128) if family == 'LFUSION' else nn.Identity()
        self.semantic = nn.Linear(128, 1)
        self.query = nn.Parameter(torch.randn(4, 128)*.02)
        self.object = nn.Linear(128, 1)
        self.joint = nn.Linear(128, 13*4)

    def forward(self, point, image=None, mapping=None):
        p = self.point(point) if self.family != 'L2D' else None
        visible = torch.ones(len(point), dtype=torch.bool, device=point.device)
        if self.family != 'L3D':
            # Masked source channels: missing pixels never acquire synthetic depth.
            valid = image[:, [4, 10, 16, 22]].amax(1, keepdim=True)
            encoded = self.enc(image)
            z = self.dec(F.interpolate(encoded, size=image.shape[-2:], mode='bilinear', align_corners=False))*valid
            flat = z[0].flatten(1).T
            mask = mapping >= 0
            gathered = flat[mapping.clamp_min(0)]*mask[:, :, None]
            im = self.image(torch.cat([gathered.flatten(1), mask.float()], 1))
            visible = mask.any(1)
            feature = im if self.family == 'L2D' else self.fuse(torch.cat([p, im], 1)).relu()
        else: feature = p
        pooled = feature.mean(0)[None]+self.query
        return dict(logit=self.semantic(feature).squeeze(-1), valid=visible,
                    query_human_logit=self.object(pooled).squeeze(-1),
                    mask_logit=feature@pooled.T/(128**.5),
                    inferred_joints=self.joint(pooled).reshape(4, 13, 4),
                    role='UNTRAINED_RESOURCE_GRAPH_NOT_SEMANTICS')


def gated_loss(output, targets, trusted_instance_complete=False, instance_targets=None, joint_targets=None):
    known = (targets >= 0) & output['valid']
    loss = F.binary_cross_entropy_with_logits(output['logit'][known], targets[known].float()) if known.any() else output['logit'].sum()*0
    # Hungarian instance supervision is only possible after exhaustive trusted membership.
    if trusted_instance_complete:
        if instance_targets is None: raise ValueError('Exhaustive instance targets required')
        from scipy.optimize import linear_sum_assignment
        target = instance_targets.float()
        if target.ndim != 2 or target.shape[0] != len(targets) or target.shape[1] > 4: raise ValueError('Instance target shape')
        if not known.any(): raise ValueError('Trusted instance supervision needs known source points')
        if target.shape[1]:
            costs = torch.stack([torch.stack([F.binary_cross_entropy_with_logits(output['mask_logit'][known, i], target[known, j])
                                             for j in range(target.shape[1])]) for i in range(4)])
            a, b = linear_sum_assignment(costs.detach().numpy())
            for i, j in zip(a, b): loss = loss+costs[i, j]
        else: a = np.empty(0, dtype=int)
        object_gt = torch.zeros(4); object_gt[a] = 1
        loss = loss+F.binary_cross_entropy_with_logits(output['query_human_logit'], object_gt)
    if joint_targets is not None:
        raise ValueError('Independent joint GT/adapter gate not satisfied')
    return loss


def load_bound_weights(net, path, expected_sha):
    from contracts import sha
    if sha(path) != expected_sha: raise ValueError('Model SHA drift')
    state = torch.load(path, map_location='cpu', weights_only=True)
    if not isinstance(state, dict) or any(not torch.is_tensor(v) or not torch.isfinite(v).all() for v in state.values()):
        raise ValueError('Invalid/nonfinite model state')
    net.load_state_dict(state, strict=True)
    return net
