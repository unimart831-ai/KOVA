"""Unit tests for WhatsApp services helpers (no API calls)."""

from apps.whatsapp.services import normalize_wa_id, variables_to_components


def test_normalize_wa_id_kenya_local():
    assert normalize_wa_id("0712345678") == "254712345678"


def test_normalize_wa_id_strips_plus():
    assert normalize_wa_id("+254712345678") == "254712345678"


def test_variables_to_components_list():
    comps = variables_to_components(["Alice", "KES 500"])
    assert comps == [{
        "type": "body",
        "parameters": [
            {"type": "text", "text": "Alice"},
            {"type": "text", "text": "KES 500"},
        ],
    }]


def test_variables_to_components_numeric_dict():
    comps = variables_to_components({2: "second", 1: "first"})
    assert comps[0]["parameters"][0]["text"] == "first"
    assert comps[0]["parameters"][1]["text"] == "second"


def test_variables_to_components_named_dict():
    comps = variables_to_components({"date": "Friday", "service": "Haircut"})
    texts = [p["text"] for p in comps[0]["parameters"]]
    assert texts == ["Friday", "Haircut"]
