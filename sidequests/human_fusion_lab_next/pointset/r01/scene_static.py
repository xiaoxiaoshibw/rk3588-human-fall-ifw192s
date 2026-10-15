"""Protected reference anchors and measured full-FOV change proposals."""
import numpy as np
from core import roi_mask, SLOTS, independence


def static_reference_mask(points, valid, polygon):
    if np.shape(points) != (len(valid),3): raise ValueError('N XYZ rows and N validity flags required')
    return np.asarray(valid, bool) & ~roi_mask(points, polygon)


def change_proposals(p, foreground, groups, cfg, distances, tolerance, body):
    selected = set(body[0]['source_indices']) if body else set()
    result = []
    for index, group in enumerate(groups):
        ids = foreground[group]; q = p[ids]
        sample = np.linspace(0,len(ids)-1,min(len(ids),cfg['display_sample_points']),dtype=int)
        center = q.mean(axis=0); values, axes = np.linalg.eigh(np.cov(q.T))
        values = np.maximum(values,0.); scale = max(float(values[-1]),np.finfo(float).eps)
        local = (q-center) @ axes
        extent = np.quantile(local,.98,axis=0)-np.quantile(local,.02,axis=0)
        quality = independence(q,distances[ids],p[np.setdiff1d(foreground,ids)],tolerance,cfg)
        quality['separation_status'] = 'GEOMETRIC_DIAGNOSTIC_ONLY'
        is_body = set(ids.tolist()) == selected
        # No body template on unknown furniture/noise proposals. Only the chosen
        # candidate inherits current-point-supported regional estimates.
        skeleton = body[0]['skeleton'] if is_body else {'nodes':{n:{'valid':False,'xyz':None,
            'support_source_indices':[],'reason':'UNCLASSIFIED_CHANGE_CLUSTER'} for n in SLOTS},'edges':[]}
        result.append({'id':'NEW-3D-'+str(index),'kind':'AUTOMATIC_CANDIDATE',
            'point_count':len(ids),'source_indices':ids.tolist(),'points':np.round(q[sample],4).tolist(),
            'display_source_indices':ids[sample].tolist(),'bbox':{'min':q.min(axis=0).tolist(),'max':q.max(axis=0).tolist()},
            'roi_point_fraction':float(roi_mask(q,cfg['roi_xy']).mean()),'independence':quality,'skeleton':skeleton,
            'pointnet_prob':0.,'rf_xyz_prob':0.,'model_status':'MEASURED_3D_CHANGE_NOT_SEMANTIC_CLASSIFIER',
            'semantic_identity':'UNKNOWN','selected_target_candidate':is_body,
            'geometry':{'centroid':center.tolist(),'pca_eigenvalues':values.tolist(),'pca_axes':axes.tolist(),
                'oriented_extent_p02_p98_m':extent.tolist(),'height_p10_p50_p90_m':np.quantile(q[:,2],[.1,.5,.9]).tolist(),
                'linearity':float((values[2]-values[1])/scale),'planarity':float((values[1]-values[0])/scale),
                'scattering':float(values[0]/scale),'identity_score':None}})
    return result
