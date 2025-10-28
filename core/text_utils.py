from typing import List, Tuple

def apply_replacements(text: str,
                       replacements: List[Tuple[int, int, str]]) -> str:
    # replacements MUST be sorted by start DESC
    out = text
    for start, end, new_text in replacements:
        out = out[:start] + new_text + out[end:]
    return out
