#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ComfyUI 看门狗：健康检查 + 可选自动重启。

用途：跑一整夜批量生图时，ComfyUI 崩了没人管。这个脚本每隔 N 秒探一次
/system_stats，连续失败 M 次就按你给的命令重启，并记录到日志。

用法：
    # 只观察，不重启
    python comfy_watchdog.py --interval 30 --fails 3

    # 连续 3 次探活失败后执行重启命令
    python comfy_watchdog.py --restart-cmd "python main.py --listen 127.0.0.1 --port 8188"

注意：
- 重启命令由你自己给，脚本不猜你的启动方式
- 重启后会等 warmup 秒再恢复探活（模型加载慢，急着探会误判）
"""
import argparse
import os
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request


def probe(base, timeout=8):
    try:
        with urllib.request.urlopen(base + "/system_stats", timeout=timeout) as resp:
            return resp.status == 200, None
    except urllib.error.HTTPError as e:
        return e.code == 200, f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def main():
    ap = argparse.ArgumentParser(description="ComfyUI 健康检查 / 自动重启")
    ap.add_argument("--url", default=os.environ.get("COMFY_URL", "http://127.0.0.1:8188"))
    ap.add_argument("--interval", type=int, default=30, help="探活间隔秒")
    ap.add_argument("--fails", type=int, default=3, help="连续失败几次判定为挂")
    ap.add_argument("--restart-cmd", default=None, help="重启命令（留空则只报警不重启）")
    ap.add_argument("--warmup", type=int, default=60, help="重启后等待秒数")
    ap.add_argument("--log", default="watchdog.log")
    ap.add_argument("--once", action="store_true", help="只探一次就退出（给外部调度用）")
    a = ap.parse_args()

    def log(msg):
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}"
        print(line, flush=True)
        with open(a.log, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    fails = 0
    restarts = 0
    while True:
        ok, err = probe(a.url)
        if ok:
            if fails:
                log(f"恢复（此前连续失败 {fails} 次）")
            fails = 0
        else:
            fails += 1
            log(f"探活失败 {fails}/{a.fails}：{err}")

            if fails >= a.fails:
                if not a.restart_cmd:
                    log("已达阈值，但未配置 --restart-cmd，跳过重启")
                    fails = 0
                else:
                    restarts += 1
                    log(f"判定为挂，执行重启（第 {restarts} 次）：{a.restart_cmd}")
                    try:
                        subprocess.Popen(shlex.split(a.restart_cmd), shell=False)
                    except Exception as e:  # noqa: BLE001
                        log(f"重启命令启动失败：{e}")
                    time.sleep(a.warmup)
                fails = 0

        if a.once:
            sys.exit(0 if ok else 1)
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
