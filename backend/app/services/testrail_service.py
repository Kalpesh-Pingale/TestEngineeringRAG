import logging
from typing import List, Optional

from app.config import settings
from app.models.test_case import TestCase, TestRailUploadResult
from app.services.mcp_client import MCPClient

logger = logging.getLogger(__name__)


class TestRailService:
    """Uploads generated test cases to TestRail via MCP server."""

    def __init__(self, mcp_client: Optional[MCPClient] = None):
        self.mcp_client = mcp_client or MCPClient(
            base_url=settings.testrail_mcp_server,
            server_type="testrail",
        )

    async def upload_test_case(
        self,
        test_case: TestCase,
        section_id: Optional[int] = None,
    ) -> TestRailUploadResult:
        section = section_id or settings.testrail_section_id
        try:
            steps_text = "\n".join(
                f"{i+1}. {step}" for i, step in enumerate(test_case.steps)
            )

            result = await self.mcp_client.testrail_create_case(
                section_id=section,
                title=test_case.title,
                template_id=1,
                type_id=self._map_test_type(test_case.test_type),
                priority_id=self._map_priority(test_case.priority),
                refs=test_case.jira_issue_key,
                custom_preconds=test_case.preconditions,
                custom_steps=steps_text,
                custom_expected=test_case.expected_results,
            )

            case_id = result.get("id", result.get("case_id"))
            return TestRailUploadResult(
                test_case_id=case_id,
                testrail_url=f"{settings.testrail_base_url}/index.php?/cases/view/{case_id}",
                success=True,
            )
        except Exception as e:
            logger.error(f"Failed to upload test case '{test_case.title}': {e}")
            return TestRailUploadResult(success=False, error=str(e))

    async def upload_test_cases(
        self,
        test_cases: List[TestCase],
        section_id: Optional[int] = None,
    ) -> List[TestRailUploadResult]:
        results = []
        for tc in test_cases:
            result = await self.upload_test_case(tc, section_id)
            results.append(result)
        return results

    def _map_priority(self, priority: str) -> int:
        mapping = {
            "Highest": 1,
            "High": 2,
            "Medium": 3,
            "Low": 4,
            "Lowest": 5,
        }
        return mapping.get(priority, 3)

    def _map_test_type(self, test_type: str) -> int:
        mapping = {
            "Positive": 1,
            "Negative": 2,
            "Boundary Value": 3,
            "API": 4,
            "UI": 5,
            "Regression": 6,
            "Exploratory": 7,
            "Edge Case": 8,
            "Non-functional": 9,
        }
        return mapping.get(test_type, 1)
