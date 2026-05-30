import json
from typing import List, Dict, Any


class InboxWriteError(Exception):
    pass


def deduplicate(existing: List[Dict], new_tasks: List[Dict]) -> List[Dict]:
    existing_refs = {t["source"]["ref"] for t in existing}
    merged = list(existing)
    for task in new_tasks:
        if task["source"]["ref"] not in existing_refs:
            merged.append(task)
            existing_refs.add(task["source"]["ref"])
    return merged


def write_inbox(repo, path: str, tasks: List[Dict[str, Any]]) -> None:
    try:
        content_file = repo.get_contents(path)
        existing = json.loads(content_file.decoded_content)
        merged = deduplicate(existing, tasks)
        if len(merged) == len(existing):
            return
        repo.update_file(
            path=path,
            message="chore(inbox): update asp-task-inbox via asp-operator",
            content=json.dumps(merged, indent=2),
            sha=content_file.sha,
        )
    except Exception as e:
        if "404" in str(e):
            merged = deduplicate([], tasks)
            repo.create_file(
                path=path,
                message="chore(inbox): create asp-task-inbox via asp-operator",
                content=json.dumps(merged, indent=2),
            )
        else:
            raise InboxWriteError(f"Failed to write inbox: {e}") from e
