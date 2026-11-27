import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from app.publishing.licensing import LicensingAuditor
from app.publishing.qa import QualityAssuranceEngine
from app.publishing.tracker import CourseProgressTracker
from app.publishing.reconciliation import BCAHierarchyReconciler

def test_inventory_structure():
    """Verify that the BCA syllabus inventory contains all 6 semesters and required fields."""
    inv_file = Path("config/bca_syllabus_inventory.json")
    assert inv_file.exists()
    data = json.loads(inv_file.read_text(encoding="utf-8"))

    assert data["programme"] == "BCA"
    assert len(data["semesters"]) == 6

    # Verify every semester has valid subjects and blocks
    for sem in data["semesters"]:
        assert 1 <= sem["semester_number"] <= 6
        assert len(sem["subjects"]) >= 2
        for subj in sem["subjects"]:
            assert "code" in subj
            assert "name" in subj
            assert len(subj["blocks"]) >= 1
            for blk in subj["blocks"]:
                assert "title" in blk
                assert len(blk["units"]) >= 1

def test_licensing_auditor_rules():
    """Test commercial and non-commercial licensing rules."""
    # 1. Original Synthesis -> Authorized with pricing
    res1 = LicensingAuditor.audit_unit_licensing(
        "BCS-011", 1, content_source_type=LicensingAuditor.LICENSE_ORIGINAL_SYNTHESIS, intended_price=25.0
    )
    assert res1["commercial_allowed"] is True
    assert res1["public_publication_allowed"] is True
    assert res1["audit_verdict"] == "AUTHORIZED_COMMERCIAL_AND_FREE"

    # 2. CC BY-NC-SA with intended_price > 0 -> BLOCKED due to NC clause
    res2 = LicensingAuditor.audit_unit_licensing(
        "BCS-011", 2, content_source_type=LicensingAuditor.LICENSE_CC_BY_NC_SA, intended_price=25.0
    )
    assert res2["commercial_allowed"] is False
    assert res2["public_publication_allowed"] is False
    assert res2["audit_verdict"] == "BLOCKED_COMMERCIAL_RESTRICTION"

    # 3. CC BY-NC-SA with price = 0 -> Authorized for free distribution
    res3 = LicensingAuditor.audit_unit_licensing(
        "BCS-011", 2, content_source_type=LicensingAuditor.LICENSE_CC_BY_NC_SA, intended_price=0.0
    )
    assert res3["commercial_allowed"] is False
    assert res3["public_publication_allowed"] is True
    assert res3["audit_verdict"] == "AUTHORIZED_FREE_ONLY"

    # 4. Proprietary -> Blocked
    res4 = LicensingAuditor.audit_unit_licensing(
        "BCS-011", 3, content_source_type=LicensingAuditor.LICENSE_PROPRIETARY, intended_price=0.0
    )
    assert res4["audit_verdict"] == "BLOCKED_UNAUTHORIZED"

def test_quality_assurance_engine():
    """Test QA auditing logic for clean markup, placeholders, and topics."""
    # Valid pages
    good_pages = [
        {
            "pageNumber": 1,
            "title": "Page 1: Architecture",
            "contentHtml": """<div class="note-chapter">
                <span class="chapter-badge ng-tag">FOUNDATION</span>
                <h1>Page 1: Architecture</h1>
                <h2>1.0 Overview</h2>
                <p>A comprehensive study of CPU architecture and memory hierarchy with detailed explanations.</p>
                <div class="callout callout-info">Important callout text</div>
            </div>""" + (" text" * 150)
        },
        {
            "pageNumber": 2,
            "title": "Page 2: Performance",
            "contentHtml": """<div class="note-chapter">
                <span class="chapter-badge ng-tag">METRICS</span>
                <h1>Page 2: Performance</h1>
                <h2>1.1 CPU Time</h2>
                <p>Calculations using CPU Time = Instruction Count * CPI * Clock Cycle Time.</p>
                <div class="callout callout-warning">Formula callout</div>
            </div>""" + (" text" * 150)
        }
    ]

    report = QualityAssuranceEngine.audit_pages(good_pages, expected_topics=["architecture", "CPU Time"])
    assert report["passed"] is True
    assert report["total_pages"] == 2
    assert report["topic_coverage_percent"] == 100.0

    # Bad pages with forbidden placeholder
    bad_pages = [
        {
            "pageNumber": 1,
            "title": "Page 1: Stub",
            "contentHtml": '<div class="note-chapter"><span class="chapter-badge ng-tag">T</span><h1>T</h1><h2>T</h2><p>Lorem ipsum dolor sit amet placeholder content</p></div>' + (" text" * 150)
        }
    ]
    bad_report = QualityAssuranceEngine.audit_pages(bad_pages)
    assert bad_report["passed"] is False
    assert any("placeholder" in issue.lower() or "lorem" in issue.lower() for issue in bad_report["issues"])

def test_progress_tracker_metrics(tmp_path):
    """Test CourseProgressTracker persistence and metrics calculation."""
    db_file = tmp_path / "test_tracker.db"
    tracker = CourseProgressTracker(db_path=db_file)
    tracker.initialize_from_inventory("config/bca_syllabus_inventory.json")

    units = tracker.get_all_units()
    assert len(units) == 105

    # Update a unit
    u_key = units[0]["unit_key"]
    tracker.update_unit_status(u_key, publishing_status="PUBLISHED", public_url="https://notes-guru.com/test")

    dash = tracker.get_dashboard_summary()
    assert dash["total_semesters"] == 6
    assert dash["total_units"] == 105
    assert dash["completed_notes"] == 1
    assert dash["pending_notes"] == 104
