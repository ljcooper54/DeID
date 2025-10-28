# Copyright 2025 H2so4 Consulting LLC

import os
from typing import List, Tuple
from .models import ObscureResult, DetectedEntity, EntityCategory
from .entity_detector import EntityDetector
from .pseudonym_mapper import PseudonymMapper
from .persistence import Persistence
from . import text_utils, hash_utils


class ObscureService:
    # ObscureService: end-to-end anonymization pipeline for a project.
    # Detects sensitive entities, merges with user/project forced names, assigns pseudonyms,
    # applies replacements, logs history, and generates consistent output filenames
    # using "Obscured_<originalname>".

    def __init__(self,
                 detector: EntityDetector,
                 mapper: PseudonymMapper,
                 db: Persistence):
        # __init__: store references to detection, pseudonym mapping, and persistence layers.
        self.detector = detector
        self.mapper = mapper
        self.db = db
        # __init__  # ObscureService.__init__

    def obscure_text(self,
                     project_id: int,
                     file_path: str,
                     text: str) -> ObscureResult:
        # obscure_text: run anonymization on `text` for the given project.
        # Steps:
        #   1. detect NLP entities
        #   2. include forced names (user + project)
        #   3. merge and dedupe entities
        #   4. allocate / reuse pseudonyms
        #   5. apply replacements
        #   6. update database bookkeeping / audit trail
        #   7. return ObscureResult with obscured text

        # 1. Get the owner of this project so we know which global forced-redaction names to include.
        owner_user_id = self.db.get_project_owner(project_id)

        # 2. Detect entities via NLP + heuristics.
        base_entities = self.detector.detect_entities(text)

        # 3. Build spans from the user's global forced names and the project's forced names.
        user_forced_spans = self._forced_name_spans_for_user(owner_user_id, text)
        project_forced_spans = self._forced_name_spans_for_project(project_id, text)

        # 4. Combine and then merge to eliminate overlap conflicts.
        combined_entities = base_entities + user_forced_spans + project_forced_spans
        merged_entities = self._merge_overlapping_entities(combined_entities)

        # 5. Assign stable pseudonyms.
        # We'll keep an in-run cache so that if "Alice Chen" occurs 20 times, we reuse the
        # exact same pseudonym for that original string within this call.
        replacements: List[Tuple[int, int, str]] = []
        seen_text_to_pseudonym = {}

        for ent in merged_entities:
            category = ent.category

            if ent.text in seen_text_to_pseudonym:
                pseudonym = seen_text_to_pseudonym[ent.text]
            else:
                pseudonym = self.mapper.get_or_create_pseudonym(
                    project_id,
                    category,
                    ent.text
                )
                seen_text_to_pseudonym[ent.text] = pseudonym

            replacements.append((ent.start_char, ent.end_char, pseudonym))
        # end for  # merged_entities loop

        # 6. Apply replacements (reverse sort so we don't shift later spans).
        replacements.sort(key=lambda r: r[0], reverse=True)
        obscured_text = text_utils.apply_replacements(text, replacements)

        # 7. Update project_file table so the file is associated with the project.
        self.db.upsert_project_file(
            project_id,
            hash_utils.path_hash(file_path),
            display_name=file_path
        )

        # 8. Record audit trail of this run.
        self.db.record_history(
            project_id,
            hash_utils.content_hash(text),
            hash_utils.content_hash(obscured_text)
        )

        # 9. Return result object.
        result = ObscureResult(
            obscured_text=obscured_text,
            new_mappings=0,        # placeholder counts; can be expanded later
            reused_mappings=0,
            skipped_temporal=0
        )
        return result
        # obscure_text  # ObscureService.obscure_text

    def _forced_name_spans_for_user(self, user_id: int, text: str) -> List[DetectedEntity]:
        # _forced_name_spans_for_user: for all globally forced redaction names belonging to `user_id`,
        # create DetectedEntity spans in the text.
        names = self.db.list_user_known_names(user_id)
        return self._string_match_entities(text, names, EntityCategory.PERSON)
        # _forced_name_spans_for_user  # ObscureService._forced_name_spans_for_user

    def _forced_name_spans_for_project(self, project_id: int, text: str) -> List[DetectedEntity]:
        # _forced_name_spans_for_project: for the current project's forced-redaction list,
        # create DetectedEntity spans in the text.
        names = self.db.list_project_known_names(project_id)
        return self._string_match_entities(text, names, EntityCategory.PERSON)
        # _forced_name_spans_for_project  # ObscureService._forced_name_spans_for_project

    def _string_match_entities(self,
                               text: str,
                               names: List[str],
                               category: EntityCategory) -> List[DetectedEntity]:
        # _string_match_entities: naive span finder for exact names/terms in `names`.
        # We only match on token-ish boundaries to avoid partial hits in the middle of words.
        import re

        results: List[DetectedEntity] = []

        for name_value in names:
            if not name_value:
                continue

            escaped = re.escape(name_value)
            pattern = re.compile(
                r"(?<![A-Za-z0-9])" + escaped + r"(?![A-Za-z0-9])"
            )

            for m in pattern.finditer(text):
                results.append(
                    DetectedEntity(
                        start_char=m.start(),
                        end_char=m.end(),
                        text=m.group(0),
                        category=category
                    )
                )
            # end for  # pattern.finditer loop
        # end for  # names loop

        return results
        # _string_match_entities  # ObscureService._string_match_entities

    def _merge_overlapping_entities(self, entities: List[DetectedEntity]) -> List[DetectedEntity]:
        # _merge_overlapping_entities: merge overlapping spans so we don't double-replace text.
        # If multiple entities overlap, we keep the "highest priority" one using a manual ranking.

        priority_order = {
            EntityCategory.PATENT: 7,
            EntityCategory.PRODUCT_CODE: 6,
            EntityCategory.PERSON: 5,
            EntityCategory.ORG: 4,
            EntityCategory.LOCATION: 3,
            EntityCategory.OTHER: 2,
        }

        # Sort candidates so we consider "better" entities first:
        #   1) start position ASC
        #   2) category priority DESC
        #   3) span length DESC
        sorted_ents = sorted(
            entities,
            key=lambda e: (
                e.start_char,
                -(priority_order.get(e.category, 0)),
                -(e.end_char - e.start_char),
            )
        )

        accepted: List[DetectedEntity] = []

        for cand in sorted_ents:
            overlaps = False
            for kept in accepted:
                # Overlap check:
                # They overlap if the start is before the other's end
                # and the end is after the other's start.
                if not (cand.end_char <= kept.start_char or cand.start_char >= kept.end_char):
                    overlaps = True
                    break
            if not overlaps:
                accepted.append(cand)
        # end for  # sorted_ents loop

        return accepted
        # _merge_overlapping_entities  # ObscureService._merge_overlapping_entities

    def build_obscured_filename(self, file_path: str) -> str:
        # build_obscured_filename: for an input path, return the output path
        # using the rule "Obscured_<original_filename>" in the same directory.
        directory, name = os.path.split(file_path)
        obscured_name = f"Obscured_{name}"
        return os.path.join(directory, obscured_name)
        # build_obscured_filename  # ObscureService.build_obscured_filename

# ObscureService
