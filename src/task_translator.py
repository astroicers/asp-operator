from datetime import datetime, timezone
from typing import Any, Dict, List


def classify_type(issue: Dict) -> str:
    label_names = [l["name"].lower() for l in (issue.get("labels") or [])]
    title = (issue.get("title") or "").lower()

    if "bug" in label_names or any(kw in title for kw in ["fix", "bug", "crash", "error", "broken"]):
        return "BUGFIX"
    if "enhancement" in label_names or "feature" in label_names or any(kw in title for kw in ["add", "feat", "new", "implement"]):
        return "NEW_FEATURE"
    return "GENERAL"


def map_priority(labels: List[str], priority_map: Dict[str, List[str]]) -> str:
    label_set = {l.lower() for l in labels}
    for priority in ["P0", "P1", "P2", "P3"]:
        keywords = [k.lower() for k in priority_map.get(priority, [])]
        if label_set & set(keywords):
            return priority
    return "P2"


def map_sla(priority: str, sla_hours_map: Dict[str, int]) -> int:
    return sla_hours_map.get(priority, 168)


def translate_issue(
    issue: Dict,
    priority_map: Dict[str, List[str]],
    sla_hours_map: Dict[str, int],
) -> Dict[str, Any]:
    number = issue["number"]
    label_names = [l["name"] for l in (issue.get("labels") or [])]
    priority = map_priority(label_names, priority_map)
    body = issue.get("body") or ""

    return {
        "id": f"INBOX-{number}",
        "title": issue["title"],
        "type": classify_type(issue),
        "priority": priority,
        "status": "pending",
        "sla_hours": map_sla(priority, sla_hours_map),
        "source": {
            "type": "github_issue",
            "ref": issue["html_url"],
            "imported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "triggered_by": "customer",
        "description": body[:500],
    }
