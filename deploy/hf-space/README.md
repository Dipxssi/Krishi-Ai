---
title: KrishiAI MobileNetV3 Vision
emoji: 🌿
colorFrom: green
colorTo: yellow
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: false
license: mit
short_description: Free CPU MobileNetV3 leaf disease inference for KrishiAI
---

# KrishiAI MobileNetV3 Vision (free Gradio Space)

Runs the KrishiAI plant-disease MobileNetV3 checkpoint on **free CPU**.
The slim Render API calls Gradio endpoint `predict` so Vercel demos work without paid Docker / 2GB hosts.

## Wake before demos

Free Spaces sleep when idle. Open this Space URL until the UI loads, then use the Vercel app.

## Create Space settings

- **SDK:** Gradio (not Docker — Docker may be marked Paid)
- **Hardware:** **ZeroGPU (Free)** — CPU basic often requires PRO now
- **Template:** Blank
- **Name:** `krishiai-vision`
- **Description:** `Free MobileNetV3 leaf disease inference for KrishiAI (tomato, potato, maize).`

## Files to upload

- `app.py`
- `inference.py`
- `requirements.txt`
- this `README.md`

## Wire to Render

Set on Render `krishiai-api`:

- `VISION_MODEL=mobilenetv3`
- `VISION_INFERENCE_URL=https://huggingface.co/spaces/Dipssi/krishiai-vision`  
  (or `Dipssi/krishiai-vision`)

See repo `docs/DEPLOY.md`.
