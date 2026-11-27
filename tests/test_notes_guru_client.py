import pytest
from unittest.mock import patch, MagicMock
from app.publishing.notes_guru_client import NotesGuruApiClient

def test_client_token_masking():
    """Verify that admin tokens are never exposed in logs or string representations."""
    secret_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secret_admin_payload"
    client = NotesGuruApiClient(token=secret_token)

    assert secret_token not in repr(client)
    assert secret_token not in str(client)
    assert "token_configured=True" in repr(client)

@patch("requests.get")
def test_get_colleges_mocked(mock_get):
    """Test get_colleges with mocked response."""
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "success": True,
            "count": 1,
            "colleges": [
                {"_id": "6b00218ae1a606d1dcb62091", "name": "Indira Gandhi National Open University", "code": "IGNOU"}
            ]
        }
    )

    client = NotesGuruApiClient()
    colleges = client.get_colleges()

    assert len(colleges) == 1
    assert colleges[0]["code"] == "IGNOU"
    assert colleges[0]["_id"] == "6b00218ae1a606d1dcb62091"

@patch("requests.get")
def test_fetch_ignou_hierarchy_tree_mocked(mock_get):
    """Test full hierarchy traversal with mocked responses."""
    def side_effect(url, headers, params, timeout):
        mock_resp = MagicMock(status_code=200)
        if "colleges" in url:
            mock_resp.json.return_value = {
                "success": True,
                "colleges": [{"_id": "ignou_123", "name": "Indira Gandhi National Open University", "code": "IGNOU"}]
            }
        elif "courses/college" in url:
            mock_resp.json.return_value = {
                "success": True,
                "courses": [{"_id": "bca_456", "name": "BCA : Bachelor of Computer Applications", "code": "BCA"}]
            }
        elif "semesters/course" in url:
            mock_resp.json.return_value = {
                "success": True,
                "semesters": [{"_id": "sem_1", "name": "Semester 1", "semesterNumber": 1}]
            }
        elif "subjects/semester" in url:
            mock_resp.json.return_value = {
                "success": True,
                "subjects": [{"_id": "sub_1", "name": "Computer Basics", "code": "BCS-011"}]
            }
        elif "blocks/subject" in url:
            mock_resp.json.return_value = {
                "success": True,
                "blocks": [{"_id": "blk_1", "name": "Hardware", "blockNumber": 1}]
            }
        elif "units/block" in url:
            mock_resp.json.return_value = {
                "success": True,
                "units": [{"_id": "unt_1", "title": "Unit 1", "unitNumber": 1}]
            }
        return mock_resp

    mock_get.side_effect = side_effect

    client = NotesGuruApiClient()
    tree = client.fetch_ignou_hierarchy_tree(target_course_code="BCA")

    assert tree["college"]["code"] == "IGNOU"
    assert tree["courses_total_count"] == 1
    target = tree["target_course_tree"]
    assert target is not None
    assert target["code"] == "BCA"
    assert len(target["semesters"]) == 1
    assert target["semesters"][0]["subjects"][0]["code"] == "BCS-011"

def test_reconcile_hierarchy_detects_existing_and_missing():
    """Test reconciliation logic when IGNOU exists but BCA course is missing."""
    client = NotesGuruApiClient()
    live_tree = {
        "college": {"_id": "6b00218ae1a606d1dcb62091", "name": "Indira Gandhi National Open University", "code": "IGNOU"},
        "courses_total_count": 30,
        "courses": [{"_id": "bam_1", "code": "BAM", "name": "BAM : Bachelor of Arts"}],
        "target_course_tree": None
    }

    source_syllabus = {
        "course_code": "BCA",
        "course_name": "Bachelor of Computer Applications",
        "semester_number": 1,
        "subject_code": "BCS-011",
        "subject_name": "Computer Basics and PC Software",
        "block_number": 1,
        "block_title": "Basics of Computer Hardware",
        "unit_number": 1,
        "unit_title": "Computers: Origin and Architecture"
    }

    report = client.reconcile_hierarchy(live_tree, source_syllabus)

    assert report["college_status"] == "EXISTS"
    assert report["course_status"] == "MISSING"
    assert any(dr for dr in report["duplicate_risks"] if "Do NOT create a duplicate College" in dr)
    assert any(mr for mr in report["missing_records"] if mr.get("code") == "BCA")
    assert any(pr for pr in report["proposed_records"] if pr.get("code") == "BCA")

@patch("requests.get")
def test_duplicate_note_detection_exact_unit(mock_get):
    """Test duplicate note detection stops when a note already exists under unitId."""
    def side_effect(url, headers, params, timeout):
        mock_resp = MagicMock(status_code=200)
        if "notes/unit" in url:
            mock_resp.json.return_value = {
                "success": True,
                "count": 1,
                "notes": [
                    {
                        "_id": "existing_note_123",
                        "title": "Computers: Their Origin and Applications",
                        "status": "draft",
                        "pageCount": 4,
                        "unitId": "unit_abc"
                    }
                ]
            }
        elif "search" in url:
            mock_resp.json.return_value = {"success": True, "results": {"notes": []}}
        return mock_resp

    mock_get.side_effect = side_effect

    client = NotesGuruApiClient(token="test_token")
    result = client.check_duplicate_note(
        unit_id="unit_abc",
        title="Computers: Their Origin and Applications"
    )

    assert result["is_duplicate"] is True
    assert result["action"] == "STOP_AND_REPORT"
    assert result["match_level"] == "EXACT_UNIT_AND_TITLE_MATCH"
    assert result["matching_note"]["_id"] == "existing_note_123"

@patch("requests.get")
def test_duplicate_note_detection_safe_when_empty(mock_get):
    """Test duplicate note detection reports SAFE_TO_PROCEED when unit has no notes."""
    def side_effect(url, headers, params, timeout):
        mock_resp = MagicMock(status_code=200)
        if "notes/unit" in url:
            mock_resp.json.return_value = {"success": True, "count": 0, "notes": []}
        elif "search" in url:
            mock_resp.json.return_value = {"success": True, "results": {"notes": []}}
        return mock_resp

    mock_get.side_effect = side_effect

    client = NotesGuruApiClient(token="test_token")
    result = client.check_duplicate_note(
        unit_id="unit_new_123",
        title="New Fresh Academic Note"
    )

    assert result["is_duplicate"] is False
    assert result["action"] == "SAFE_TO_PROCEED"
    assert result["matching_note"] is None

