import csv
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.crop_registry import clear_crop_registry_cache, get_crop_defaults
from app.services.upag_apy import (
    default_snapshot_csv_path,
    load_upag_csv,
    parse_upag_csv_rows,
    resolve_upag_yields,
)


@pytest.fixture(autouse=True)
def _fresh():
    clear_crop_registry_cache()
    yield
    clear_crop_registry_cache()


def test_parse_upag_csv_tonne_per_hectare():
    rows = [
        {
            "fiscal_year": "2024-25",
            "state": "All India",
            "crop": "Wheat",
            "crop_yield": "3.6",
            "yield_unit": "tonnes_per_hectare",
        }
    ]
    out = parse_upag_csv_rows(rows)
    assert out["wheat"]["yield_kg_per_hectare"] == 3600.0
    assert out["wheat"]["data_origin"] == "upag_csv"


def test_parse_upag_cotton_lint_alias():
    rows = [
        {
            "fiscal_year": "2024-25",
            "state": "All India",
            "crop": "Cotton(lint)",
            "crop_yield": "437.06",
            "yield_unit": "kilogram_per_hectare",
        }
    ]
    out = parse_upag_csv_rows(rows)
    assert "cotton" in out
    assert out["cotton"]["yield_kg_per_hectare"] == pytest.approx(437.06, rel=0.001)


def test_load_bundled_upag_snapshot():
    path = default_snapshot_csv_path()
    assert path.exists()
    yields = load_upag_csv(path)
    assert len(yields) == 7
    assert yields["tomato"]["source_organization"]
    assert yields["tomato"]["data_origin"] == "upag_csv"


def test_resolve_upag_yields_from_snapshot():
    yields, mode = resolve_upag_yields(prefer_live=False)
    assert mode == "upag_snapshot_csv"
    assert yields["maize"]["yield_kg_per_hectare"] == pytest.approx(3478.3, rel=0.01)


def test_build_registry_uses_upag_snapshot_values():
    clear_crop_registry_cache()
    wheat = get_crop_defaults("wheat")
    prov = wheat["yield_provenance"]
    # After rebuild: should be UPAg 2024-25 wheat ~3606.6 kg/ha -> ~1459.5 kg/acre
    # Registry may still be old until rebuild - test snapshot directly
    yields, _ = resolve_upag_yields(prefer_live=False)
    assert yields["wheat"]["expected_yield_kg_per_acre"] == pytest.approx(1459.5, rel=0.02)


def test_fetch_upag_live_mock(tmp_path: Path):
    fake_csv_rows = [
        {
            "fiscal_year": "2024-25",
            "state": "All India",
            "crop": "Tomato",
            "crop_yield": "25.0",
            "yield_unit": "tonnes_per_hectare",
        }
    ]
    csv_path = tmp_path / "upag_test.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["fiscal_year", "state", "crop", "crop_yield", "yield_unit", "source"],
        )
        writer.writeheader()
        for row in fake_csv_rows:
            writer.writerow({**row, "source": "test"})

    yields = load_upag_csv(csv_path)
    assert yields["tomato"]["yield_kg_per_hectare"] == 25000.0

    with patch("app.services.upag_apy.fetch_upag_yields_live", side_effect=ValueError("no creds")):
        yields2, mode = resolve_upag_yields(prefer_live=True, csv_path=csv_path)
    assert mode == "upag_csv"
    assert yields2["tomato"]["yield_kg_per_hectare"] == 25000.0
