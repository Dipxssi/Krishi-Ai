import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.crop_registry import clear_crop_registry_cache, get_crop_defaults
from app.services.crop_yield_data import (
    aggregate_live_yields,
    kg_per_hectare_to_kg_per_acre,
    load_apy_reference,
    reference_yield_by_crop,
    resolve_yields,
)


@pytest.fixture(autouse=True)
def _fresh_registry():
    clear_crop_registry_cache()
    yield
    clear_crop_registry_cache()


def test_kg_per_hectare_to_acre_conversion():
    # 2471 kg/ha ≈ 1000 kg/acre
    assert kg_per_hectare_to_kg_per_acre(2471.05381) == pytest.approx(1000.0, rel=0.01)


def test_reference_file_has_seven_crops():
    ref = load_apy_reference()
    assert len(ref["crops"]) == 7
    assert ref["year_label"] == "2022-23"
    assert "data.gov.in" in ref["reference_urls"][0]


def test_reference_yields_differ_by_crop():
    yields = reference_yield_by_crop()
    assert yields["tomato"]["expected_yield_kg_per_acre"] != yields["wheat"]["expected_yield_kg_per_acre"]
    assert yields["rice"]["data_origin"] == "government_reference_file"
    assert yields["tomato"]["source_organization"]


def test_aggregate_live_yields_from_mock_records():
    records = [
        {"crop": "Tomato", "yield_quintal_per_hectare": 250},
        {"crop": "Tomato", "yield_quintal_per_hectare": 270},
        {"crop": "Wheat", "yield_kg_per_hectare": 3400},
    ]
    out = aggregate_live_yields(records)
    assert out["tomato"]["yield_kg_per_hectare"] == 26000.0  # median of 25000, 27000
    assert out["wheat"]["yield_kg_per_hectare"] == 3400.0
    assert out["tomato"]["data_origin"] == "data.gov.in_live_api"


def test_resolve_yields_falls_back_to_reference_when_live_fails():
    with patch("app.services.crop_yield_data.fetch_apy_records_live", side_effect=ValueError("blocked")):
        yields, mode = resolve_yields(prefer_live=True, prefer_upag=False, api_key="test-key")
    assert mode == "reference"
    assert "potato" in yields


def test_built_registry_has_provenance():
    clear_crop_registry_cache()
    tomato = get_crop_defaults("tomato")
    prov = tomato.get("yield_provenance") or {}
    assert tomato["expected_yield_kg_per_acre"] > 0
    assert prov.get("data_origin") in (
        "upag_snapshot_csv",
        "upag_scraped_csv",
        "upag_live",
        "upag_live_api",
        "government_reference_file",
        "data.gov.in_live_api",
    )
    assert prov.get("yield_kg_per_hectare")
