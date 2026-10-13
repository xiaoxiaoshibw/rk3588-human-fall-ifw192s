#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""pull_gt_from_board.py — 把 3588 板上的 GT 标注产物拉回 PC 落 gt_store。

动机（用户 2026-10-10 "保存在3588可以下载到本机"）：
板端是协同真源，PC 拿副本用来训练/评估/留档。
通过刚新增的 /api/gt/exports（发现清单）+ /api/gt/exports/file?sid&name（下载），
原 sha256 逐文件校验后写入 PC 的 gt_store（/git_ignored、BOARD 上同步 PATH 一致），
不动已经存在的版本文件（GT_V*.json 是不可变的；PC 与板不一致要 report 而不是覆盖）。

用法： python pc_apps/human_replay/pull_gt_from_board.py [--board http://192.168.31.58:8088]
"""
import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import config as C  # noqa: E402

DEFAULT_BOARD = "http://192.168.31.58:8088"


def _get(url, expect_json=True, timeout=15):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8")) if expect_json else raw


def pull(board=DEFAULT_BOARD, dest_store=None, log=None):
    log = log or (lambda m: print(m, flush=True))
    dest_store = dest_store or os.path.join(_HERE, "gt_store")
    os.makedirs(dest_store, exist_ok=True)

    log("从 %s 拿可下载清单…" % board)
    sessions_listing = _get(board + "/api/gt/export")
    sids = sessions_listing.get("sessions") or []
    log("板上 %d 个会话有 GT 产物" % len(sids))

    pulled, skipped, conflict = [], [], []
    # 全局级
    for sess_bucket, prefix in [(None, ""), *[(s, s + "/") for s in sids]]:
        url = board + "/api/gt/export" + ("?sid=" + sess_bucket if sess_bucket else "")
        try:
            listing = _get(url)
        except urllib.error.URLError as exc:
            log("  [%s] 清单拉取失败: %s" % (sess_bucket or "global", exc))
            continue
        files = listing.get("files") or []
        # history.jsonl 是服务端审计 artifact（每写一行追加），不属于"可下载产物"；
        # 页面 / export .file 白名单本来就拒绝它，pull 把它从列举里过滤掉避免每次 400.
        files = [f for f in files if f != "history.jsonl"]
        for name in files:
            dl_url = board + "/api/gt/exports/file?name=" + name
            if sess_bucket:
                dl_url += "&sid=" + sess_bucket
            try:
                raw = _get(dl_url, expect_json=False)
            except urllib.error.URLError as exc:
                log("  [%s/%s] 下载失败: %s" % (sess_bucket or "global", name, exc))
                continue
            sha = hashlib.sha256(raw).hexdigest()
            dest_dir = os.path.join(dest_store, sess_bucket) if sess_bucket else dest_store
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = os.path.join(dest_dir, name)
            rel = prefix + name
            if os.path.isfile(dest_path):
                with open(dest_path, "rb") as fh:
                    existing = fh.read()
                if hashlib.sha256(existing).hexdigest() == sha:
                    skipped.append((rel, "已是最新"))
                    continue
                if name.startswith("GT_V"):
                    conflict.append((rel, "GT_V* 已存在且 sha 不一致 — 不可变, 不覆盖"))
                    continue
            with open(dest_path, "wb") as fh:
                fh.write(raw)
            pulled.append((rel, sha[:12]))

    log("落 %d 个新文件, 跳过 %d 个, 冲突 %d 个" % (len(pulled), len(skipped), len(conflict)))
    for rel, sha in pulled:
        log("  + %s (%s)" % (rel, sha))
    for rel, why in conflict:
        log("  ! CONFLICT %s: %s" % (rel, why))
    return {"pulled": pulled, "skipped": skipped, "conflicts": conflict}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", default=DEFAULT_BOARD)
    ap.add_argument("--store", default=None,
                    help="覆盖落水点；默认 ./gt_store（human_replay 约定）")
    args = ap.parse_args()
    res = pull(board=args.board, dest_store=args.store)
    sys.exit(0 if not res["conflicts"] else 2)


if __name__ == "__main__":
    main()
