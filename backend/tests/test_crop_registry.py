import pytest

from app.services.crop_registry import (
    clear_crop_registry_cache,
    get_crop_defaults,
    get_crop_profile,
    list_supported_crops,
    normalize_crop_name,
)


@pytest.fixture(autouse=True)
def _fresh_registry():
    clear_crop_registry_cache()
    yield
    clear_crop_registry_cache()


def test_list_supported_crops_has_seven():
    crops = list_supported_crops()
    assert len(crops) == 7
    assert "tomato" in crops
    assert "potato" in crops
    assert "cotton" in crops


def test_yields_differ_by_crop():
    tomato = get_crop_defaults("tomato")
    potato = get_crop_defaults("potato")
    maize = get_crop_defaults("maize")
    # Values from UPAg snapshot after build_crop_registry.py
    assert tomato["expected_yield_kg_per_acre"] == pytest.approx(9712.4, rel=0.02)
    assert potato["expected_yield_kg_per_acre"] == pytest.approx(9914.8, rel=0.02)
    assert maize["expected_yield_kg_per_acre"] == pytest.approx(1407.6, rel=0.02)
    assert tomato["expected_yield_kg_per_acre"] != potato["expected_yield_kg_per_acre"]
    assert potato["expected_yield_kg_per_acre"] != maize["expected_yield_kg_per_acre"]
    assert tomato["yield_provenance"]["data_origin"] in (
        "upag_snapshot_csv",
        "upag_scraped_csv",
        "upag_live",
    )


def test_normalize_crop_aliases():
    assert normalize_crop_name("Tomatoes") == "tomato"
    assert normalize_crop_name("corn") == "maize"
    assert normalize_crop_name("paddy") == "rice"
    assert normalize_crop_name(None) is None


def test_get_crop_profile_includes_npk_and_diseases():
    profile = get_crop_profile("wheat")
    assert profile["crop_id"] == "wheat"
    assert "yellow_rust" in profile["common_diseases"]
    assert profile["npk_targets"]["n_kg_per_acre"] == 120
    assert profile["market_commodity_name"] == "Wheat"


def test_get_crop_defaults_costs_are_per_acre():
    defaults = get_crop_defaults("onion")
    costs = defaults["default_input_costs_per_acre"]
    assert costs["seed_cost"] > 0
    assert costs["labor_cost"] > costs["pesticide_cost"]


def test_unknown_crop_raises():
    with pytest.raises(KeyError, match="unsupported crop"):
        get_crop_profile("mango")
