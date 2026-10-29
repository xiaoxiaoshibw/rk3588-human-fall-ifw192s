"""Observed silhouette branches with RAW-XYZ continuity, not anatomical joints.

Image-up is an explicit hypothesis, never gravity. No missing pixels are filled.
Arc-fraction segment boundaries are deliberately not called elbows or knees.
"""
import heapq
import math

import numpy as np

METHOD = 'range_topology_branches_v2'
SETTINGS = dict(min_target_points=40, min_image_aspect=1.35, max_edge_m=.15,
                min_branch_m=.08, full_arm_m=.28, full_leg_m=.45,
                max_region_distance_m=.16, min_region_points=6,
                foot_turn_deg=30., foot_terminal_m=.10, foot_min_span_m=.045)
NAMES = ['head', 'torso']+[s+'_'+b for s in ('upper_arm', 'forearm', 'thigh', 'shin', 'foot') for b in ('1', '2')]


def thin(mask):
    """Zhang-Suen thinning: removes measured cells only; never invents a cell."""
    a = np.pad(mask.astype(np.uint8), 1)
    for _ in range(max(mask.shape)*2):
        changed = False
        for phase in (0, 1):
            p = [a[:-2, 1:-1], a[:-2, 2:], a[1:-1, 2:], a[2:, 2:],
                 a[2:, 1:-1], a[2:, :-2], a[1:-1, :-2], a[:-2, :-2]]
            n = sum(p)
            transitions = sum((p[i] == 0) & (p[(i+1) % 8] == 1) for i in range(8))
            gate = ((p[0]*p[2]*p[4] == 0) & (p[2]*p[4]*p[6] == 0) if phase == 0
                    else (p[0]*p[2]*p[6] == 0) & (p[0]*p[4]*p[6] == 0))
            delete = (a[1:-1, 1:-1] == 1) & (n >= 2) & (n <= 6) & (transitions == 1) & gate
            if delete.any():
                a[1:-1, 1:-1][delete] = 0
                changed = True
        if not changed:
            return a[1:-1, 1:-1].astype(bool)
    raise ValueError('silhouette thinning did not converge')


def graph(mask, indices, xyz):
    yy, xx = np.nonzero(mask)
    lookup = np.full(mask.shape, -1, dtype=np.int32)
    lookup[yy, xx] = np.arange(len(xx))
    points = xyz[indices[yy, xx]].astype(float)
    adjacency = [[] for _ in xx]
    h, w = mask.shape
    # Undirected measured-neighbour edges, no bridge across a missing pixel.
    for dx, dy in ((1, 0), (0, 1), (1, 1), (-1, 1)):
        ok = (xx+dx >= 0) & (xx+dx < w) & (yy+dy < h)
        a = np.flatnonzero(ok)
        b = lookup[yy[a]+dy, xx[a]+dx]
        good = b >= 0
        a, b = a[good], b[good]
        distance = np.linalg.norm(points[a]-points[b], axis=1)
        for ai, bi, weight in zip(a, b, distance):
            if weight <= SETTINGS['max_edge_m']:
                # Nanometre cost quantization makes shortest-path ties stable
                # under floating-point rigid transforms; RAW points stay exact.
                cost = round(float(weight), 9)+.0001*math.hypot(dx, dy)
                adjacency[int(ai)].append((int(bi), cost))
                adjacency[int(bi)].append((int(ai), cost))
    return xx, yy, points, lookup, adjacency


def shortest(adjacency, seeds, limit=float('inf')):
    distances = np.full(len(adjacency), np.inf)
    owners = np.full(len(adjacency), -1, dtype=np.int32)
    previous = np.full(len(adjacency), -1, dtype=np.int32)
    heap = []
    for node, label in seeds:
        distances[node] = 0.
        owners[node] = label
        heapq.heappush(heap, (0., node, label))
    while heap:
        distance, node, label = heapq.heappop(heap)
        if distance != distances[node] or label != owners[node]:
            continue
        for other, weight in adjacency[node]:
            candidate = distance+weight
            if candidate <= limit and candidate < distances[other]-1e-12:
                distances[other], owners[other], previous[other] = candidate, label, node
                heapq.heappush(heap, (candidate, other, label))
    return distances, owners, previous


def torso_root(xx, yy, adjacency, center_x, center_y):
    """Choose on the largest measured ridge component, not an isolated pore loop."""
    seen, largest = set(), []
    for node in range(len(adjacency)):
        if node in seen:
            continue
        todo, component = [node], []
        seen.add(node)
        while todo:
            current = todo.pop()
            component.append(current)
            for other, _ in adjacency[current]:
                if other not in seen:
                    seen.add(other)
                    todo.append(other)
        if len(component) > len(largest):
            largest = component
    candidates = np.asarray(sorted(largest), dtype=int)
    score = (xx[candidates]-center_x)**2+((yy[candidates]-center_y)*1.2)**2
    return int(candidates[np.argmin(score)])


def central_body_regions(mask, reachable, leg_start_y=None):
    """Measured central cap and trunk areas, independent of ridge endpoints.

    Image-profile proportions propose boundaries, not anatomical neck/hip GT.
    Holes stay holes; reachable was computed on the original RAW-neighbour graph.
    """
    height, width = mask.shape
    empty = np.zeros(mask.shape, dtype=bool)
    yy, xx = np.nonzero(mask)
    if not len(xx):
        return empty, empty.copy(), {}, {}
    y0, y1 = int(yy.min()), int(yy.max())
    extent = y1-y0+1
    lo, hi = y0+int(extent*.35), y0+max(int(extent*.35)+1, int(extent*.65))
    occupancy = mask[lo:hi].mean(axis=0)
    supported = occupancy >= .60
    candidates = np.flatnonzero(supported)
    if not len(candidates):
        return empty, empty.copy(), {}, {}
    center = int(candidates[np.argmin(abs(candidates-np.median(xx)))])
    left, right = center, center
    while left > 0 and supported[left-1]:
        left -= 1
    while right+1 < width and supported[right+1]:
        right += 1
    core_width, core_x = right-left+1, (right+left)/2.
    if core_width < 4:
        return empty, empty.copy(), {}, {}

    def row_group(y):
        x = np.flatnonzero(mask[y])
        if not len(x):
            return None
        groups = np.split(x, np.flatnonzero(np.diff(x) > 2)+1)
        group = min(groups, key=lambda g: float(np.min(abs(g-core_x))))
        if np.min(abs(group-core_x)) > core_width*.25:
            return None
        return group

    # The central dome survives raised arms even if thinning has no head endpoint.
    cap_rows, cap_widths, cap_centers = [], [], []
    top = None
    broad = 0
    for y in range(y0, min(height, y0+int(extent*.5)+1)):
        group = row_group(y)
        if group is None or np.min(abs(group-core_x)) > max(1., core_width*.15):
            if top is not None:
                break
            continue
        if top is None:
            top = y
        span = int(group[-1]-group[0]+1)
        if span > core_width*.90:
            broad += 1
            if broad >= 2:
                break
        else:
            broad = 0
            cap_rows.append(y)
            cap_widths.append(span)
            cap_centers.append((int(group[0])+int(group[-1]))/2.)
        if y-top >= core_width:
            break
    head = empty.copy()
    head_info = dict(reason='no_supported_compact_central_cap')
    cap_bottom = None
    if len(cap_rows) >= 3 and max(cap_widths) >= core_width*.35 and top is not None and top > 0:
        cap_width = float(np.median(cap_widths))
        if (core_width*.35 <= cap_width <= extent*.25
                and min(cap_widths) < .8*max(cap_widths)):
            cap_x = float(np.median(cap_centers))
            cap_y = top+cap_width*.5
            gy, gx = np.indices(mask.shape)
            ellipse = ((gx-cap_x)/max(1., cap_width*.60))**2+((gy-cap_y)/max(1., cap_width*.65))**2 <= 1.
            head = mask & reachable & ellipse
            if head.sum() >= SETTINGS['min_region_points']:
                cap_bottom = min(height-1, int(math.ceil(top+cap_width*1.15)))
                head_info = dict(reason='measured_compact_central_cap_depth_connected_to_trunk', capTopY=top,
                    capWidthPx=cap_width, coreWidthPx=core_width,
                    boundary='visible_cap_profile_hypothesis_not_anatomical_neck')
            else:
                head[:] = False
    trunk_top = cap_bottom+1 if cap_bottom is not None else y0+int(extent*.2)
    trunk_bottom = y0+int(extent*.65)
    if cap_bottom is not None:
        trunk_bottom = min(trunk_bottom, cap_bottom+2*core_width)
    if leg_start_y is not None and leg_start_y > trunk_top:
        trunk_bottom = min(trunk_bottom, int(leg_start_y))
    if cap_bottom is not None and trunk_bottom-trunk_top+1 < core_width*.8:
        return empty, empty.copy(), dict(reason='compact_cap_without_resolved_trunk'), dict(reason='compact_cap_without_resolved_trunk')
    trunk = empty.copy()
    for y in range(trunk_top, min(height, trunk_bottom+1)):
        group = row_group(y)
        if group is None:
            continue
        central = group[abs(group-core_x) <= core_width*.5]
        if not len(central):
            continue
        row_x = float(np.median(central))
        selected = group[abs(group-row_x) <= core_width*.625]
        trunk[y, selected] = reachable[y, selected]
    trunk &= ~head
    trunk_info = dict(reason='measured_central_cross_sections_depth_connected_to_trunk',
        profileRows=[lo, hi], columnSupportFraction=.60, coreWidthPx=core_width,
        torsoRows=[trunk_top, trunk_bottom],
        boundary='cross_section_profile_prior_not_anatomical_shoulder_or_hip')
    return head, trunk, head_info, trunk_info


def propose(indices, xyz, target_rows):
    """Returns all label slots; unsupported slots have no point set."""
    common = ['semantic_hypothesis_not_anatomical_recognition', 'image_up_not_gravity',
              'single_visible_surface_occlusion_and_background_unverified',
              'branch_numbers_are_frame_local_not_anatomical_left_right']
    slots = {name:dict(part=name, state='uncertain', rect=None, origin=dict(kind='automatic', method=METHOD,
             uncertainty=list(common), evidence=dict(reason='no_separable_measured_branch', settings=SETTINGS))) for name in NAMES}

    def reject(reason):
        for slot in slots.values():
            slot['origin']['evidence']['reason'] = reason
        return list(slots.values())

    mask = (indices >= 0) & np.isin(indices, target_rows)
    all_y, all_x = np.nonzero(mask)
    if len(all_x) < SETTINGS['min_target_points']:
        return reject('missing_target_or_insufficient_support')
    x0, x1, y0, y1 = int(all_x.min()), int(all_x.max()), int(all_y.min()), int(all_y.max())
    height, width = y1-y0+1, x1-x0+1
    profile = mask[y0+int(height*.35):y0+max(int(height*.35)+1, int(height*.65))].sum(axis=1)
    torso_width = max(1., float(np.median(profile)))
    if height/torso_width < SETTINGS['min_image_aspect']:
        return reject('upright_image_hypothesis_not_supported_bent_or_ambiguous_shape')
    # Crop only for thinning speed; original pixel identity remains unchanged.
    skeleton = np.zeros(mask.shape, dtype=bool)
    skeleton[y0:y1+1, x0:x1+1] = thin(mask[y0:y1+1, x0:x1+1])
    xx, yy, points, lookup, adjacency = graph(skeleton, indices, xyz)
    center_x = float(np.median(all_x))
    if not len(xx):
        return reject('no_observed_silhouette_ridge')
    root = torso_root(xx, yy, adjacency, center_x, y0+.48*height)
    distances, _, previous = shortest(adjacency, [(root, 0)])
    paths = {}
    for node, neighbours in enumerate(adjacency):
        if len(neighbours) != 1 or not np.isfinite(distances[node]) or distances[node] < SETTINGS['min_branch_m']:
            continue
        path, cursor = [], node
        while cursor != -1:
            path.append(int(cursor))
            cursor = int(previous[cursor])
        paths[node] = path[::-1]
    heads, arms, legs = [], [], []
    for end in paths:
        if yy[end] < y0+.32*height and abs(xx[end]-center_x) <= max(2., width*.14):
            heads.append(end)
        elif yy[end] >= y0+.80*height:
            legs.append(end)
        elif abs(xx[end]-center_x) >= max(3., width*.18):
            arms.append(end)

    def select(endpoints):
        chosen = []
        for end in sorted(endpoints, key=lambda i: (-distances[i], int(xx[i]), int(yy[i]))):
            if all(abs(xx[end]-xx[other]) >= max(3, width*.08)
                   and np.linalg.norm(points[end]-points[other]) >= .08 for other in chosen):
                chosen.append(end)
            if len(chosen) == 2:
                break
        return sorted(chosen, key=lambda i: (int(xx[i]), int(yy[i])))

    arms, legs = select(arms), select(legs)
    head = min(heads, key=lambda i: (abs(xx[i]-center_x), -distances[i])) if heads else None
    ends = arms+legs+([head] if head is not None else [])
    if len(ends) < 3:
        # Head/trunk regions can be observed without three resolved limbs.
        ends = []
    use = np.zeros(len(xx), dtype=int)
    for end in ends:
        use[paths[end]] += 1
    regions, evidence = {}, {}
    backbone = np.flatnonzero((use >= 2) & (yy >= y0+.2*height) & (yy <= y0+.65*height)).tolist()
    if backbone:
        regions['torso'] = backbone
        evidence['torso'] = dict(reason='shared_observed_branch_backbone', seedSourceRows=indices[yy[backbone], xx[backbone]].tolist())

    def unique_path(end):
        path = paths[end]
        start = len(path)-1
        while start > 0 and use[path[start-1]] == 1:
            start -= 1
        return path[start:]

    if head is not None:
        regions['head'] = unique_path(head)
        evidence['head'] = dict(reason='central_upper_terminal_branch_hypothesis')

    for family, endpoints in [('arm', arms), ('leg', legs)]:
        for number, end in enumerate(endpoints, 1):
            path = unique_path(end)
            if len(path) < 3:
                continue
            p = points[path]
            arc = np.r_[0., np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
            length = float(arc[-1])
            if length < SETTINGS['min_branch_m']:
                continue
            base = dict(reason='observed_separable_terminal_branch', branchFamily=family,
                arcLengthM=length, attachmentPixel=[int(xx[path[0]]), int(yy[path[0]])],
                endpointPixel=[int(xx[end]), int(yy[end])], pathSourceRows=indices[yy[path], xx[path]].tolist())
            foot_start = len(path)
            if family == 'leg' and length >= .2 and len(path) >= 8:
                terminal = max(1, int(np.searchsorted(arc, max(0., length-SETTINGS['foot_terminal_m']))))
                before = max(0, int(np.searchsorted(arc, max(0., arc[terminal]-.16))))
                distal, proximal = p[-1]-p[terminal], p[terminal]-p[before]
                dn, pn = float(np.linalg.norm(distal)), float(np.linalg.norm(proximal))
                if dn > 1e-9 and pn > 1e-9:
                    angle = float(np.degrees(np.arccos(np.clip(abs(np.dot(distal, proximal)/(dn*pn)), 0, 1))))
                    if (angle >= SETTINGS['foot_turn_deg'] and dn >= SETTINGS['foot_min_span_m']
                            and pn >= .08 and len(path)-terminal >= 3
                            and 0 < xx[end] < mask.shape[1]-1 and 0 < yy[end] < mask.shape[0]-1):
                        foot_start = terminal
                        name = 'foot_'+str(number)
                        regions[name] = path[terminal:]
                        evidence[name] = dict(base, reason='measured_distal_turn_foot_hypothesis', terminalTurnDeg=angle,
                            terminalSpanM=dn, groundContact='UNKNOWN')
            rest = path[:foot_start]
            proximal_name, distal_name = ('upper_arm', 'forearm') if family == 'arm' else ('thigh', 'shin')
            full_length = SETTINGS['full_arm_m'] if family == 'arm' else SETTINGS['full_leg_m']
            if length >= full_length and len(rest) >= 8:
                split = max(2, min(len(rest)-2, int(np.searchsorted(arc[:len(rest)], arc[len(rest)-1]*.5))))
                for name, nodes in [(proximal_name, rest[:split]), (distal_name, rest[split:])]:
                    regions[name+'_'+str(number)] = nodes
                    evidence[name+'_'+str(number)] = dict(base, segmentBoundary='half_observed_arc_not_anatomical_joint')
            else:
                name = distal_name+'_'+str(number)
                regions[name] = rest
                evidence[name] = dict(base, reason='distal_support_only_proximal_shared_or_unresolved')
    # Compete on the original measured neighbour graph; never use a rectangular
    # bounding box to fill between a limb and the torso or across a depth edge.
    fx, fy, _, full_lookup, full_graph = graph(mask, indices, xyz)
    root_node = int(full_lookup[yy[root], xx[root]])
    root_distances, _, _ = shortest(full_graph, [(root_node, 0)])
    reachable = np.zeros(mask.shape, dtype=bool)
    reachable[fy, fx] = np.isfinite(root_distances)
    leg_starts = [int(yy[unique_path(end)[0]]) for end in legs if len(unique_path(end)) >= 3]
    head_area, trunk_area, head_info, trunk_info = central_body_regions(mask, reachable, min(leg_starts) if leg_starts else None)
    if not head_area.any() and len(ends) < 3:
        trunk_area[:] = False
        trunk_info = dict(reason='no_compact_cap_or_branch_supported_trunk')
    interior = trunk_area.copy()
    for _ in range(2):
        padded = np.pad(interior, 1)
        interior = interior & padded[:-2, 1:-1] & padded[2:, 1:-1] & padded[1:-1, :-2] & padded[1:-1, 2:]
    protected = head_area | interior
    # Full measured body-region seeds take precedence over nearby limb paths.
    regions.pop('head', None)
    regions.pop('torso', None)
    node_seeds = {name:[int(full_lookup[yy[node], xx[node]]) for node in nodes
                       if not protected[yy[node], xx[node]]] for name,nodes in regions.items()}
    limb_band = set()
    for nodes in node_seeds.values():
        for node in nodes:
            limb_band.add(node)
            limb_band.update(other for other, _ in full_graph[node]
                             if not protected[fy[other], fx[other]])
    for name, area, info in [('head', head_area, head_info), ('torso', trunk_area, trunk_info)]:
        info.setdefault('reason', 'no_measured_central_profile')
        node_seeds[name] = [int(node) for node in full_lookup[area]
                            if name == 'head' or int(node) not in limb_band]
        evidence[name] = info
        slots[name]['origin']['evidence'] = dict(info, settings=SETTINGS)
    names = list(node_seeds)
    seeds = [(node, label) for label, name in enumerate(names) for node in node_seeds[name]]
    _, owners, _ = shortest(full_graph, seeds, SETTINGS['max_region_distance_m'])
    for label, name in enumerate(names):
        selected = owners == label
        if name in ('head', 'torso'):
            area = head_area if name == 'head' else trunk_area
            selected &= area[fy, fx]
        else:
            selected &= ~protected[fy, fx]
        if name.startswith(('upper_arm', 'forearm')) and not head_area.any() and backbone:
            # Raised hands may be the only upper endpoints. The unresolved
            # central cap must not be consumed as an arm just because it is near.
            selected &= ~((abs(fx-center_x) <= max(3., width*.14)) & (fy < yy[backbone].min()))
        ids = np.flatnonzero(selected)
        if len(ids) < SETTINGS['min_region_points']:
            if name not in ('head', 'torso'):
                slots[name]['origin']['evidence']['reason'] = 'limb_path_in_body_core_or_insufficient_visible_boundary_support'
            continue
        pixels = (fy[ids]*indices.shape[1]+fx[ids]).tolist()
        info = dict(evidence[name], supportCount=len(ids), maxEdgeM=SETTINGS['max_edge_m'], settings=SETTINGS)
        uncertainty = list(common)
        if 'segmentBoundary' in info:
            uncertainty.append('upper_lower_split_is_arc_fraction_not_elbow_or_knee')
        if name.startswith('foot'):
            uncertainty.append('distal_turn_can_be_shoe_floor_contamination_or_other_surface_not_verified_foot')
        slots[name] = dict(part=name, state='visible', rect=None, pixels=pixels,
            origin=dict(kind='automatic', method=METHOD, uncertainty=uncertainty, evidence=info))
    return list(slots.values())
