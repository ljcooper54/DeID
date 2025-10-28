# Copyright 2025 H2so4 Consulting LLC

import re
import en_core_web_sm
from typing import List
from .models import DetectedEntity, EntityCategory

import spacy


class EntityDetector:
    # EntityDetector: uses spaCy NER plus custom heuristics to detect sensitive entities
    # (people, orgs, locations, patents, product codenames, emails, etc.) while skipping
    # temporal expressions like dates/quarters.

    def __init__(self, model_name: str = "en_core_web_sm"):
        # __init__: load the spaCy model for NER. Call this once and reuse.
        # self.nlp = spacy.load(model_name) # Usual way
        # __init__: load spaCy English pipeline from bundled model.
        self._nlp = en_core_web_sm.load()
        # __init__  # EntityDetector.__init__

# Copyright 2025 H2so4 Consulting LLC

import spacy
import en_core_web_sm
from .models import DetectedEntity, EntityCategory

class EntityDetector:
    # EntityDetector: runs spaCy NER + our heuristic passes to yield DetectedEntity spans.

    def __init__(self):
        # __init__: load English model from bundled en_core_web_sm package.
        self._nlp = en_core_web_sm.load()
        # __init__  # EntityDetector.__init__

    @property
    def nlp(self):
        # nlp: backwards-compatible accessor that returns the underlying spaCy pipeline.
        return self._nlp
        # nlp  # EntityDetector.nlp

    def detect_entities(self, text: str) -> List[DetectedEntity]:
        # detect_entities: run spaCy, run rule-based passes, merge / dedupe / prioritize.
        doc = self._nlp(text)

        spacy_entities: List[DetectedEntity] = []
        for ent in doc.ents:
            mapped = self._map_spacy_label(ent.label_)
            if mapped is None:
                continue  # skip temporal etc.

            span_text = text[ent.start_char:ent.end_char]

            # Guardrail: don't replace temporal expressions even if spaCy misfires
            if self._looks_like_date(span_text):
                continue

            spacy_entities.append(
                DetectedEntity(
                    start_char=ent.start_char,
                    end_char=ent.end_char,
                    text=span_text,
                    category=mapped,
                )
            )
        # end for  # spaCy entity loop

        # Rule-based detectors to fill gaps spaCy misses.
        patent_entities = self._detect_patents(text)
        product_code_entities = self._detect_product_codes(text)
        email_entities = self._detect_emails(text)
        camelcase_org_entities = self._detect_camelcase_orgs(text)
        greeting_name_entities = self._detect_greeting_names(text)
        handle_entities = self._detect_handle_mentions(text)
        standalone_codename_entities = self._detect_single_token_codenames(text)

        # NEW: detect "Name Name <email@...>" patterns in headers / exports
        name_before_email_entities = self._detect_name_before_email(text)

        all_entities = (
            spacy_entities
            + patent_entities
            + product_code_entities
            + email_entities
            + camelcase_org_entities
            + greeting_name_entities
            + handle_entities
            + standalone_codename_entities
            + name_before_email_entities
        )

        merged = self._merge_overlapping_entities(all_entities)
        merged.sort(key=lambda e: e.start_char)
        return merged
        # detect_entities  # EntityDetector.detect_entities

    def _map_spacy_label(self, label: str):
        # _map_spacy_label: convert spaCy labels to our internal categories.
        label_upper = label.upper()

        # We intentionally ignore temporal labels (dates, quarters, etc.)
        if label_upper in ("DATE", "TIME", "EVENT"):
            return None

        if label_upper == "PERSON":
            return EntityCategory.PERSON
        if label_upper == "ORG":
            return EntityCategory.ORG
        if label_upper in ("GPE", "LOC", "FAC"):
            return EntityCategory.LOCATION
        if label_upper == "PRODUCT":
            return EntityCategory.PRODUCT_CODE
        if label_upper == "LAW":
            return EntityCategory.OTHER

        return EntityCategory.OTHER
        # _map_spacy_label  # EntityDetector._map_spacy_label

    def _detect_patents(self, text: str) -> List[DetectedEntity]:
        # _detect_patents: detect patent identifiers like "U.S. Patent No. 9,876,543".
        results: List[DetectedEntity] = []

        for m in re.finditer(
            r"\b(?:U\.?S\.?\s+)?Patent\s+(?:No\.|Number|#)\s*[0-9,]{4,}\b",
            text,
            flags=re.IGNORECASE,
        ):
            results.append(
                DetectedEntity(
                    start_char=m.start(),
                    end_char=m.end(),
                    text=m.group(0),
                    category=EntityCategory.PATENT,
                )
            )
        # end for  # patent style 1

        for m in re.finditer(
            r"\b(?:US|U\.S\.|WO|EP)\s+[0-9][0-9,./ ]+[A-Z0-9]{1,3}\b",
            text,
            flags=re.IGNORECASE,
        ):
            results.append(
                DetectedEntity(
                    start_char=m.start(),
                    end_char=m.end(),
                    text=m.group(0),
                    category=EntityCategory.PATENT,
                )
            )
        # end for  # patent style 2

        return results
        # _detect_patents  # EntityDetector._detect_patents

    def _detect_product_codes(self, text: str) -> List[DetectedEntity]:
        # _detect_product_codes: detect explicit code phrases like "Project Falcon v2.1"
        # and SKUs like "ACME-9000", while not confusing "Q1 2025".
        results: List[DetectedEntity] = []

        for m in re.finditer(
            r"\b(Project|Codename)\s+[A-Z][A-Za-z0-9_-]*(?:\s+v[0-9.]+)?",
            text,
        ):
            span = m.group(0)
            if self._looks_like_quarter(span):
                continue
            if self._looks_like_date(span):
                continue

            results.append(
                DetectedEntity(
                    start_char=m.start(),
                    end_char=m.end(),
                    text=span,
                    category=EntityCategory.PRODUCT_CODE,
                )
            )
        # end for  # Pattern A

        for m in re.finditer(
            r"\b[A-Z][A-Z0-9]{1,}[-_][A-Z0-9]{2,}\b",
            text,
        ):
            span = m.group(0)
            if self._looks_like_quarter(span):
                continue
            if self._looks_like_date(span):
                continue
            results.append(
                DetectedEntity(
                    start_char=m.start(),
                    end_char=m.end(),
                    text=span,
                    category=EntityCategory.PRODUCT_CODE,
                )
            )
        # end for  # Pattern B

        return results
        # _detect_product_codes  # EntityDetector._detect_product_codes

    def _detect_emails(self, text: str) -> List[DetectedEntity]:
        # _detect_emails: capture email addresses as sensitive identifiers.
        results: List[DetectedEntity] = []

        for m in re.finditer(
            r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[A-Za-z]{2,}\b",
            text,
        ):
            results.append(
                DetectedEntity(
                    start_char=m.start(),
                    end_char=m.end(),
                    text=m.group(0),
                    category=EntityCategory.OTHER,
                )
            )
        # end for  # email loop

        return results
        # _detect_emails  # EntityDetector._detect_emails

    def _detect_camelcase_orgs(self, text: str) -> List[DetectedEntity]:
        # _detect_camelcase_orgs: detect single-token company-style names like "BainCap".
        results: List[DetectedEntity] = []

        for m in re.finditer(
            r"\b[A-Z][a-z]+[A-Z][A-Za-z0-9]+\b",
            text,
        ):
            span = m.group(0)
            if self._looks_like_date(span):
                continue
            if self._looks_like_quarter(span):
                continue

            results.append(
                DetectedEntity(
                    start_char=m.start(),
                    end_char=m.end(),
                    text=span,
                    category=EntityCategory.ORG,
                )
            )
        # end for  # camelCase org loop

        return results
        # _detect_camelcase_orgs  # EntityDetector._detect_camelcase_orgs

    def _detect_greeting_names(self, text: str) -> List[DetectedEntity]:
        # _detect_greeting_names: catch "Hi Ryan", "Hey Lorne,", "Thanks Athena", "Thanks [Brient]", etc.
        # We mark these as PERSON.
        results: List[DetectedEntity] = []

        pattern = re.compile(
            r"\b(?:Hi|Hey|Hello|Thanks|Thank\s+you|Dear)\s+"
            r"([@\[({]?[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?[\])}:,]?)",
            re.IGNORECASE,
        )

        for m in pattern.finditer(text):
            raw = m.group(1)
            cleaned = raw.strip("[](){}:,>@")
            if not cleaned:
                continue
            if self._looks_like_date(cleaned):
                continue
            if self._looks_like_quarter(cleaned):
                continue

            start_char = m.start(1)
            end_char = m.end(1)

            results.append(
                DetectedEntity(
                    start_char=start_char,
                    end_char=end_char,
                    text=raw,
                    category=EntityCategory.PERSON,
                )
            )
        # end for  # greeting loop

        return results
        # _detect_greeting_names  # EntityDetector._detect_greeting_names

    def _detect_handle_mentions(self, text: str) -> List[DetectedEntity]:
        # _detect_handle_mentions: catch @Ryan or @Ryan Jacobson.
        results: List[DetectedEntity] = []

        pattern = re.compile(
            r"@([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)"
        )

        for m in pattern.finditer(text):
            raw = m.group(0)  # "@Ryan" or "@Ryan Jacobson"
            cleaned = raw.lstrip("@")
            if self._looks_like_date(cleaned):
                continue
            if self._looks_like_quarter(cleaned):
                continue

            results.append(
                DetectedEntity(
                    start_char=m.start(),
                    end_char=m.end(),
                    text=raw,
                    category=EntityCategory.PERSON,
                )
            )
        # end for  # handle loop

        return results
        # _detect_handle_mentions  # EntityDetector._detect_handle_mentions

    def _detect_single_token_codenames(self, text: str) -> List[DetectedEntity]:
        # _detect_single_token_codenames: detect things like "Athena rollout", "BainCap diligence".
        results: List[DetectedEntity] = []

        trigger_words = (
            r"rollout|launch|diligence|workstream|initiative|program|platform|phase|deal\s+team"
        )

        pat1 = re.compile(
            rf"\b([A-Z][a-zA-Z0-9]+)\s+(?:{trigger_words})\b",
            re.IGNORECASE,
        )

        pat2 = re.compile(
            rf"\b(?:{trigger_words})\s+(?:for|on|of|around)\s+([A-Z][a-zA-Z0-9]+)\b",
            re.IGNORECASE,
        )

        for m in pat1.finditer(text):
            name = m.group(1)
            if self._looks_like_date(name) or self._looks_like_quarter(name):
                continue
            results.append(
                DetectedEntity(
                    start_char=m.start(1),
                    end_char=m.end(1),
                    text=name,
                    category=EntityCategory.PRODUCT_CODE,
                )
            )
        # end for  # pat1 loop

        for m in pat2.finditer(text):
            name = m.group(1)
            if self._looks_like_date(name) or self._looks_like_quarter(name):
                continue
            results.append(
                DetectedEntity(
                    start_char=m.start(1),
                    end_char=m.end(1),
                    text=name,
                    category=EntityCategory.PRODUCT_CODE,
                )
            )
        # end for  # pat2 loop

        return results
        # _detect_single_token_codenames  # EntityDetector._detect_single_token_codenames

    def _detect_name_before_email(self, text: str) -> List[DetectedEntity]:
        # _detect_name_before_email: catch patterns like:
        # "Lorne Cooper <ljcooper54@gmail.com>"
        # "Jane Doe\t<jane@company.com>"
        #
        # We mark the name span as PERSON.
        results: List[DetectedEntity] = []

        # Two-token case: First Last <email>
        pat_full = re.compile(
            r"\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+))\s*[<]\s*[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\s*[>]"
        )

        # Also allow single-token first names before email, e.g. "Athena <athena@...>"
        pat_single = re.compile(
            r"\b([A-Z][A-Za-z]+)\s*[<]\s*[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\s*[>]"
        )

        for m in pat_full.finditer(text):
            name_span = m.group(1)
            if self._looks_like_date(name_span) or self._looks_like_quarter(name_span):
                continue
            results.append(
                DetectedEntity(
                    start_char=m.start(1),
                    end_char=m.end(1),
                    text=name_span,
                    category=EntityCategory.PERSON,
                )
            )
        # end for  # full-name loop

        for m in pat_single.finditer(text):
            name_span = m.group(1)
            if self._looks_like_date(name_span) or self._looks_like_quarter(name_span):
                continue
            results.append(
                DetectedEntity(
                    start_char=m.start(1),
                    end_char=m.end(1),
                    text=name_span,
                    category=EntityCategory.PERSON,
                )
            )
        # end for  # single-name loop

        return results
        # _detect_name_before_email  # EntityDetector._detect_name_before_email

    def _looks_like_date(self, s: str) -> bool:
        # _looks_like_date: detect temporal/quarter/time expressions; we never obscure these.
        if re.search(r"\bQ[1-4]\s+FY?\d{4}\b", s, flags=re.IGNORECASE):
            return True
        if re.search(r"\bQ[1-4]\s+\d{4}\b", s, flags=re.IGNORECASE):
            return True
        if re.search(
            r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(st|nd|rd|th)?(,\s*\d{4})?\b",
            s,
            flags=re.IGNORECASE,
        ):
            return True
        if re.search(
            r"\b\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)(\s+\d{4})?\b",
            s,
            flags=re.IGNORECASE,
        ):
            return True
        if re.search(
            r"\b(Spring|Summer|Fall|Autumn|Winter)\s+\d{4}\b",
            s,
            flags=re.IGNORECASE,
        ):
            return True
        return False
        # _looks_like_date  # EntityDetector._looks_like_date

    def _looks_like_quarter(self, s: str) -> bool:
        # _looks_like_quarter: detect "Q1 2025", "Q3 FY2024".
        if re.search(r"\bQ[1-4]\s+\d{4}\b", s, flags=re.IGNORECASE):
            return True
        if re.search(r"\bQ[1-4]\s+FY?\d{4}\b", s, flags=re.IGNORECASE):
            return True
        return False
        # _looks_like_quarter  # EntityDetector._looks_like_quarter

    def _merge_overlapping_entities(self, entities: List[DetectedEntity]) -> List[DetectedEntity]:
        # _merge_overlapping_entities: resolve overlaps by priority so each character range
        # maps to only one category. Higher priority wins.
        priority_order = {
            EntityCategory.PATENT: 7,
            EntityCategory.PRODUCT_CODE: 6,
            EntityCategory.PERSON: 5,
            EntityCategory.ORG: 4,
            EntityCategory.LOCATION: 3,
            EntityCategory.OTHER: 2,
        }

        sorted_ents = sorted(
            entities,
            key=lambda e: (
                e.start_char,
                -(priority_order.get(e.category, 0)),
                -(e.end_char - e.start_char),
            ),
        )

        accepted: List[DetectedEntity] = []
        for cand in sorted_ents:
            overlaps = False
            for kept in accepted:
                if not (cand.end_char <= kept.start_char or cand.start_char >= kept.end_char):
                    overlaps = True
                    break
            if not overlaps:
                accepted.append(cand)
        # end for  # merge loop

        return accepted
        # _merge_overlapping_entities  # EntityDetector._merge_overlapping_entities

# EntityDetector.py