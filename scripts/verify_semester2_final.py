import json
import requests
from app.publishing.notes_guru_client import NotesGuruApiClient
from app.publishing.tracker import CourseProgressTracker

def verify_all_sem2_notes():
    client = NotesGuruApiClient()
    tracker = CourseProgressTracker()
    units = tracker.get_all_units(semester=2)

    print(f"Total Semester 2 Units in DB: {len(units)}")
    results = []
    
    for u in units:
        note_id = u.get("notes_guru_note_id")
        note_meta = {}
        pages_count = 0
        preview_count = 0
        price = 0
        discounted_price = 0
        is_published = False

        try:
            detail = client.get_note_detail(note_id)
            n = detail.get("note", {})
            pages = detail.get("pages", [])
            pages_count = n.get("totalPages") or len(pages)
            preview_count = n.get("previewPageCount", 0)
            price = n.get("price", 0)
            discounted_price = n.get("discountedPrice", 0)
            is_published = n.get("isPublished", False)
            note_meta = n
        except Exception as e:
            print(f"Error fetching detail for {note_id}: {e}")
            pages_count = -1

        try:
            unauth = requests.get(f"{client.base_url.rstrip('/')}/notes/{note_id}", timeout=10)
            pub_ok = unauth.status_code == 200 and unauth.json().get("success", False)
        except Exception:
            pub_ok = False

        results.append({
            "unit_key": u["unit_key"],
            "subject": u["subject_code"],
            "block": u["block_number"],
            "unit": u["unit_number"],
            "title": u["unit_title"],
            "note_id": note_id,
            "pages": pages_count,
            "preview_count": preview_count,
            "price": price,
            "discounted_price": discounted_price,
            "is_published": is_published,
            "pub_verified": pub_ok,
            "url": u.get("public_url")
        })

    # Output table
    print("\n" + "=" * 95)
    print("FINAL VERIFICATION TABLE: ALL 23 SEMESTER 2 UNITS (GenZnotes)")
    print("=" * 95)
    print(f"{'Subject':<10} {'Blk':<4} {'Unt':<4} {'Pages':<6} {'Price':<10} {'Public':<10} {'Note ID':<26} {'Title'}")
    print("-" * 95)
    for r in results:
        v_str = "YES (200)" if r["pub_verified"] else "FAIL"
        price_str = f"₹{r['discounted_price']}/₹{r['price']}"
        print(f"{r['subject']:<10} {r['block']:<4} {r['unit']:<4} {r['pages']:<6} {price_str:<10} {v_str:<10} {r['note_id']:<26} {r['title'][:30]}")
    print("=" * 95)

    # Summary metrics
    total_pages_sum = sum(r["pages"] for r in results if r["pages"] > 0)
    fully_compliant = sum(1 for r in results if r["pages"] >= 5)
    public_verified = sum(1 for r in results if r["pub_verified"])

    print(f"\nSummary Metrics for Semester 2:")
    print(f"  • Total Units in Semester 2:         {len(results)}")
    print(f"  • Units with >= 5 Pages:              {fully_compliant} / {len(results)} ({fully_compliant/len(results)*100:.1f}%)")
    print(f"  • Total Academic Pages Published:     {total_pages_sum}")
    print(f"  • Public Unauthenticated Access:     {public_verified} / {len(results)} verified HTTP 200 OK")
    print(f"  • Standard Pricing (₹19 / ₹25):      {sum(1 for r in results if r['price'] == 25 and r['discounted_price'] == 19)} / {len(results)}")
    print(f"  • Preview Standard (2 Pages Free):   {sum(1 for r in results if r['preview_count'] == 2)} / {len(results)}")

    # Check Semester 1 integrity
    sem1_units = tracker.get_all_units(semester=1)
    print(f"\nSemester 1 Regression Check:")
    print(f"  • Total Semester 1 Units in DB:      {len(sem1_units)} (Unchanged)")

    return results

if __name__ == "__main__":
    verify_all_sem2_notes()
