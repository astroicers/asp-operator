import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class InboxWriteError(Exception):
    pass


def deduplicate(existing: List[Dict], new_tasks: List[Dict]) -> List[Dict]:
    existing_refs = {
        t.get("source", {}).get("ref")
        for t in existing
        if isinstance(t, dict) and t.get("source")
    } - {None}
    merged = list(existing)
    for task in new_tasks:
        if task["source"]["ref"] not in existing_refs:
            merged.append(task)
            existing_refs.add(task["source"]["ref"])
    return merged


def _try_update(repo, path: str, merged: List, sha: str, retries: int = 1) -> None:
    """Update file with retry on 409 Conflict (re-fetch SHA and merge again)."""
    for attempt in range(retries + 1):
        try:
            repo.update_file(
                path=path,
                message="chore(inbox): update asp-task-inbox via asp-operator",
                content=json.dumps(merged, indent=2),
                sha=sha,
            )
            return
        except Exception as e:
            if "409" in str(e) and attempt < retries:
                # Re-fetch latest state and re-merge
                content_file = repo.get_contents(path)
                existing = json.loads(content_file.decoded_content)
                merged = deduplicate(existing, merged)
                sha = content_file.sha
            else:
                raise InboxWriteError("Failed to write inbox to GitHub") from e


def write_inbox(repo, path: str, tasks: List[Dict[str, Any]]) -> None:
    try:
        content_file = repo.get_contents(path)
        existing = json.loads(content_file.decoded_content)
        merged = deduplicate(existing, tasks)
        if len(merged) == len(existing):
            return
        _try_update(repo, path, merged, content_file.sha)
    except InboxWriteError:
        raise
    except Exception as e:
        if "404" in str(e):
            merged = deduplicate([], tasks)
            repo.create_file(
                path=path,
                message="chore(inbox): create asp-task-inbox via asp-operator",
                content=json.dumps(merged, indent=2),
            )
        else:
            raise InboxWriteError("Failed to write inbox to GitHub") from e
