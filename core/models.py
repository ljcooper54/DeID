from dataclasses import dataclass
from enum import Enum
from typing import List

class EntityCategory(str, Enum):
    PERSON = "PERSON"
    ORG = "ORG"
    LOCATION = "LOCATION"
    PATENT = "PATENT"
    PRODUCT_CODE = "PRODUCT_CODE"
    OTHER = "OTHER"

@dataclass(frozen=True)
class DetectedEntity:
    start_char: int
    end_char: int
    text: str
    category: EntityCategory

@dataclass(frozen=True)
class ObscureResult:
    obscured_text: str
    new_mappings: int
    reused_mappings: int
    skipped_temporal: int

@dataclass(frozen=True)
class RestoreResult:
    restored_text: str
