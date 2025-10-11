"""
Unit tests for reporting adapters: report template store and figure factory.
"""

import json
import os
import sys
from unittest.mock import AsyncMock

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.adapters.figure_factory import FigureFactory
from app.adapters.report_template_store import ReportTemplateStore


@pytest.mark.asyncio
async def test_report_template_store_decodes_sections_and_styles():
    """Ensure report template rows are normalized with JSON fields decoded."""
    clickhouse = AsyncMock()
    sections_payload = json.dumps([
        {
            "section_id": "b",
            "section_title": "Resource Portfolio",
            "section_order": 2,
            "required": True,
            "data_sources": [{"source_type": "clickhouse", "query": "SELECT 1"}],
            "figures": [{"figure_id": "dispatch_profile"}],
        },
        {
            "section_id": "a",
            "section_title": "Executive Summary",
            "section_order": 1,
            "required": True,
            "figures": [{"figure_id": "capacity_additions_chart"}],
            "text_templates": [{"template_id": "summary"}],
        },
    ])
    styles_payload = json.dumps({"font_family": "Arial", "font_size": 11})
    clickhouse.query = AsyncMock(return_value={"data": [
        {
            "template_id": "template-1",
            "template_name": "Test Template",
            "report_type": "irp",
            "jurisdictions": ["CAISO"],
            "document_format": "docx",
            "template_engine": "jinja2",
            "sections": sections_payload,
            "styles": styles_payload,
            "version": "1.0.0",
            "author": "Tester",
            "created_at": "2024-03-01T00:00:00Z",
            "updated_at": "2024-03-01T00:00:00Z",
        }
    ]})

    store = ReportTemplateStore(clickhouse)
    templates = await store.list_templates(report_type=None, jurisdiction=None)

    assert len(templates) == 1
    template = templates[0]
    sections = template["sections"]
    assert [section["section_id"] for section in sections] == ["a", "b"]
    assert sections[0]["figures"][0]["figure_id"] == "capacity_additions_chart"
    assert sections[0]["text_templates"][0]["template_id"] == "summary"
    assert template["styles"]["font_family"] == "Arial"


@pytest.mark.asyncio
async def test_figure_factory_normalizes_and_binds_parameters():
    """Verify figure factory decodes JSON fields and casts parameter types."""
    clickhouse = AsyncMock()
    figure_row = {
        "figure_id": "capacity_additions_chart",
        "figure_type": "bar_chart",
        "data_source": "irp_outputs",
        "query_template": (
            "SELECT * FROM some_table WHERE case_id = {case_id:String} LIMIT {limit:UInt32}"
        ),
        "filters": json.dumps({"market": "CAISO"}),
        "columns": json.dumps([{"column_name": "capacity", "display_name": "Capacity"}]),
        "conditional_formats": json.dumps([]),
        "color_palette": json.dumps(["#000000", "#FFFFFF"]),
        "show_legend": "true",
        "show_grid": "false",
        "created_at": "2024-03-01T00:00:00Z",
        "updated_at": "2024-03-01T00:00:00Z",
        "version": "1.0.0",
    }
    clickhouse.query = AsyncMock(return_value={"data": [{"capacity": 100}]})

    factory = FigureFactory(clickhouse)
    result = await factory.render_figure(figure_row, {"case_id": "case-123", "limit": "25"})

    clickhouse.query.assert_awaited_once_with(
        figure_row["query_template"], {"case_id": "case-123", "limit": 25}
    )
    assert result["figure"]["filters"] == {"market": "CAISO"}
    assert result["figure"]["columns"][0]["display_name"] == "Capacity"
    assert result["figure"]["color_palette"] == ["#000000", "#FFFFFF"]
    assert result["parameters"]["limit"] == 25
    assert result["row_count"] == 1
