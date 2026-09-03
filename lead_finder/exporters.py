"""Export a scored lead list to CSV, XLSX, or JSON."""

from __future__ import annotations

import csv
import json
import logging
from typing import List

from .scoring import Lead

logger = logging.getLogger(__name__)


def export_csv(leads: List[Lead], path: str) -> None:
    if not leads:
        raise ValueError("No leads to export")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(Lead.FIELD_ORDER))
        writer.writeheader()
        for lead in leads:
            writer.writerow(lead.as_row())
    logger.info("Wrote %d leads to %s", len(leads), path)


def export_json(leads: List[Lead], path: str) -> None:
    if not leads:
        raise ValueError("No leads to export")
    with open(path, "w", encoding="utf-8") as f:
        json.dump([lead.as_row() for lead in leads], f, indent=2)
    logger.info("Wrote %d leads to %s", len(leads), path)


def export_xlsx(leads: List[Lead], path: str) -> None:
    if not leads:
        raise ValueError("No leads to export")
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
    except ImportError as exc:
        raise RuntimeError(
            "openpyxl is required for xlsx export: "
            "pip install openpyxl --break-system-packages"
        ) from exc

    wb = Workbook()
    ws = wb.active
    ws.title = "Leads"

    headers = list(Lead.FIELD_ORDER)
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for lead in leads:
        row = lead.as_row()
        ws.append([row[h] for h in headers])

    for col in ws.columns:
        max_len = max(len(str(c.value)) for c in col)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 50)

    wb.save(path)
    logger.info("Wrote %d leads to %s", len(leads), path)


EXPORTERS = {"csv": export_csv, "xlsx": export_xlsx, "json": export_json}


def export(leads: List[Lead], fmt: str, path: str) -> None:
    if fmt not in EXPORTERS:
        raise ValueError(f"Unknown export format: {fmt}")
    EXPORTERS[fmt](leads, path)
