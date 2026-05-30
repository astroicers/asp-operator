import logging
import os
import yaml
from github import Github
from typing import List, Dict, Any

from src.config_loader import load_config
from src.task_translator import translate_issue
from src.inbox_writer import write_inbox

logger = logging.getLogger(__name__)


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
    except Exception as exc:
        logger.warning("Could not load .ai_profile for %s: %s", repo.full_name, type(exc).__name__)
        return {}


def _translate_safe(issue_obj, priority_map, sla_hours_map):
    try:
        return translate_issue(
            {
                "number": issue_obj.number,
                "title": issue_obj.title,
                "body": issue_obj.body,
                "html_url": issue_obj.html_url,
                "labels": [{"name": l.name} for l in issue_obj.labels],
            },
            priority_map,
            sla_hours_map,
        )
    except (KeyError, ValueError) as exc:
        logger.warning("Skipping issue #%s: translation error %s", getattr(issue_obj, "number", "?"), exc)
        return None


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

    tasks = [t for t in (
        _translate_safe(i, priority_map, sla_hours_map) for i in matched
    ) if t is not None]

    if not tasks:
        return

    write_inbox(repo, inbox_path, tasks)


def main():
    config_path = os.path.join(os.path.dirname(__file__), "..", "operator-config.yaml")
    config = load_config(config_path)
    token = config.get_token()
    gh = build_github_client(token)

    for owner in config.authorized_owners:
        try:
            repos = gh.get_user(owner).get_repos()
        except Exception as exc:
            logger.error("Cannot fetch repos for owner %s: %s", owner, type(exc).__name__)
            continue
        for repo in repos:
            try:
                poll_repo(
                    repo,
                    ".asp-task-inbox.json",
                    config.defaults.label_filter,
                    config.defaults.priority_map,
                    config.defaults.sla_hours_map,
                )
            except Exception as exc:
                logger.error("poll_repo failed for %s: %s", repo.full_name, type(exc).__name__)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
