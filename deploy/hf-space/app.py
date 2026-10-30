"""Gradio Space (free ZeroGPU) — MobileNetV3 leaf disease inference for KrishiAI."""

from __future__ import annotations

import base64
import io
import json
import logging
from typing import Any

import gradio as gr
import spaces
from PIL import Image, ImageOps, UnidentifiedImageError

from inference import predict_image

logger = logging.getLogger("krishiai-vision")
logging.basicConfig(level=logging.INFO)


def _decode_image_base64(image_base64: str) -> Image.Image:
    raw = (image_base64 or "").split(",", 1)[-1].strip()
    if not raw:
        raise ValueError("image_base64 is empty")
    data = base64.b64decode(raw, validate=False)
    if len(data) < 100:
        raise ValueError("Image too small")
    if len(data) > 10 * 1024 * 1024:
        raise ValueError("Image must be 10 MB or smaller")
    try:
        # Honor phone EXIF orientation so hosted matches upright local previews.
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
        return img.convert("RGB")
    except UnidentifiedImageError as exc:
        raise ValueError("Unrecognized image format") from exc


@spaces.GPU(duration=60)
def predict_api(
    image_base64: str,
    crop_hint: str | None = None,
    confidence_threshold: float = 0.60,
) -> dict[str, Any]:
    """API used by KrishiAI Render backend (base64 in → diagnosis JSON out)."""
    try:
        img = _decode_image_base64(image_base64)
        hint = (crop_hint or "").strip() or None
        result = predict_image(
            img,
            crop_hint=hint,
            confidence_threshold=float(confidence_threshold or 0.60),
        )
        result["inference_source"] = "hf_space"
        return result
    except Exception as exc:
        logger.exception("predict_api failed: %s", exc)
        return {
            "status": "rejected",
            "rejection_reason": str(exc),
            "requires_expert": True,
            "treatment_hints": [
                "Vision Space error. Wake the Space and retry, or upload a clearer leaf photo."
            ],
            "model_version": "mobilenetv3_plantdisease_best",
            "inference_source": "hf_space",
            "top_3": [],
        }


def predict_ui_safe(
    image: Image.Image | None,
    crop_hint: str,
    confidence_threshold: float,
) -> str:
    """Browser demo — calls the same @spaces.GPU predict_api used by Render."""
    if image is None:
        return json.dumps({"status": "rejected", "rejection_reason": "No image uploaded"}, indent=2)
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return json.dumps(predict_api(b64, crop_hint or "", float(confidence_threshold or 0.60)), indent=2)


with gr.Blocks(title="KrishiAI MobileNetV3 Vision") as demo:
    gr.Markdown(
        "# KrishiAI MobileNetV3 Vision\n"
        "Free ZeroGPU leaf-disease classifier (tomato / potato / maize). "
        "Render calls the **predict** API; use the form below to smoke-test."
    )
    with gr.Tab("Demo"):
        img_in = gr.Image(type="pil", label="Leaf photo")
        crop_in = gr.Textbox(label="Crop hint (optional)", placeholder="tomato | potato | maize")
        thr_in = gr.Slider(0.0, 1.0, value=0.60, step=0.05, label="Confidence threshold")
        out = gr.Code(label="Diagnosis JSON", language="json")
        btn = gr.Button("Predict", variant="primary")
        btn.click(predict_ui_safe, inputs=[img_in, crop_in, thr_in], outputs=out)

    with gr.Tab("API (base64)"):
        b64_in = gr.Textbox(label="image_base64", lines=6)
        crop_api = gr.Textbox(label="crop_hint", placeholder="tomato")
        thr_api = gr.Number(value=0.60, label="confidence_threshold")
        json_out = gr.JSON(label="result")
        api_btn = gr.Button("Call predict_api", variant="primary")
        api_btn.click(
            predict_api,
            inputs=[b64_in, crop_api, thr_api],
            outputs=json_out,
            api_name="predict",
        )

demo.queue(default_concurrency_limit=1)

if __name__ == "__main__":
    demo.launch()
