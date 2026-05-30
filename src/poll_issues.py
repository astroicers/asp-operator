import os
import yaml
from github import Github
from typing import List, Dict, Any

from src.config_loader import load_config
from src.task_translator import translate_issue
from src.inbox_writer import write_inbox


def build_github_client(token: str) -> Github:
    return Github(token)


def filter_issues(issues: list, label_filter: List[str]) -> list:
    if not label_filter:
        return list(issues)
    return [
        issue for issue in issues
        if any(l.name in label_filter for l in issue.labels)
    ]


def _get_profile(repo) -> Dict:
    try:
        content = repo.get_contents(".ai_profile")
        return yaml.safe_load(content.decoded_content) or {}
    except Exception:
        return {}


def poll_repo(
    repo,
    inbox_path: str,
    default_label_filter: List[str],
    priority_map: Dict[str, List[str]],
    sla_hours_map: Dict[str, int],
) -> None:
    profile = _get_profile(repo)
    operator_cfg = profile.get("operator", {})

    if not operator_cfg.get("enabled", False):
        return

    label_filter = operator_cfg.get("label_filter") or default_label_filter

    open_issues = repo.get_issues(state="open")
    matched = filter_issues(open_issues, label_filter)

    if not matched:
        return

    tasks = [translate_issue(
        {
            "number": i.number,
            "title": i.title,
            "body": i.body,
            "html_url": i.html_url,
            "labels": [{"name": l.name} for l in i.labels],
        },
        priority_map,
        sla_hours_map,
    ) for i in matched]

    write_inbox(repo, inbox_path, tasks)


def main():
    config_path = os.path.join(os.path.dirname(__file__), "..", "operator-config.yaml")
    config = load_config(config_path)
    token = config.get_token()
    gh = build_github_client(token)

    for owner in config.authorized_owners:
        for repo in gh.get_user(owner).get_repos():
            poll_repo(
                repo,
                ".asp-task-inbox.json",
                config.defaults.label_filter,
                config.defaults.priority_map,
                config.defaults.sla_hours_map,
            )


if __name__ == "__main__":
    main()
