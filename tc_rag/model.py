from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4

def new_id(prefix: str = "rec") -> str:
    return f"{prefix}_{uuid4().hex}"


@dataclass
class SourceRef:
    source_document_id: str
    source_filename: str
    source_sheet: str = ""
    source_row: int | None = None
    original_tc_id: str = ""


@dataclass
class TestCase:
    record_id: str = field(default_factory=new_id)
    original_tc_id: str = ""
    generated_tc_id: str = ""
    project_id: str = ""
    product_version: str = ""
    category_large: str = ""
    category_medium: str = ""
    category_small: str = ""
    scenario: str = ""
    preconditions: str = ""
    inputs: str = ""
    steps: list[str] = field(default_factory=list)
    expected_results: str | None = None
    postconditions: str = ""
    raw_input_text: str = ""
    raw_expected_output_text: str = ""
    source_refs: list[dict[str, Any]] = field(default_factory=list)
    origin: str = "original"
    review_status: str = "candidate"
    assumptions: list[str] = field(default_factory=list)
    expected_result_basis: str = "existing_tc"
    requires_confirmation: bool = False
    related_record_ids: list[str] = field(default_factory=list)
    reviewer_questions: list[str] = field(default_factory=list)
    difference_from_existing: str = ""
    test_result: str = ""
    detailed_test_result: str = ""
    notes: str = ""
    parser_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TestCase":
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in value.items() if k in allowed})


def embedding_text(tc: TestCase) -> str:
    parts = [
        ("CATEGORY_LARGE", tc.category_large), ("CATEGORY_MEDIUM", tc.category_medium),
        ("CATEGORY_SMALL", tc.category_small), ("SCENARIO", tc.scenario),
        ("PRECONDITIONS", tc.preconditions), ("INPUTS", tc.inputs),
        ("STEPS", "\n".join(tc.steps)), ("EXPECTED_RESULTS", tc.expected_results or ""),
        ("POSTCONDITIONS", tc.postconditions),
    ]
    return "\n".join(f"[{name}]\n{text}" for name, text in parts if text)

