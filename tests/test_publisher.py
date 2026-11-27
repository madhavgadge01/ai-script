import pytest
from unittest.mock import MagicMock, patch
from app.publishing.publisher import NotesPublisher

def test_load_local_pages():
    """Verify loading local HTML pages from storage."""
    publisher = NotesPublisher(client=MagicMock())
    pages = publisher.load_local_pages(export_dir="storage/exports/BCA_BCS-011_U1")
    assert len(pages) == 4
    for idx, p in enumerate(pages, 1):
        assert p["pageNumber"] == idx
        assert "class=\"note-chapter\"" in p["contentHtml"]
        if idx <= 2:
            assert p["isLockedPreview"] is False
        else:
            assert p["isLockedPreview"] is True

def test_publish_workflow_mocked():
    """Verify the 11-step publishing workflow end-to-end with mocked API client."""
    mock_client = MagicMock()
    mock_client.base_url = "https://notes-guru-production.up.railway.app/api/"

    # Step 1: Mock IGNOU college
    mock_client.get_colleges.return_value = [
        {"_id": "ignou_college_id", "code": "IGNOU", "name": "Indira Gandhi National Open University"}
    ]

    # Step 2: BCA missing -> created
    mock_client.get_courses_by_college.return_value = []
    mock_client.create_course.return_value = {
        "success": True,
        "course": {"_id": "bca_course_id", "code": "BCA", "name": "BCA"}
    }

    # Step 3: Fetch semesters -> Semester 1 found
    mock_client.get_semesters_by_course.return_value = [
        {"_id": "sem_1_id", "semesterNumber": 1, "name": "Semester 1"},
        {"_id": "sem_2_id", "semesterNumber": 2, "name": "Semester 2"}
    ]

    # Step 4 & 5: Subject BCS-011 missing -> created, auto-spawns Block 1
    mock_client.get_subjects_by_semester.return_value = []
    mock_client.create_subject.return_value = {
        "success": True,
        "subject": {"_id": "sub_bcs011_id", "code": "BCS-011", "name": "Computer Basics and PC Software"},
        "block": {"_id": "blk_1_id", "blockNumber": 1, "name": "Computer Basics and PC Software"}
    }

    # Units under block 1
    mock_client.get_units_by_block.return_value = [
        {"_id": "unit_1_id", "unitNumber": 1, "title": "Computer Basics and PC Software"}
    ]

    mock_client.update_block.return_value = {"success": True}
    mock_client.update_unit.return_value = {"success": True}

    # Step 7: Duplicate check -> safe
    mock_client.check_duplicate_note.return_value = {"is_duplicate": False}

    # Step 9 & 10: Create note -> published
    mock_client.create_note.return_value = {
        "success": True,
        "note": {
            "_id": "pub_note_id_123",
            "title": "Computers: Their Origin and Applications",
            "status": "published",
            "isPublished": True
        }
    }

    publisher = NotesPublisher(client=mock_client)

    with patch("requests.get") as mock_http_get:
        mock_http_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"success": True, "note": {"status": "published", "isPublished": True}}
        )

        result = publisher.publish_bca_unit_1(
            export_dir="storage/exports/BCA_BCS-011_U1",
            unit_title="Computers: Their Origin and Applications"
        )

        assert result["college_id"] == "ignou_college_id"
        assert result["course_id"] == "bca_course_id"
        assert result["semester_id"] == "sem_1_id"
        assert result["subject_id"] == "sub_bcs011_id"
        assert result["block_id"] == "blk_1_id"
        assert result["unit_id"] == "unit_1_id"
        assert result["note_id"] == "pub_note_id_123"
        assert result["status"] == "published"
        assert result["is_published"] is True
        assert result["unauthenticated_verified"] is True
        assert result["page_count"] == 4
