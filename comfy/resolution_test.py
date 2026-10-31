#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分辨率甜点测试：同一提示词，不同分辨率各跑一张，看耗时与显存是否吃得消。

用法：
    python resolution_test.py --workflow workflows/qwen_image.example.json \
        --prompt "a quiet street after rain, cinematic" \
        --sizes 640x640,768x1024,1024x1024,1024x1536,1536x1024

输出一张表：分辨率 / 耗时 / 输出文件。图要自己看——**耗时能接受、画面不变形**的那个才是甜点。
"""
import argparse
import json
import os
import time

from comfy_batch import DEFAULT_URL, http_json, render, submit, wait


def parse_sizes(s):
    out = []
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        w, h = part.lower().split("x")
        out.append((int(w), int(h)))
    return out


def main():
    ap = argparse.ArgumentParser(description="分辨率甜点测试")
    ap.add_argument("--workflow", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--sizes", default="640x640,768x768,1024x1024,1024x1536")
    ap.add_argument("--seed", type=int, default=12345, help="固定种子，保证只变分辨率")
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--out", default="./resolution-report.json")
    a = ap.parse_args()

    with open(a.workflow, encoding="utf-8") as fh:
        template = json.load(fh)

    rows = []
    for w, h in parse_sizes(a.sizes):
        wf = render(template, a.prompt, w, h, a.seed, "res", 1)
        t0 = time.time()
        try:
            pid = submit(a.url, wf)
            images, cost = wait(a.url, pid, timeout=3600)
        except Exception as e:  # noqa: BLE001
            rows.append({"size": f"{w}x{h}", "seconds": None, "images": [], "error": str(e)})
            print(f"{w}x{h}  失败：{e}")
            continue
        rows.append({"size": f"{w}x{h}", "seconds": round(cost, 1), "images": images})
        print(f"{w}x{h}  {cost:.1f}s  {images}  (wall {time.time() - t0:.0f}s)")

    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=2)

    print("\n分辨率      耗时(s)")
    print("-" * 26)
    for r in rows:
        print(f"{r['size']:<12}{r['seconds'] if r['seconds'] is not None else '失败'}")
    print(f"\n明细已写入 {a.out}")


if __name__ == "__main__":
    main()
