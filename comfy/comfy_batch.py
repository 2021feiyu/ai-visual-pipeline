#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ComfyUI 批量生图：一份工作流模板 + 一个提示词列表，跑完为止。

用法：
    python comfy_batch.py --workflow workflows/qwen_image.example.json \
                          --prompts prompts.txt --out ./out --width 1024 --height 1024

    # 只打印将要提交的工作流，不真的提交
    python comfy_batch.py ... --dry-run

设计要点：
- 工作流用 JSON 模板，占位符 {{PROMPT}} {{WIDTH}} {{HEIGHT}} {{SEED}} {{PREFIX}} 会在提交前替换
- 每张图完成后把结果追加到 <out>/manifest.jsonl，中断后重跑会跳过已完成的提示词
- 只用一个并发（ComfyUI 默认队列串行）；要并发就多开两个进程，别改这里

环境变量：
    COMFY_URL   默认 http://127.0.0.1:8188
"""
import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request

DEFAULT_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")


def http_json(url, payload=None, timeout=30):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"},
        method="POST" if data else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_prompts(path):
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                out.append(line)
    return out


def render(template, prompt, width, height, seed, prefix, index):
    """把模板里的占位符替换掉；返回 dict。以 _ 开头的键视为注释，提交前剔除。"""
    body = {k: v for k, v in template.items() if not str(k).startswith("_")}
    raw = json.dumps(body, ensure_ascii=False)
    raw = (raw.replace("{{PROMPT}}", json.dumps(prompt, ensure_ascii=False)[1:-1])
              .replace("{{WIDTH}}", str(width))
              .replace("{{HEIGHT}}", str(height))
              .replace("{{SEED}}", str(seed))
              .replace("{{PREFIX}}", f"{prefix}_{index:03d}"))
    return json.loads(raw)


def submit(base, workflow, client_id="comfy-batch"):
    r = http_json(base + "/prompt", {"prompt": workflow, "client_id": client_id})
    if "prompt_id" not in r:
        raise RuntimeError(f"提交失败：{r}")
    return r["prompt_id"]


def wait(base, pid, interval=4, timeout=1800):
    t0 = time.time()
    while True:
        if time.time() - t0 > timeout:
            raise TimeoutError(f"{pid} 超过 {timeout}s 未完成")
        time.sleep(interval)
        try:
            h = http_json(base + "/history/" + pid, timeout=15)
        except (urllib.error.URLError, TimeoutError):
            continue
        if pid in h:
            images = []
            for node in h[pid].get("outputs", {}).values():
                for im in node.get("images", []):
                    images.append(im.get("filename"))
            return images, time.time() - t0


def done_set(manifest):
    done = set()
    if os.path.exists(manifest):
        with open(manifest, encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("prompt"):
                    done.add(rec["prompt"])
    return done


def main():
    ap = argparse.ArgumentParser(description="ComfyUI 批量生图")
    ap.add_argument("--workflow", required=True, help="工作流模板 JSON（含占位符）")
    ap.add_argument("--prompts", required=True, help="提示词文件，一行一条，# 开头为注释")
    ap.add_argument("--out", default="./out", help="输出目录（存 manifest）")
    ap.add_argument("--width", type=int, default=1024)
    ap.add_argument("--height", type=int, default=1024)
    ap.add_argument("--seed", type=int, default=-1, help="-1 表示每条随机")
    ap.add_argument("--prefix", default="batch")
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    with open(a.workflow, encoding="utf-8") as fh:
        template = json.load(fh)
    prompts = load_prompts(a.prompts)
    if not prompts:
        sys.exit("提示词文件是空的")

    os.makedirs(a.out, exist_ok=True)
    manifest = os.path.join(a.out, "manifest.jsonl")
    done = done_set(manifest)
    todo = [p for p in prompts if p not in done]
    print(f"共 {len(prompts)} 条，已完成 {len(done)}，本次待跑 {len(todo)}")

    for i, prompt in enumerate(todo, 1):
        seed = a.seed if a.seed >= 0 else random.randint(1, 2**31 - 1)
        wf = render(template, prompt, a.width, a.height, seed, a.prefix, len(done) + i)
        if a.dry_run:
            print(json.dumps(wf, ensure_ascii=False)[:400])
            continue

        for attempt in range(1, a.retries + 2):
            try:
                pid = submit(a.url, wf)
                images, cost = wait(a.url, pid)
                rec = {
                    "prompt": prompt, "seed": seed, "images": images,
                    "seconds": round(cost, 1), "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
                with open(manifest, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                print(f"[{i}/{len(todo)}] ok {cost:.1f}s  {images}")
                break
            except Exception as e:  # noqa: BLE001
                print(f"[{i}/{len(todo)}] 第 {attempt} 次失败：{e}")
                if attempt > a.retries:
                    print("  放弃这一条，继续下一条")
                time.sleep(3)

    print("完成。清单见", manifest)


if __name__ == "__main__":
    main()
