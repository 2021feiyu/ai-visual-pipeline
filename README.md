# AI Visual Pipeline

**本地 ComfyUI 的批量生图套件 + 图文短篇的交付流水线。**

两部分：`comfy/` 解决"怎么稳定跑一夜"，`story/` 解决"怎么把图变成能发出去的东西"。

---

## 为什么自己写

ComfyUI 的批量脚本大多散在 issue 里，能跑通的多，能**跑一整夜不崩**的少。缺的通常是三样：

| 缺什么 | 后果 | 这里怎么补 |
|---|---|---|
| 断点续跑 | 跑到第 80 张崩了，得从头再来 | 每条完成即写 `manifest.jsonl`，重跑自动跳过 |
| 健康检查 | 服务挂了脚本还在傻等 | `comfy_watchdog.py` 探活 + 可选自动重启 |
| 甜点测试 | 分辨率开太大爆显存，开太小糊 | `resolution_test.py` 同种子跑多档，用耗时和画面说话 |

---

## 目录

```
comfy/
  comfy_batch.py          批量生图：模板 + 提示词列表 → 逐张提交、轮询、记录
  comfy_watchdog.py       探活 + 连续失败自动重启（重启命令由你给）
  resolution_test.py      同提示词多分辨率对照，输出耗时表
  workflows/
    qwen_image.example.json   示例工作流（ComfyUI API 格式）
story/
  story_to_html.py        分镜清单 + 图片 → 单文件 HTML（base64 内嵌）
  story-workflow.md       图文短篇的方法：四角色分离、风格锚、分镜、验收
```

---

## 快速开始

### 1. 准备一份 API 格式的工作流

在 ComfyUI 界面里搭好流程 → 菜单 **Save (API Format)** → 得到 JSON。

把要变的字段换成占位符：

| 占位符 | 含义 |
|---|---|
| `{{PROMPT}}` | 提示词 |
| `{{WIDTH}}` / `{{HEIGHT}}` | 尺寸 |
| `{{SEED}}` | 种子 |
| `{{PREFIX}}` | 输出文件名前缀 |

> 以 `_` 开头的键会被当作注释，提交前自动剔除。

### 2. 跑批

```bash
cd comfy
python comfy_batch.py --workflow workflows/qwen_image.example.json \
                      --prompts prompts.txt --out ./out \
                      --width 1024 --height 1024

# 先看一眼渲染出来的工作流对不对（不提交）
python comfy_batch.py ... --dry-run
```

`prompts.txt` 一行一条，`#` 开头是注释。跑完在 `out/manifest.jsonl` 里有每条的种子、耗时、输出文件名。

### 3. 挂个看门狗（可选）

```bash
python comfy_watchdog.py --interval 30 --fails 3 \
       --restart-cmd "python main.py --listen 127.0.0.1 --port 8188"
```

只探活不重启就省掉 `--restart-cmd`；`--once` 可以给外部调度器当健康检查用。

### 4. 测甜点分辨率

```bash
python resolution_test.py --workflow workflows/qwen_image.example.json \
       --prompt "a quiet street after rain" \
       --sizes 640x640,768x1024,1024x1024,1024x1536
```

固定种子，只变分辨率。**看两条：耗时能不能接受、画面有没有变形。**

### 5. 拼成交付页

```bash
python story/story_to_html.py --manifest story.json --out story.html
```

`story.json` 结构见脚本头部注释。输出是**单个 html**，图全部 base64 内嵌——发给别人不会丢图。

---

## 环境

- Python 3.9+，只用标准库（`urllib` / `json` / `base64`），**不需要装任何包**
- ComfyUI 跑在本机或局域网，把 `COMFY_URL` 指过去即可（默认 `http://127.0.0.1:8188`）

---

## 注意

- **并发保持 1**：ComfyUI 队列本身是串行的，多进程抢显存只会互相拖慢。要快就加卡，不要加线程。
- **模型名要对**：示例工作流里的 `unet_name` / `clip_name` 是示例，换成你本地 `models/` 下的真实文件名，否则提交报 400。
- **大图先测**：显存不够时 ComfyUI 会直接崩，不会优雅降级——先跑 `resolution_test.py`。
- **生成内容自负其责**：模型许可、素材版权、平台规则，都在你这边。

---

## License

MIT
