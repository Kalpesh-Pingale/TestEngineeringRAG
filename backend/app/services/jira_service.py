import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

from app.config import settings
from app.models.jira import JiraIssue
from app.services.mcp_client import MCPClient

logger = logging.getLogger(__name__)


class JiraService:
    """Service for fetching and transforming Jira issues."""

    def __init__(self, mcp_client: Optional[MCPClient] = None):
        self.mcp_client = mcp_client or MCPClient(
            base_url=settings.jira_mcp_server,
            server_type="jira",
        )

    @staticmethod
    def _extract_text_from_adf(adf) -> str:
        """Extract plain text from Atlassian Document Format."""
        if isinstance(adf, str):
            return adf
        if not isinstance(adf, dict):
            return str(adf or "")
        parts = []
        content = adf.get("content", [])
        for node in content:
            if node.get("type") == "paragraph":
                for inline in node.get("content", []):
                    if inline.get("type") == "text":
                        parts.append(inline.get("text", ""))
                parts.append("\n")
            elif node.get("type") == "bulletList":
                for item in node.get("content", []):
                    for sub in item.get("content", []):
                        if sub.get("type") == "paragraph":
                            for inline in sub.get("content", []):
                                if inline.get("type") == "text":
                                    parts.append("- " + inline.get("text", ""))
                            parts.append("\n")
            elif node.get("type") == "orderedList":
                for i, item in enumerate(node.get("content", []), 1):
                    for sub in item.get("content", []):
                        if sub.get("type") == "paragraph":
                            for inline in sub.get("content", []):
                                if inline.get("type") == "text":
                                    parts.append(f"{i}. " + inline.get("text", ""))
                            parts.append("\n")
        return "".join(parts).strip()

    @staticmethod
    def _extract_sprint_name(sprint_field) -> str:
        """Extract sprint name from various Jira API formats."""
        if isinstance(sprint_field, list):
            for s in sprint_field:
                if isinstance(s, dict) and s.get("name"):
                    return s["name"]
                if isinstance(s, str):
                    return s
            return ""
        if isinstance(sprint_field, dict):
            return sprint_field.get("name", "")
        return str(sprint_field) if sprint_field else ""

    def _parse_jira_issue(self, raw: Dict[str, Any]) -> JiraIssue:
        fields = raw.get("fields", raw)
        raw_desc = fields.get("description", "")
        description = self._extract_text_from_adf(raw_desc)
        raw_ac = fields.get("customfield_10016", "")
        acceptance_criteria = self._extract_text_from_adf(raw_ac) if raw_ac else ""
        # Rough token estimate (~4 chars/token) of the raw fetched payload, kept
        # for the tentative "vs a live fetch" savings comparison at generation time.
        raw_fetch_tokens = len(json.dumps(raw)) // 4
        return JiraIssue(
            issue_key=raw.get("key", raw.get("issue_key", "")),
            project_key=fields.get("project", {}).get("key", settings.jira_project_key),
            issue_type=fields.get("issuetype", {}).get("name", "Unknown"),
            summary=fields.get("summary", ""),
            description=description,
            acceptance_criteria=acceptance_criteria,
            priority=fields.get("priority", {}).get("name", "Medium"),
            status=fields.get("status", {}).get("name", ""),
            sprint=self._extract_sprint_name(fields.get("customfield_10020")),
            labels=fields.get("labels", []),
            components=[c.get("name", "") for c in fields.get("components", [])],
            story_points=fields.get("customfield_10014"),
            created_date=fields.get("created", ""),
            updated_date=fields.get("updated", ""),
            reporter=fields.get("reporter", {}).get("displayName", ""),
            assignee=fields.get("assignee", {}).get("displayName", "") if fields.get("assignee") else "",
            linked_issues=[],
            comments=[],
            raw_fetch_tokens=raw_fetch_tokens,
        )

    def compute_content_hash(self, issue: JiraIssue) -> str:
        content = f"{issue.summary}|{issue.description}|{issue.acceptance_criteria}|{issue.status}|{issue.priority}|{issue.story_points}|{issue.labels}|{issue.components}|{issue.assignee}|{issue.updated_date}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    async def fetch_all_issues(
        self,
        project_key: str = "",
        issue_types: Optional[List[str]] = None,
    ) -> List[JiraIssue]:
        pk = project_key or settings.jira_project_key
        it = issue_types or ["Story", "Bug"]
        logger.info(f"Fetching all {it} from Jira project {pk}")

        if settings.jira_use_mcp:
            raw_issues = await self.mcp_client.jira_get_project_issues(
                project_key=pk, issue_types=it
            )
        else:
            raw_issues = await self._fetch_via_rest(pk, it)

        parsed = [self._parse_jira_issue(iss) for iss in raw_issues]
        logger.info(f"Fetched {len(parsed)} issues from Jira")
        return parsed

    async def fetch_incremental_issues(
        self,
        last_sync_time: str,
        project_key: str = "",
        issue_types: Optional[List[str]] = None,
    ) -> List[JiraIssue]:
        pk = project_key or settings.jira_project_key
        it = issue_types or ["Story", "Bug"]
        logger.info(
            f"Fetching incremental issues for {pk} since {last_sync_time}"
        )

        if settings.jira_use_mcp:
            raw_issues = await self.mcp_client.jira_get_incremental_issues(
                project_key=pk,
                last_sync_time=last_sync_time,
                issue_types=it,
            )
        else:
            raw_issues = await self._fetch_via_rest_incremental(
                pk, it, last_sync_time
            )

        parsed = [self._parse_jira_issue(iss) for iss in raw_issues]
        logger.info(f"Fetched {len(parsed)} incremental issues")
        return parsed

    async def _fetch_via_rest(self, project_key: str, issue_types: List[str]) -> List[Dict]:
        import aiohttp
        from aiohttp import BasicAuth

        types_str = ", ".join(f'"{t}"' for t in issue_types)
        jql = f'project = {project_key} AND issuetype in ({types_str}) ORDER BY created DESC'
        url = f"{settings.jira_base_url}/rest/api/3/search/jql"

        auth = BasicAuth(settings.jira_email, settings.jira_api_token)
        all_issues = []
        start_at = 0
        max_results = 100

        async with aiohttp.ClientSession() as session:
            while True:
                params = {
                    "jql": jql,
                    "startAt": start_at,
                    "maxResults": max_results,
                    "fields": "*all",
                }
                async with session.get(
                    url, auth=auth, params=params
                ) as resp:
                    if resp.status != 200:
                        data = await resp.json()
                        err = data.get("errorMessages", data)
                        logger.error(f"Jira API error {resp.status}: {err}")
                        return []
                    data = await resp.json()
                    issues = data.get("issues", [])
                    all_issues.extend(issues)
                    if data.get("isLast", True):
                        break
                    start_at += max_results

        return all_issues

    async def _fetch_via_rest_incremental(
        self,
        project_key: str,
        issue_types: List[str],
        last_sync_time: str,
    ) -> List[Dict]:
        import aiohttp
        from aiohttp import BasicAuth
        from datetime import datetime, timezone, timedelta

        types_str = ", ".join(f'"{t}"' for t in issue_types)
        # Convert UTC timestamp to local Jira timezone (IST = UTC+5:30)
        # Jira JQL interprets bare timestamps in the server local timezone
        try:
            utc_dt = datetime.fromisoformat(last_sync_time.replace("Z", "+00:00"))
            local_dt = utc_dt.astimezone(timezone(timedelta(hours=5, minutes=30)))
            # Subtract 1 minute buffer to avoid timezone boundary misses
            local_dt = local_dt - timedelta(minutes=1)
            local_time = local_dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            # Fallback: strip problematic chars
            local_time = last_sync_time.split(".")[0].replace("T", " ")[:19]
        jql = f'project = {project_key} AND issuetype in ({types_str}) AND updated >= "{local_time}" ORDER BY updated DESC'
        logger.info(f"Incremental JQL: {jql}")
        url = f"{settings.jira_base_url}/rest/api/3/search/jql"

        auth = BasicAuth(settings.jira_email, settings.jira_api_token)
        all_issues = []
        start_at = 0
        max_results = 100

        async with aiohttp.ClientSession() as session:
            while True:
                params = {
                    "jql": jql,
                    "startAt": start_at,
                    "maxResults": max_results,
                    "fields": "*all",
                }
                async with session.get(
                    url, auth=auth, params=params
                ) as resp:
                    if resp.status != 200:
                        data = await resp.json()
                        err = data.get("errorMessages", data)
                        logger.warning(f"Jira incremental API error {resp.status}: {err}, falling back to full fetch")
                        return []
                    data = await resp.json()
                    issues = data.get("issues", [])
                    all_issues.extend(issues)
                    if data.get("isLast", True):
                        break
                    start_at += max_results

        return all_issues
