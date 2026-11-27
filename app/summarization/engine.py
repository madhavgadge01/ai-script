import json
import uuid
import math
from typing import List, Optional, Dict
from pathlib import Path

from config.settings import settings
from app.pdf.metadata import AcademicHierarchy, ExtractedPage
from app.extraction.chunker import SemanticChunker, Chunk
from app.ai.client import GeminiClient
from app.summarization.schemas import MultiPageNotePlan, StructuredPage, SubSection, ExamCallout
from app.summarization.prompts import ACADEMIC_SYSTEM_INSTRUCTION, CHUNK_PAGE_PROMPT
from app.database.connection import get_db, init_db
from app.database.models import ProcessingStatus

class SummarizationEngine:
    """
    Orchestrates section-aware and chunked multi-page summarization with Gemini,
    atomic SQLite checkpointing, resumption after interruptions, and duplicate detection.
    Guarantees zero content truncation.
    """

    def __init__(
        self,
        client: GeminiClient = None,
        chunker: SemanticChunker = None,
        db_path: Path = None
    ):
        self.client = client or GeminiClient()
        self.chunker = chunker or SemanticChunker(max_chars=4000)
        self.db_path = db_path or settings.db_path
        init_db(self.db_path)

    def calculate_target_page_count(self, total_source_pages: int, total_chunks: int) -> int:
        """
        Calculates target structured pages:
        - 1-4 source pages: 2-4 pages
        - 5-15 source pages: 4-6 pages
        - 16-40 source pages: 7-8 pages
        - 40+ source pages: 8-12 pages
        """
        if total_source_pages <= 4:
            return max(2, min(4, total_chunks))
        elif total_source_pages <= 15:
            return max(4, min(6, total_chunks))
        elif total_source_pages <= 40:
            return max(7, min(8, total_chunks))
        else:
            return max(8, min(12, total_chunks))

    def _cluster_chunks(self, chunks: List[Chunk], target_pages: int) -> List[List[Chunk]]:
        """
        Partitions an ordered list of chunks into exactly `target_pages` clusters.
        Guarantees that 100% of chunks are accounted for in strictly sequential order.
        """
        total_chunks = len(chunks)
        if total_chunks == 0:
            return []

        # If chunks <= target_pages, each chunk gets its own page
        if total_chunks <= target_pages:
            return [[c] for c in chunks]

        clusters: List[List[Chunk]] = []
        chunks_per_page = total_chunks / float(target_pages)
        for i in range(target_pages):
            start_idx = int(round(i * chunks_per_page))
            end_idx = int(round((i + 1) * chunks_per_page))
            cluster = chunks[start_idx:end_idx]
            if cluster:
                clusters.append(cluster)

        # Validation: Verify all chunks are strictly accounted for
        accounted_indices = [c.chunk_index for cluster in clusters for c in cluster]
        expected_indices = [c.chunk_index for c in chunks]
        if accounted_indices != expected_indices:
            raise ValueError(
                f"Chunk clustering validation failed! Accounted: {accounted_indices} != Expected: {expected_indices}"
            )

        return clusters

    def process_unit(
        self,
        hierarchy: AcademicHierarchy,
        extracted_pages: List[ExtractedPage],
        pdf_hash: str,
        force_reprocess: bool = False,
    ) -> MultiPageNotePlan:
        """
        Processes a unit's extracted content into structured notes using a staged,
        checkpointed chunk-to-page pipeline.
        """
        unit_id = f"{hierarchy.course}_{hierarchy.subject_code}_B{hierarchy.block_number}_U{hierarchy.unit_number}"

        # -------------------------------------------------------------------------
        # 1. Duplicate Run Detection (Idempotency Check)
        # -------------------------------------------------------------------------
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, status, source_pdf_hash FROM units WHERE id = ?", (unit_id,))
            row = cursor.fetchone()

            if row and not force_reprocess:
                if row["source_pdf_hash"] == pdf_hash and row["status"] == ProcessingStatus.SUMMARIZED.value:
                    cursor.execute(
                        "SELECT page_number, page_title, content_html FROM generated_pages WHERE unit_id = ? ORDER BY page_number",
                        (unit_id,)
                    )
                    pages_rows = cursor.fetchall()
                    if pages_rows:
                        print(f"[Engine] Unit {unit_id} has already been processed with identical hash. Returning existing plan.")
                        reconstituted_pages = [
                            StructuredPage(
                                page_number=r["page_number"],
                                page_title=r["page_title"],
                                category_badge="ACADEMIC FOUNDATION",
                                intro_paragraph="",
                                sections=[
                                    SubSection(
                                        heading=r["page_title"],
                                        explanation="Loaded from existing processed database record.",
                                    )
                                ]
                            )
                            for r in pages_rows
                        ]
                        return MultiPageNotePlan(
                            unit_number=hierarchy.unit_number,
                            unit_title=hierarchy.unit_title,
                            target_page_count=len(reconstituted_pages),
                            pages=reconstituted_pages
                        )

            # Record or update unit in DB as SUMMARIZING
            cursor.execute("""
                INSERT INTO units (
                    id, university, course, semester, subject_code, subject_name,
                    block_number, block_title, unit_number, unit_title,
                    source_pdf_hash, status, total_pages, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    source_pdf_hash = excluded.source_pdf_hash,
                    status = excluded.status,
                    total_pages = excluded.total_pages,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                unit_id, hierarchy.university, hierarchy.course, hierarchy.semester,
                hierarchy.subject_code, hierarchy.subject_name, hierarchy.block_number,
                hierarchy.block_title, hierarchy.unit_number, hierarchy.unit_title,
                pdf_hash, ProcessingStatus.SUMMARIZING.value, len(extracted_pages)
            ))

        # -------------------------------------------------------------------------
        # 2. Extract Chunks & Account for 100% of Content (No 60k Truncation)
        # -------------------------------------------------------------------------
        chunks = self.chunker.create_chunks(extracted_pages)
        if not chunks:
            raise ValueError(f"No readable content extracted from unit {unit_id}.")

        target_page_count = self.calculate_target_page_count(len(extracted_pages), len(chunks))
        clusters = self._cluster_chunks(chunks, target_page_count)
        actual_page_count = len(clusters)

        generated_pages: List[StructuredPage] = []
        run_id = str(uuid.uuid4())

        # -------------------------------------------------------------------------
        # 3. Process Chunk Clusters Page-by-Page with Checkpoints
        # -------------------------------------------------------------------------
        try:
            for page_idx, cluster in enumerate(clusters, start=1):
                checkpoint_id = f"{unit_id}_p{page_idx}"
                cluster_heading = cluster[0].heading if cluster else f"Section {page_idx}"

                # Combine text from all chunks in this cluster
                cluster_text = "\n\n".join([f"### {c.heading} (Pages {c.page_numbers}):\n{c.content}" for c in cluster])

                # Check if this page already completed in checkpoints
                cached_page = None
                with get_db(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT status, summarized_json FROM chunk_checkpoints WHERE id = ?",
                        (checkpoint_id,)
                    )
                    cp_row = cursor.fetchone()
                    if cp_row and cp_row["status"] == "COMPLETED" and cp_row["summarized_json"] and not force_reprocess:
                        try:
                            cached_page = StructuredPage.model_validate_json(cp_row["summarized_json"])
                        except Exception:
                            cached_page = None

                if cached_page is not None:
                    # Successfully resumed from checkpoint!
                    generated_pages.append(cached_page)
                    continue

                # Generate StructuredPage via Gemini for this specific cluster
                prompt = CHUNK_PAGE_PROMPT.format(
                    page_number=page_idx,
                    total_pages=actual_page_count,
                    university=hierarchy.university,
                    course=hierarchy.course,
                    subject_code=hierarchy.subject_code,
                    subject_name=hierarchy.subject_name,
                    block_number=hierarchy.block_number,
                    block_title=hierarchy.block_title,
                    unit_number=hierarchy.unit_number,
                    unit_title=hierarchy.unit_title,
                    section_heading=cluster_heading,
                    source_text=cluster_text,
                )

                page_result = self.client.generate_structured(
                    prompt=prompt,
                    response_schema=StructuredPage,
                    system_instruction=ACADEMIC_SYSTEM_INSTRUCTION,
                )
                page_result.page_number = page_idx

                # Atomically persist checkpoint in SQLite
                with get_db(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO chunk_checkpoints (
                            id, unit_id, chunk_index, heading, raw_text, cleaned_text, summarized_json, status, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'COMPLETED', CURRENT_TIMESTAMP)
                        ON CONFLICT(id) DO UPDATE SET
                            summarized_json = excluded.summarized_json,
                            status = excluded.status,
                            updated_at = CURRENT_TIMESTAMP
                    """, (
                        checkpoint_id,
                        unit_id,
                        page_idx,
                        cluster_heading,
                        cluster_text,
                        cluster_text,
                        page_result.model_dump_json()
                    ))

                generated_pages.append(page_result)

            # -------------------------------------------------------------------------
            # 4. Final Validation & Record Run
            # -------------------------------------------------------------------------
            if len(generated_pages) != actual_page_count:
                raise ValueError(
                    f"Generated page count mismatch: {len(generated_pages)} != {actual_page_count}"
                )

            metrics = self.client.tracker.get_metrics()
            with get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO processing_runs (
                        id, unit_id, model_used, input_tokens, output_tokens,
                        total_tokens, estimated_cost_usd, duration_seconds, retry_count, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    run_id, unit_id, metrics.model, metrics.input_tokens, metrics.output_tokens,
                    metrics.total_tokens, metrics.estimated_cost_usd, metrics.duration_seconds,
                    metrics.retries, ProcessingStatus.SUMMARIZED.value
                ))

                cursor.execute(
                    "UPDATE units SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (ProcessingStatus.SUMMARIZED.value, unit_id)
                )

            return MultiPageNotePlan(
                unit_number=hierarchy.unit_number,
                unit_title=hierarchy.unit_title,
                target_page_count=len(generated_pages),
                pages=generated_pages
            )

        except Exception as e:
            with get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE units SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (ProcessingStatus.FAILED.value, unit_id)
                )
            raise e
