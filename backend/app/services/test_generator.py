import json
import logging
import re
from typing import List

from app.models.test_case import TestCase
from app.models.rag import RAGResponse

logger = logging.getLogger(__name__)


class TestGenerator:
    """Parses LLM output into structured test cases."""

    def parse_rag_response(
        self, rag_response: RAGResponse
    ) -> List[TestCase]:
        text = rag_response.generated_response
        return self.parse_text(text, rag_response.query)

    def parse_text(
        self, text: str, issue_key: str = ""
    ) -> List[TestCase]:
        json_cases = self._parse_json(text, issue_key)
        if json_cases:
            return json_cases

        test_cases: List[TestCase] = []
        blocks = re.split(r"(?:^|\n)\s*(?:#+\s*|Test\s+(?:Case|Scenario)\s*[#:]?\s*\d*)\s*", text.strip())

        for block in blocks:
            block = block.strip()
            if not block or len(block) < 20:
                continue

            title = self._extract_field(block, ["Title", "Test Title", "Name"])
            if not title:
                lines = block.split("\n")
                title = lines[0].strip().rstrip(":")
                if len(title) > 100:
                    title = title[:97] + "..."

            preconditions = self._extract_field(
                block, ["Preconditions", "Pre-condition", "Prerequisites", "Setup"]
            )
            steps_raw = self._extract_field(
                block, ["Steps", "Test Steps", "Procedure", "Test Procedure"]
            )
            steps = (
                [s.strip() for s in steps_raw.split("\n") if s.strip()]
                if steps_raw
                else []
            )
            expected = self._extract_field(
                block,
                [
                    "Expected Results",
                    "Expected Result",
                    "Expected Outcome",
                    "Expected Behavior",
                ],
            )
            priority = self._extract_field(block, ["Priority"])
            if not priority:
                priority = self._infer_priority(block)

            test_type = self._extract_field(block, ["Test Type", "Type"])
            if not test_type:
                test_type = self._infer_test_type(block)

            automation = self._extract_field(
                block, ["Automation Candidate", "Automation", "Automated"]
            )
            if not automation:
                automation = "Yes" if "api" in block.lower() or "automation" in block.lower() else "No"

            test_cases.append(
                TestCase(
                    title=title,
                    preconditions=preconditions or "",
                    steps=steps if steps else [block],
                    expected_results=expected or "See test steps for expected behavior.",
                    priority=priority,
                    test_type=test_type,
                    automation_candidate=automation,
                    requirement=issue_key,
                    jira_issue_key=issue_key,
                )
            )

        return test_cases

    def _parse_json(self, text: str, issue_key: str) -> List[TestCase]:
        cleaned = text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```\s*$", "", cleaned)

        match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if not match:
            return []

        try:
            raw_cases = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []

        if not isinstance(raw_cases, list):
            return []

        test_cases: List[TestCase] = []
        for item in raw_cases:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            if not title:
                continue

            steps = item.get("steps") or []
            if isinstance(steps, str):
                steps = [s.strip() for s in steps.split("\n") if s.strip()]
            else:
                steps = [str(s).strip() for s in steps if str(s).strip()]

            test_cases.append(
                TestCase(
                    title=title,
                    preconditions=str(item.get("preconditions") or ""),
                    steps=steps,
                    expected_results=str(item.get("expected_results") or "See test steps for expected behavior."),
                    priority=str(item.get("priority") or "Medium"),
                    test_type=str(item.get("test_type") or "Positive"),
                    automation_candidate=str(item.get("automation_candidate") or "No"),
                    requirement=issue_key,
                    jira_issue_key=issue_key,
                )
            )

        return test_cases

    def _extract_field(self, text: str, field_names: List[str]) -> str:
        for name in field_names:
            patterns = [
                rf"(?:^|\n)\s*[*]?{re.escape(name)}\s*[*]?:\s*(.+?)(?=\n\s*\n|\n\s*[*]?(?:{'|'.join(self._common_headers())})\s*:|\Z)",
                rf"(?:^|\n)\s*[-]?\s*{re.escape(name)}\s*:\s*(.+)",
            ]
            for pat in patterns:
                m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
                if m:
                    value = m.group(1).strip().rstrip("\n")
                    return value
        return ""

    def _common_headers(self) -> List[str]:
        return [
            "Title", "Preconditions", "Steps", "Expected Results",
            "Priority", "Test Type", "Automation Candidate",
            "Automation", "Expected Result", "Expected Outcome",
        ]

    def _infer_priority(self, text: str) -> str:
        text_lower = text.lower()
        if "critical" in text_lower or "high" in text_lower:
            return "High"
        if "medium" in text_lower:
            return "Medium"
        if "low" in text_lower:
            return "Low"
        return "Medium"

    def _infer_test_type(self, text: str) -> str:
        text_lower = text.lower()
        if "negative" in text_lower or "invalid" in text_lower:
            return "Negative"
        if "boundary" in text_lower:
            return "Boundary Value"
        if "api" in text_lower or "endpoint" in text_lower:
            return "API"
        if "ui" in text_lower or "user interface" in text_lower:
            return "UI"
        if "regression" in text_lower:
            return "Regression"
        if "exploratory" in text_lower:
            return "Exploratory"
        if "edge" in text_lower:
            return "Edge Case"
        if "non-functional" in text_lower or "performance" in text_lower or "security" in text_lower:
            return "Non-functional"
        return "Positive"
