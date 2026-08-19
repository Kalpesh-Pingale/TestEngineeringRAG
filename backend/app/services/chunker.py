import hashlib
import logging
import re
from typing import List

from app.config import settings
from app.models.jira import JiraIssue, JiraIssueChunk

logger = logging.getLogger(__name__)


class TextChunker:
    """Splits Jira issues into overlapping semantic chunks for embedding."""

    def __init__(
        self, chunk_size: int = 0, chunk_overlap: int = 0
    ):
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap

    def chunk_text(self, text: str, base_metadata: dict) -> List[JiraIssueChunk]:
        if not text.strip():
            return []

        chunks: List[JiraIssueChunk] = []
        sentences = re.split(r"(?<=[.!?])\s+", text)
        current_chunk = ""
        chunk_index = 0

        for sentence in sentences:
            if (
                len(current_chunk) + len(sentence)
                <= self.chunk_size
            ):
                current_chunk += sentence + " "
            else:
                if current_chunk.strip():
                    chunk_id = hashlib.md5(
                        f"{base_metadata.get('issue_key', '')}_{chunk_index}".encode()
                    ).hexdigest()
                    chunks.append(
                        JiraIssueChunk(
                            chunk_id=chunk_id,
                            issue_key=base_metadata.get("issue_key", ""),
                            project_key=base_metadata.get("project_key", ""),
                            issue_type=base_metadata.get("issue_type", ""),
                            content=current_chunk.strip(),
                            chunk_index=chunk_index,
                            metadata={
                                **base_metadata,
                                "chunk_index": chunk_index,
                            },
                        )
                    )
                    chunk_index += 1
                    # Overlap: keep last N chars for context
                    overlap_text = current_chunk[-self.chunk_overlap :] if self.chunk_overlap > 0 else ""
                    current_chunk = overlap_text + sentence + " "

                else:
                    current_chunk = sentence + " "

        if current_chunk.strip():
            chunk_id = hashlib.md5(
                f"{base_metadata.get('issue_key', '')}_{chunk_index}".encode()
            ).hexdigest()
            chunks.append(
                JiraIssueChunk(
                    chunk_id=chunk_id,
                    issue_key=base_metadata.get("issue_key", ""),
                    project_key=base_metadata.get("project_key", ""),
                    issue_type=base_metadata.get("issue_type", ""),
                    content=current_chunk.strip(),
                    chunk_index=chunk_index,
                    metadata={
                        **base_metadata,
                        "chunk_index": chunk_index,
                    },
                )
            )

        return chunks

    def chunk_issue(self, issue: JiraIssue) -> List[JiraIssueChunk]:
        base_meta = {
            "issue_key": issue.issue_key,
            "project_key": issue.project_key,
            "issue_type": issue.issue_type,
            "summary": issue.summary,
            "priority": issue.priority or "",
            "status": issue.status or "",
            "labels": ",".join(issue.labels),
            "components": ",".join(issue.components),
            "updated_date": issue.updated_date or "",
            "raw_fetch_tokens": issue.raw_fetch_tokens,
        }

        # Build comprehensive text from issue fields
        text_parts = [
            f"Summary: {issue.summary}",
        ]
        if issue.description:
            text_parts.append(f"Description: {issue.description}")
        if issue.acceptance_criteria:
            text_parts.append(
                f"Acceptance Criteria: {issue.acceptance_criteria}"
            )
        if issue.comments:
            text_parts.append(f"Comments: {' | '.join(issue.comments)}")

        full_text = "\n\n".join(text_parts)
        return self.chunk_text(full_text, base_meta)
