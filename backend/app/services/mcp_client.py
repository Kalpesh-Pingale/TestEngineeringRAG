import json
import logging
from typing import Any, Dict, List, Optional
import aiohttp

logger = logging.getLogger(__name__)


class MCPClient:
    """Client for Model Context Protocol (MCP) servers (Jira, TestRail)."""

    def __init__(self, base_url: str, server_type: str = "generic"):
        self.base_url = base_url.rstrip("/")
        self.server_type = server_type
        self.session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None

    async def _request(
        self, method: str, endpoint: str, **kwargs
    ) -> Dict[str, Any]:
        await self._ensure_session()
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            async with self.session.request(method, url, **kwargs) as resp:
                data = await resp.json()
                if not resp.ok:
                    raise Exception(
                        f"MCP {self.server_type} error {resp.status}: {data}"
                    )
                return data
        except aiohttp.ClientError as e:
            raise Exception(f"MCP {self.server_type} connection failed: {e}")

    # --- Jira MCP ---

    async def jira_get_project_issues(
        self,
        project_key: str,
        issue_types: Optional[List[str]] = None,
        jql: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        payload = {"project_key": project_key}
        if issue_types:
            payload["issue_types"] = issue_types
        if jql:
            payload["jql"] = jql
        result = await self._request("POST", "jira/search", json=payload)
        return result.get("issues", result.get("data", []))

    async def jira_get_incremental_issues(
        self,
        project_key: str,
        last_sync_time: str,
        issue_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        payload = {"project_key": project_key, "updated_since": last_sync_time}
        if issue_types:
            payload["issue_types"] = issue_types
        result = await self._request(
            "POST", "jira/incremental", json=payload
        )
        return result.get("issues", result.get("data", []))

    async def jira_get_issue_details(
        self, issue_key: str
    ) -> Dict[str, Any]:
        result = await self._request(
            "GET", f"jira/issue/{issue_key}"
        )
        return result.get("issue", result.get("data", result))

    # --- TestRail MCP ---

    async def testrail_get_projects(self) -> List[Dict[str, Any]]:
        result = await self._request("GET", "testrail/projects")
        return result.get("projects", result.get("data", []))

    async def testrail_get_sections(
        self, project_id: int, suite_id: int
    ) -> List[Dict[str, Any]]:
        result = await self._request(
            "GET",
            f"testrail/sections?project_id={project_id}&suite_id={suite_id}",
        )
        return result.get("sections", result.get("data", []))

    async def testrail_create_case(
        self,
        section_id: int,
        title: str,
        template_id: int = 1,
        type_id: int = 1,
        priority_id: int = 3,
        estimate: Optional[str] = None,
        refs: Optional[str] = None,
        custom_preconds: Optional[str] = None,
        custom_steps: Optional[str] = None,
        custom_expected: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {
            "section_id": section_id,
            "title": title,
            "template_id": template_id,
            "type_id": type_id,
            "priority_id": priority_id,
        }
        if estimate:
            payload["estimate"] = estimate
        if refs:
            payload["refs"] = refs
        if custom_preconds:
            payload["custom_preconds"] = custom_preconds
        if custom_steps:
            payload["custom_steps"] = custom_steps
        if custom_expected:
            payload["custom_expected"] = custom_expected
        result = await self._request(
            "POST", "testrail/case", json=payload
        )
        return result.get("case", result.get("data", result))
