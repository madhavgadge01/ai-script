import json
import requests
from app.publishing.notes_guru_client import NotesGuruApiClient
from app.publishing.tracker import CourseProgressTracker

def verify_all_sem1_notes():
    client = NotesGuruApiClient()
    tracker = CourseProgressTracker()
    units = tracker.get_all_units(semester=1)

    print(f"Total Semester 1 Units in DB: {len(units)}")
    results = []
    
    for u in units:
        note_id = u.get("notes_guru_note_id")
        try:
            detail = client.get_note_detail(note_id)
            n = detail.get("note", {})
            pages = detail.get("pages", [])
            total_pages = n.get("totalPages") or len(pages)
        except Exception as e:
            total_pages = -1

        try:
            unauth = requests.get(f"{client.base_url.rstrip('/')}/notes/{note_id}", timeout=10)
            pub_ok = unauth.status_code == 200 and unauth.json().get("success", False)
        except Exception:
            pub_ok = False

        results.append({
            "subject": u["subject_code"],
            "block": u["block_number"],
            "unit": u["unit_number"],
            "title": u["unit_title"],
            "note_id": note_id,
            "pages": total_pages,
            "pub_verified": pub_ok,
            "url": u.get("public_url")
        })

    # Output table
    print("\n" + "=" * 80)
    print("FINAL VERIFICATION TABLE: ALL 29 SEMESTER 1 UNITS")
    print("=" * 80)
    print(f"{'Subject':<10} {'Blk':<4} {'Unt':<4} {'Pages':<7} {'Status':<12} {'Note ID':<26} {'Title'}")
    print("-" * 80)
    for r in results:
        v_str = "VERIFIED" if r["pub_verified"] else "UNVERIFIED"
        print(f"{r['subject']:<10} {r['block']:<4} {r['unit']:<4} {r['pages']:<7} {v_str:<12} {r['note_id']:<26} {r['title']}")
    print("=" * 80)

    # Summary metrics
    total_pages_sum = sum(r["pages"] for r in results if r["pages"] > 0)
    fully_compliant = sum(1 for r in results if r["pages"] >= 4)
    print(f"\nTotal Published Pages Across Semester 1: {total_pages_sum}")
    print(f"Units Meeting Minimum 4-5 Page Standard: {fully_compliant} / {len(results)}")
    print(f"Public Access Verified: {sum(1 for r in results if r['pub_verified'])} / {len(results)}")

    return results

if __name__ == "__main__":
    verify_all_sem1_notes()
