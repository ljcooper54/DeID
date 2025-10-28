# Copyright 2025 H2so4 Consulting LLC

import os
from typing import Dict, List, Tuple
from .persistence import Persistence
from .models import RestoreResult


class RestoreService:
    # RestoreService: reverses anonymization for a given project by mapping
    # pseudonyms back to their original values. Also determines the proper
    # restored filename using "Restored_<...>" rules.

    def __init__(self, db: Persistence):
        # __init__: store persistence layer for reading entity mappings.
        self.db = db
        # __init__  # RestoreService.__init__

    def restore_text(self, project_id: int, obscured_text: str) -> RestoreResult:
        # restore_text: take the obscured text and replace each pseudonym with its
        # original value using entity_mapping for the given project.

        # 1. Build reverse map { pseudonym -> original_value }.
        mapping_rows = self.db.get_all_mappings_for_project(project_id)

        pseudo_to_original: Dict[str, str] = {}
        for row in mapping_rows:
            pseudo_to_original[row["pseudonym"]] = row["original_value"]
        # end for  # mapping_rows loop

        # 2. Prepare replacements sorted so longer pseudonyms are replaced first,
        # which avoids partial collisions (e.g. "Person_10" before "Person_1").
        replacements: List[Tuple[str, str]] = []
        for pseudo, orig in pseudo_to_original.items():
            replacements.append((pseudo, orig))
        # end for  # pseudo_to_original loop

        replacements.sort(key=lambda pr: len(pr[0]), reverse=True)

        restored_text = obscured_text
        for pseudo, orig in replacements:
            restored_text = restored_text.replace(pseudo, orig)
        # end for  # replacements loop

        result = RestoreResult(
            restored_text=restored_text
        )
        return result
        # restore_text  # RestoreService.restore_text

    def build_restored_filename(self, file_path: str) -> str:
        # build_restored_filename: given the obscured file path, return the output path
        # using:
        #   - If file name starts with "Obscured_", replace that prefix with "Restored_"
        #   - Else prepend "Restored_"
        directory, name = os.path.split(file_path)

        if name.startswith("Obscured_"):
            # Replace "Obscured_" with "Restored_"
            rest = name[len("Obscured_"):]
            restored_name = f"Restored_{rest}"
        else:
            restored_name = f"Restored_{name}"

        return os.path.join(directory, restored_name)
        # build_restored_filename  # RestoreService.build_restored_filename

# RestoreService
