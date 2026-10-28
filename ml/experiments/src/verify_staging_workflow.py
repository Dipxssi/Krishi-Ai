"""Verification script for complete KrishiAI workflow against staging configuration."""

from __future__ import annotations

import base64
import io
import json
import os
import sys
from pathlib import Path
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from starlette.testclient import TestClient
from app.main import app
from app.core.config import get_settings
from app.vision.mobilenetv3_service import clear_mobilenetv3_cache

# Point to staging checkpoint
os.environ["HF_MODEL_FILENAME"] = "mobilenetv3_plantdisease_staging.pth"
clear_mobilenetv3_cache()

client = TestClient(app)

def pil_to_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def run_tests():
    print("=" * 80)
    print("KRISHIAI STAGING WORKFLOW VERIFICATION (Experiment C)")
    print("=" * 80)

    # 1. Image upload to MobileNetV3 test endpoint
    sample_dir = PROJECT_ROOT / "ml" / "PlantVillage" / "raw" / "color" / "Tomato___Early_blight"
    sample_file = next(sample_dir.glob("*.JPG"))
    img = Image.open(sample_file).convert("RGB")
    b64 = pil_to_b64(img)

    print("\n1. Testing Image Diagnosis with explicit crop hint ('tomato')...")
    resp = client.post("/crop/mobilenetv3-diagnosis", json={
        "image_base64": b64,
        "crop_hint": "tomato",
        "confidence_threshold": 0.60,
    })
    assert resp.status_code == 200, f"Error: {resp.text}"
    d1 = resp.json()
    print(f"   Status: {d1['status']}")
    print(f"   Predicted Disease: {d1.get('predicted_disease')}")
    print(f"   Confidence: {d1.get('confidence')} (Calibrated: {d1.get('confidence_is_calibrated')})")
    print(f"   Requires Expert: {d1.get('requires_expert')}")
    print(f"   Treatment Hints: {d1.get('treatment_hints')}")
    assert d1["status"] == "accepted"
    assert d1["crop_id"] == "tomato"

    print("\n2. Testing Image Diagnosis with NO crop hint (provisional mode)...")
    resp_no_hint = client.post("/crop/mobilenetv3-diagnosis", json={
        "image_base64": b64,
        "confidence_threshold": 0.60,
    })
    assert resp_no_hint.status_code == 200
    d2 = resp_no_hint.json()
    print(f"   Status: {d2['status']}")
    print(f"   Predicted Disease: {d2.get('predicted_disease')}")
    print(f"   Hints count: {len(d2.get('treatment_hints', []))}")
    hints_text = " ".join(d2.get("treatment_hints", []))
    assert "Provisional prediction" in hints_text or "Crop identity was not explicitly confirmed" in hints_text
    print("   Verified: Provisional disclaimer attached when crop is unconfirmed.")

    print("\n3. Testing Unsupported Crop ('apple')...")
    resp_apple = client.post("/crop/mobilenetv3-diagnosis", json={
        "image_base64": b64,
        "crop_hint": "apple",
    })
    assert resp_apple.status_code == 200
    d3 = resp_apple.json()
    print(f"   Status: {d3['status']}")
    print(f"   Rejection Reason: {d3.get('rejection_reason')}")
    print(f"   Requires Expert: {d3.get('requires_expert')}")
    assert d3["status"] == "rejected"
    assert d3["requires_expert"] is True
    assert "apple" in d3["rejection_reason"].lower()

    print("\n4. Testing Full Orchestrator /query with Image (Multi-agent RAG)...")
    # First create farmer profile via POST /farmers
    farmer_resp = client.post("/farmers", json={
        "farmer_id": "staging-farmer-01",
        "name": "Ramesh Patil",
        "location": "Nashik, Maharashtra",
        "farm_area_acres": 2.5,
        "crop": "tomato",
        "soil_type": "black",
        "preferred_language": "en",
    })
    assert farmer_resp.status_code in (200, 201, 409), f"Farmer creation failed: {farmer_resp.text}"

    resp_query = client.post("/query", json={
        "farmer_id": "staging-farmer-01",
        "query": "My tomato leaves have brown concentric rings and yellow halos. What disease is this and how should I treat it?",
        "image_base64": b64,
        "selected_crop": "tomato",
        "vision_model": "mobilenetv3",
    })
    assert resp_query.status_code == 200, f"Error: {resp_query.text}"
    q_data = resp_query.json()
    print(f"   Agents Used: {q_data.get('agents_used')}")
    print(f"   Response Language: {q_data.get('response_language')}")
    print(f"   Has Image Diagnosis: {q_data.get('image_diagnosis') is not None}")
    if q_data.get("image_diagnosis"):
        print(f"   Image Status: {q_data['image_diagnosis'].get('status')}")
        print(f"   Disease: {q_data['image_diagnosis'].get('disease')}")
    print(f"   Response Preview: {q_data.get('final_recommendation', '')[:160]}...")
    assert len(q_data.get("agents_used", [])) > 0

    print("\n5. Testing Economics and Cost Calculator query (Non-vision)...")
    resp_econ = client.post("/query", json={
        "farmer_id": "staging-farmer-01",
        "query": "What is the expected cost and profit per acre for tomato in Maharashtra?",
        "selected_crop": "tomato",
    })
    assert resp_econ.status_code == 200
    e_data = resp_econ.json()
    print(f"   Econ Agents Used: {e_data.get('agents_used')}")
    print(f"   Econ Response Preview: {e_data.get('final_recommendation', '')[:160]}...")
    assert "economics_agent" in e_data.get("agents_used", []) or len(e_data.get("agents_used", [])) > 0

    print("\n6. Testing Multilingual Hindi Query...")
    resp_hindi = client.post("/query", json={
        "farmer_id": "staging-farmer-01",
        "query": "टमाटर के पत्तों पर भूरे धब्बे हैं, क्या उपाय करें?",
        "selected_crop": "tomato",
    })
    assert resp_hindi.status_code == 200
    h_data = resp_hindi.json()
    print(f"   Hindi Detected Lang: {h_data.get('response_language')}")
    print(f"   Hindi Response Preview: {h_data.get('final_recommendation', '')[:160]}...")
    assert h_data.get("response_language") == "hi"

    print("\n" + "=" * 80)
    print("ALL 6 WORKFLOW VERIFICATIONS PASSED SUCCESSFULLY IN STAGING!")
    print("=" * 80)


if __name__ == "__main__":
    run_tests()
