import json

import pytest


@pytest.fixture
def sample_municipality():
    return {
        "bfs": "EE-0784",
        "name": "Tallinn",
        "canton": "Harju maakond",
        "country": "EE",
        "domain": "tallinn.ee",
        "mx": ["mx1.tallinn.ee", "mx2.tallinn.ee"],
        "spf": "v=spf1 ip4:85.253.224.0/20 -all",
        "provider": "independent",
    }


@pytest.fixture
def sovereign_municipality():
    return {
        "bfs": "LV-0001",
        "name": "Rīga",
        "canton": "Rīgas plānošanas reģions",
        "country": "LV",
        "domain": "riga.lv",
        "mx": ["mx.riga.lv"],
        "spf": "v=spf1 include:spf.protection.outlook.com -all",
        "provider": "microsoft",
    }


@pytest.fixture
def unknown_municipality():
    return {
        "bfs": "LT-99",
        "name": "Testinis",
        "canton": "Testland",
        "country": "LT",
        "domain": "",
        "mx": [],
        "spf": "",
        "provider": "unknown",
    }


@pytest.fixture
def sample_data_json(tmp_path):
    data = {
        "generated": "2025-01-01T00:00:00Z",
        "total": 3,
        "counts": {"microsoft": 1, "independent": 1, "unknown": 1},
        "municipalities": {
            "EE-0784": {
                "bfs": "EE-0784",
                "name": "Tallinn",
                "canton": "Harju maakond",
                "country": "EE",
                "domain": "tallinn.ee",
                "mx": ["mx1.tallinn.ee", "mx2.tallinn.ee"],
                "spf": "v=spf1 ip4:85.253.224.0/20 -all",
                "provider": "independent",
            },
            "LV-0001": {
                "bfs": "LV-0001",
                "name": "Rīga",
                "canton": "Rīgas plānošanas reģions",
                "country": "LV",
                "domain": "riga.lv",
                "mx": ["mx.riga.lv"],
                "spf": "v=spf1 include:spf.protection.outlook.com -all",
                "provider": "microsoft",
            },
            "LT-99": {
                "bfs": "LT-99",
                "name": "Testinis",
                "canton": "Testland",
                "country": "LT",
                "domain": "",
                "mx": [],
                "spf": "",
                "provider": "unknown",
            },
        },
    }
    path = tmp_path / "data.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path
