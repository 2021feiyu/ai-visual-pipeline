#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「分镜清单 + 图片」打成一个自包含的 HTML 页面（图片 base64 内嵌，单文件可离线打开）。

用法：
    python story_to_html.py --manifest story.json --out story.html

story.json：
    {
      "title": "标题",
      "subtitle": "副标题（可省）",
      "author": "署名（可省）",
      "scenes": [
        {"image": "01.png", "text": "第一段的文字"},
        {"image": "02.png", "text": "第二段的文字"}
      ]
    }

为什么内嵌：带一堆相对路径的 HTML 发给别人，图经常丢。base64 内嵌后是**一个文件**，
双击能看、邮件能发、微信能传。
"""
import argparse
import base64
import json
import mimetypes
import os


def data_uri(path):
    mime, _ = mimetypes.guess_type(path)
    mime = mime or "image/png"
    with open(path, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"


TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{
    --ink: #1f1d1a;
    --muted: #6b6560;
    --paper: #f7f4ee;
    --rule: #ddd6ca;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--paper); color: var(--ink);
    font-family: "Songti SC", "Noto Serif SC", Georgia, serif;
    line-height: 1.9; font-size: 18px;
  }}
  main {{ max-width: 720px; margin: 0 auto; padding: 64px 24px 96px; }}
  header {{ text-align: center; margin-bottom: 56px; }}
  h1 {{ font-size: 30px; font-weight: 600; letter-spacing: .02em; margin: 0 0 12px; }}
  .sub {{ color: var(--muted); font-size: 15px; }}
  figure {{ margin: 0 0 56px; }}
  figure img {{ width: 100%; height: auto; display: block; border-radius: 2px; }}
  figcaption {{ margin-top: 18px; font-size: 17px; }}
  footer {{
    margin-top: 72px; padding-top: 20px; border-top: 1px solid var(--rule);
    color: var(--muted); font-size: 13px; text-align: center;
  }}
</style>
</head>
<body>
<main>
  <header>
    <h1>{title}</h1>
    {subtitle}
  </header>
  {figures}
  <footer>{author}</footer>
</main>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description="分镜清单 → 单文件 HTML")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--base-dir", default=None, help="图片相对路径的基准目录，默认取 manifest 所在目录")
    a = ap.parse_args()

    with open(a.manifest, encoding="utf-8") as fh:
        m = json.load(fh)
    base = a.base_dir or os.path.dirname(os.path.abspath(a.manifest))

    figures = []
    for i, sc in enumerate(m.get("scenes", []), 1):
        img = os.path.join(base, sc["image"])
        if not os.path.exists(img):
            raise SystemExit(f"找不到图片：{img}")
        text = (sc.get("text") or "").strip()
        cap = f"<figcaption>{text}</figcaption>" if text else ""
        figures.append(f'  <figure><img src="{data_uri(img)}" alt="scene {i}">{cap}</figure>')

    html = TEMPLATE.format(
        title=m.get("title", ""),
        subtitle=f'<p class="sub">{m["subtitle"]}</p>' if m.get("subtitle") else "",
        figures="\n  ".join(figures),
        author=m.get("author", ""),
    )
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(html)

    size = os.path.getsize(a.out) / 1024 / 1024
    print(f"写入 {a.out}（{size:.1f} MB，{len(figures)} 幕）")


if __name__ == "__main__":
    main()
