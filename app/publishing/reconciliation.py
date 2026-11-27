import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.publishing.notes_guru_client import NotesGuruApiClient

class BCAHierarchyReconciler:
    """
    Reconciles the complete BCA syllabus inventory against the live Notes Guru backend.
    Produces non-destructive audit reports comparing existing vs missing entities.
    """

    def __init__(self, inventory_path: str = "config/bca_syllabus_inventory.json", client: Optional[NotesGuruApiClient] = None):
        self.inventory_path = Path(inventory_path)
        self.client = client or NotesGuruApiClient()
        if not self.inventory_path.exists():
            raise FileNotFoundError(f"Inventory file '{inventory_path}' not found.")
        self.inventory = json.loads(self.inventory_path.read_text(encoding="utf-8"))

    def reconcile_full_bca(self) -> Dict[str, Any]:
        """
        Traverses all 6 semesters in the inventory and matches them against the live Notes Guru hierarchy.
        """
        # 1. Fetch live BCA hierarchy tree from Notes Guru
        live_tree = self.client.fetch_ignou_hierarchy_tree(target_course_code="BCA")
        bca_live = live_tree.get("target_course_tree")
        college_live = live_tree.get("college")

        report: Dict[str, Any] = {
            "college": college_live,
            "course": {
                "_id": bca_live.get("_id") if bca_live else None,
                "name": bca_live.get("name") if bca_live else None,
                "code": "BCA",
                "status": "EXISTS" if bca_live else "MISSING"
            },
            "semesters_summary": [],
            "total_inventory_subjects": 0,
            "total_existing_subjects": 0,
            "total_missing_subjects": 0,
            "total_inventory_units": 0,
            "existing_notes_found": [],
            "reconciliation_actions": []
        }

        if not bca_live:
            report["reconciliation_actions"].append("CRITICAL: Course BCA missing on Notes Guru.")
            return report

        live_semesters_map = {s.get("semesterNumber"): s for s in bca_live.get("semesters", [])}

        for sem_data in self.inventory.get("semesters", []):
            sem_num = sem_data["semester_number"]
            live_sem = live_semesters_map.get(sem_num)

            sem_report: Dict[str, Any] = {
                "semester_number": sem_num,
                "semester_id": live_sem.get("_id") if live_sem else None,
                "status": "EXISTS" if live_sem else "MISSING",
                "subjects": []
            }

            live_subjects_map = {}
            if live_sem:
                for subj in live_sem.get("subjects", []):
                    code_norm = subj.get("code", "").upper().strip()
                    live_subjects_map[code_norm] = subj

            for subj_data in sem_data.get("subjects", []):
                report["total_inventory_subjects"] += 1
                subj_code = subj_data["code"].upper().strip()
                subj_units_count = sum(len(b.get("units", [])) for b in subj_data.get("blocks", []))
                report["total_inventory_units"] += subj_units_count

                live_subj = live_subjects_map.get(subj_code)

                subj_entry: Dict[str, Any] = {
                    "code": subj_data["code"],
                    "name": subj_data["name"],
                    "type": subj_data.get("type", "Theory"),
                    "credits": subj_data.get("credits", 4),
                    "inventory_blocks_count": len(subj_data.get("blocks", [])),
                    "inventory_units_count": subj_units_count,
                    "status": "EXISTS" if live_subj else "MISSING",
                    "existing_subject_id": live_subj.get("_id") if live_subj else None,
                    "existing_blocks": [],
                    "notes_count": 0
                }

                if live_subj:
                    report["total_existing_subjects"] += 1
                    # Inspect blocks and units under this live subject
                    for blk in live_subj.get("blocks", []):
                        blk_units = blk.get("units", [])
                        subj_entry["existing_blocks"].append({
                            "_id": blk.get("_id"),
                            "blockNumber": blk.get("blockNumber"),
                            "name": blk.get("name"),
                            "units_count": len(blk_units),
                            "unit_ids": [u.get("_id") for u in blk_units]
                        })

                        # Check for existing notes on these units
                        for u in blk_units:
                            unit_id = u.get("_id")
                            if unit_id:
                                try:
                                    notes = self.client.get_notes_by_unit(unit_id, include_drafts=True)
                                    if notes:
                                        subj_entry["notes_count"] += len(notes)
                                        for n in notes:
                                            report["existing_notes_found"].append({
                                                "note_id": n.get("_id"),
                                                "title": n.get("title"),
                                                "status": n.get("status"),
                                                "unit_id": unit_id,
                                                "subject_code": subj_code
                                            })
                                except Exception:
                                    pass
                else:
                    report["total_missing_subjects"] += 1

                sem_report["subjects"].append(subj_entry)

            report["semesters_summary"].append(sem_report)

        return report
