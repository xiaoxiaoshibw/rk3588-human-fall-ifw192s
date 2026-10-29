#!/usr/bin/env python3
"""Verify the *actual* lidar input source of the running driver.

Why this exists: ``header.seq`` continuity, the topic name, or a config file
lying around in the repository do not prove where the points come from. This
tool reads the real process:

* the driver process actually publishing the cloud topic (its cmdline and the
  ``_config_path:=`` it was started with),
* the SHA of that effective YAML plus its ``msg_source`` / ``pcap_file`` /
  ``pcap_repeat`` values,
* the open file descriptors of that process (an open ``.pcap`` is positive
  evidence of replay; no pcap fd with ``msg_source: 1`` is consistent with the
  live sensor),
* the ROS publisher registration (when ``rosnode`` is available).

Output is ``live_lidar`` / ``pcap`` / ``unknown`` with the evidence attached.
It never upgrades to ``live_lidar`` just because nothing contradicted it, unless
``msg_source == 1`` *and* no pcap file is open *and* the publisher registration
matches. Anything else stays ``unknown``.

Exit codes: 0 = live_lidar, 4 = pcap, 3 = unknown, 2 = ROS/proc unavailable.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time


def _read_cmdline(pid):
    try:
        with open('/proc/%s/cmdline' % pid, 'rb') as handle:
            raw = handle.read()
    except OSError:
        return []
    return [part.decode('utf-8', 'replace') for part in raw.split(b'\0') if part]


def _read_fds(pid):
    directory = '/proc/%s/fd' % pid
    links = []
    try:
        names = os.listdir(directory)
    except OSError:
        return links
    for name in sorted(names):
        try:
            target = os.readlink(os.path.join(directory, name))
        except OSError:
            continue
        links.append({'fd': name, 'target': target})
    return links


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def _load_yaml(path):
    try:
        import yaml
    except ImportError:
        return None, 'pyyaml_missing'
    try:
        with open(path, encoding='utf-8') as handle:
            return yaml.safe_load(handle) or {}, None
    except (OSError, ValueError) as exc:
        return None, str(exc)


def find_driver_processes(needle='inno_lidar_node'):
    found = []
    try:
        entries = os.listdir('/proc')
    except OSError:
        return found
    for name in sorted(entries):
        if not name.isdigit():
            continue
        cmdline = _read_cmdline(name)
        if not cmdline:
            continue
        if any(needle in part for part in cmdline):
            found.append((int(name), cmdline))
    return found


def _rosnode_info(node_name):
    try:
        result = subprocess.run(['rosnode', 'info', node_name],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                timeout=6, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return {'available': False, 'detail': str(exc)}
    text = result.stdout.decode('utf-8', 'replace')
    publishers = []
    subscribers = []
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith('Publications:'):
            current = publishers
        elif stripped.startswith('Subscriptions:'):
            current = subscribers
        elif stripped.startswith('* /') and current is not None:
            current.append(stripped[2:].split()[0])
    return {'available': True, 'publishers': publishers, 'subscribers': subscribers,
            'exit_code': result.returncode}


def decide_mode(msg_source, open_pcap):
    """Map the observed driver facts to ``live_lidar`` / ``pcap`` / ``unknown``.

    Deliberately conservative: ``live_lidar`` needs ``msg_source == 1`` *and* no
    open pcap file. An open pcap with ``msg_source == 1`` (an inconsistent
    process) is ``unknown``, never silently promoted to live.
    """
    if open_pcap and msg_source != 1:
        return 'pcap'
    if msg_source == 2:
        return 'pcap'
    if msg_source == 1 and not open_pcap:
        return 'live_lidar'
    return 'unknown'


def inspect(publisher_hint=None):
    evidence = {'kind': 'input_source_evidence', 'schema_version': 1,
                'checked_at': time.time(), 'mode': 'unknown', 'reason': None,
                'candidates': []}
    processes = find_driver_processes()
    if not processes:
        evidence['reason'] = 'no_driver_process_found'
        return evidence
    for pid, cmdline in processes:
        entry = {'pid': pid, 'cmdline': cmdline, 'node_name': None,
                 'config_path': None, 'config_sha256': None, 'msg_source': None,
                 'pcap_file': None, 'pcap_repeat': None,
                 'open_pcap_files': [], 'open_files_sampled': 0}
        text = ' '.join(cmdline)
        if '__name:=' in text:
            entry['node_name'] = text.split('__name:=', 1)[1].split()[0]
        config_path = None
        for part in cmdline:
            if '_config_path:=' in part:
                config_path = part.split('_config_path:=', 1)[1]
        entry['config_path'] = config_path
        if config_path and os.path.isfile(config_path):
            entry['config_sha256'] = _sha256(config_path)
            config, error = _load_yaml(config_path)
            entry['config_error'] = error
            if isinstance(config, dict):
                entry['msg_source'] = (config.get('common') or {}).get('msg_source')
                lidars = config.get('lidar') or []
                if lidars and isinstance(lidars[0], dict):
                    driver = lidars[0].get('driver') or {}
                    entry['pcap_file'] = driver.get('pcap_file')
                    entry['pcap_repeat'] = driver.get('pcap_repeat')
                    entry['device_type'] = driver.get('lidar_type')
        fds = _read_fds(pid)
        entry['open_files_sampled'] = len(fds)
        for fd in fds:
            target = fd['target']
            if target.endswith('.pcap') or '.pcap' in target:
                entry['open_pcap_files'].append(fd)
        evidence['candidates'].append(entry)

    # Choose the process that looks like the cloud publisher.
    chosen = None
    for entry in evidence['candidates']:
        if publisher_hint and entry.get('node_name') and publisher_hint in entry['node_name']:
            chosen = entry
            break
    if chosen is None:
        chosen = evidence['candidates'][0]
    evidence['publisher'] = {key: chosen.get(key) for key in
                             ('pid', 'node_name', 'cmdline', 'config_path',
                              'config_sha256', 'msg_source', 'pcap_file',
                              'pcap_repeat', 'open_pcap_files')}
    evidence['driver_config'] = {'path': chosen.get('config_path'),
                                 'sha256': chosen.get('config_sha256'),
                                 'msg_source': chosen.get('msg_source'),
                                 'pcap_file': chosen.get('pcap_file'),
                                 'pcap_repeat': chosen.get('pcap_repeat')}

    node_name = chosen.get('node_name')
    if node_name:
        info = _rosnode_info(node_name.lstrip('/'))
        evidence['rosnode'] = info
        if info.get('available'):
            cloud_topics = [topic for topic in info.get('publishers') or []
                            if topic.endswith('points')]
            evidence['rosnode']['cloud_publishers'] = cloud_topics

    msg_source = chosen.get('msg_source')
    open_pcap = chosen.get('open_pcap_files') or []
    evidence['mode'] = decide_mode(msg_source, open_pcap)
    if open_pcap and msg_source == 1:
        evidence['reason'] = 'inconsistent_open_pcap_with_msg_source_1'
    elif open_pcap and msg_source != 1:
        evidence['reason'] = 'driver_process_has_open_pcap'
    elif msg_source == 2:
        evidence['reason'] = 'effective_config_msg_source_is_2'
    elif msg_source == 1:
        evidence['reason'] = 'effective_config_msg_source_is_1_and_no_pcap_open'
    else:
        evidence['reason'] = 'unrecognised_msg_source'
    evidence['loop_capable'] = bool(chosen.get('pcap_repeat'))
    evidence['caveat'] = ('msg_source=1 with no open pcap is consistent with the '
                          'live sensor but does not prove it; stream continuity is '
                          'reported separately by the node')
    return evidence


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json-out', required=True)
    parser.add_argument('--mode-file', default=None)
    parser.add_argument('--publisher', default='inno_lidar')
    args = parser.parse_args(argv)
    evidence = inspect(args.publisher)
    with open(args.json_out, 'w', encoding='utf-8') as handle:
        json.dump(evidence, handle, sort_keys=True, indent=1)
        handle.write('\n')
    if args.mode_file:
        tmp = args.mode_file + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as handle:
            handle.write(evidence['mode'] + '\n')
        os.replace(tmp, args.mode_file)
    print(json.dumps({'mode': evidence['mode'], 'reason': evidence['reason'],
                      'publisher': evidence.get('publisher', {}).get('node_name'),
                      'config': evidence.get('driver_config', {}).get('path'),
                      'evidence': os.path.abspath(args.json_out)}))
    return {'live_lidar': 0, 'pcap': 4}.get(evidence['mode'], 3)


if __name__ == '__main__':
    sys.exit(main())