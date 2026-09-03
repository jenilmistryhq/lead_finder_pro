import csv
import json

import pytest

from lead_finder.exporters import export, export_csv, export_json, export_xlsx
from lead_finder.scoring import Lead

SAMPLE = [Lead(name="A", score=10), Lead(name="B", score=5)]


def test_export_csv(tmp_path):
    path = tmp_path / "out.csv"
    export_csv(SAMPLE, str(path))
    rows = list(csv.DictReader(path.open()))
    assert len(rows) == 2
    assert rows[0]["name"] == "A"
    assert set(rows[0].keys()) == set(Lead.FIELD_ORDER)


def test_export_json(tmp_path):
    path = tmp_path / "out.json"
    export_json(SAMPLE, str(path))
    data = json.loads(path.read_text())
    assert len(data) == 2
    assert data[1]["name"] == "B"


def test_export_xlsx(tmp_path):
    path = tmp_path / "out.xlsx"
    export_xlsx(SAMPLE, str(path))
    assert path.exists()
    assert path.stat().st_size > 0


def test_export_empty_list_raises(tmp_path):
    with pytest.raises(ValueError):
        export_csv([], str(tmp_path / "empty.csv"))


def test_export_dispatch_by_format(tmp_path):
    path = tmp_path / "out.csv"
    export(SAMPLE, "csv", str(path))
    assert path.exists()


def test_export_unknown_format_raises(tmp_path):
    with pytest.raises(ValueError):
        export(SAMPLE, "pdf", str(tmp_path / "out.pdf"))
