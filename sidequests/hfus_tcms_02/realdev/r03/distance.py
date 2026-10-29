"""Spherical range image over FIT rows. Every valid row enters the CSR; holes stay UNKNOWN."""
import numpy as np
from s2core import validity


def angles(p):
    r = np.sqrt(np.einsum('ij,ij->i', p, p))
    az = np.arctan2(p[:, 1], p[:, 0])
    el = np.arctan2(p[:, 2], np.hypot(p[:, 0], p[:, 1]))
    return r, az, el


def bins(az, el, naz, nel):
    ia = np.floor((az + np.pi) * (naz / (2 * np.pi))).astype(np.int32)
    ie = np.floor((el + np.pi / 2) * (nel / np.pi)).astype(np.int32)
    np.clip(ia, 0, naz - 1, out=ia)
    np.clip(ie, 0, nel - 1, out=ie)
    return ie.astype(np.int64) * naz + ia


def build(source, frames, naz, nel, stored=()):
    nb = naz * nel
    nearest = np.full(nb, np.inf, dtype=np.float32)
    nearest_row = np.full(nb, -1, dtype=np.int64)
    count = np.zeros(nb, dtype=np.int64)
    rmax = np.full(nb, -np.inf, dtype=np.float32)
    all_bins = []
    all_rows = []
    per_frame = {}
    stored = set(stored)
    for fi in frames:
        f = source.frame(fi)
        p = f['xyz']
        ok = validity(p)[1]
        pv = p[ok]
        if not len(pv):
            continue
        r, az, el = angles(pv)
        b = bins(az, el, naz, nel)
        count += np.bincount(b, minlength=nb)
        np.maximum.at(rmax, b, r.astype(np.float32))
        all_bins.append(b.astype(np.int32))
        all_rows.append((np.flatnonzero(ok).astype(np.int64) + f['offset']).astype(np.int32))
        order = np.lexsort((r, b))
        bs = b[order]
        first = np.r_[True, bs[1:] != bs[:-1]]
        bid = bs[first]
        rfirst = r[order][first].astype(np.float32)
        better = rfirst < nearest[bid]
        nearest[bid[better]] = rfirst[better]
        nearest_row[bid[better]] = all_rows[-1][order[first][better]]
        if fi in stored:
            fr = np.full(nb, np.inf, dtype=np.float32)
            fr[bid] = rfirst
            per_frame[fi] = fr
    b = np.concatenate(all_bins)
    rows = np.concatenate(all_rows)
    order = np.argsort(b, kind='stable')
    rows = rows[order]
    indptr = np.r_[0, np.cumsum(np.bincount(b, minlength=nb))].astype(np.int64)
    del b, all_bins, all_rows
    return dict(naz=naz, nel=nb // naz, nearest=nearest, nearest_row=nearest_row, count=count,
                rmax=rmax, indptr=indptr, rows=rows, per_frame=per_frame)


def stats(image):
    occ = image['count'] > 0
    az_cov = occ.reshape(image['nel'], image['naz']).any(axis=0).mean()
    el_cov = occ.reshape(image['nel'], image['naz']).any(axis=1).mean()
    seam = (image['count'].reshape(image['nel'], image['naz'])[:, 0] > 0).mean()
    return dict(bins=int(image['count'].size), occupied=int(occ.sum()),
                hole_fraction=float(1 - occ.mean()), rows_in_csr=int(len(image['rows'])),
                mean_rows_per_occupied_bin=float(image['count'][occ].mean()),
                azimuth_bins_with_data=float(az_cov), elevation_bins_with_data=float(el_cov),
                seam_column_occupied=float(seam))
