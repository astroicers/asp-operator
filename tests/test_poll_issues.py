import pytest
from unittest.mock import MagicMock, patch, call
from src.poll_issues import poll_repo, filter_issues, build_github_client


LABEL_FILTER = ["ready-for-agent"]

PRIORITY_MAP = {"P0": ["critical", "urgent"], "P1": ["high"], "P2": ["medium"], "P3": ["low"]}
SLA_MAP = {"P0": 0, "P1": 24, "P2": 72, "P3": 168}


def _make_issue(number, title, labels, html_url=None):
    issue = MagicMock()
    issue.number = number
    issue.title = title
    issue.body = "some body"
    issue.html_url = html_url or f"https://github.com/org/repo/issues/{number}"
    issue.labels = [MagicMock(name=l) for l in labels]
    for i, label_name in enumerate(labels):
        issue.labels[i].name = label_name
    issue.get_labels = MagicMock(return_value=issue.labels)
    return issue


def _make_repo(name="org/repo", issues=None, has_profile=True):
    repo = MagicMock()
    repo.full_name = name
    repo.get_issues.return_value = issues or []

    if has_profile:
        profile_file = MagicMock()
        profile_file.decoded_content = b"operator:\n  enabled: true\n  label_filter: []\n"
        repo.get_contents.side_effect = lambda path: (
            profile_file if path == ".ai_profile" else MagicMock()
        )
    else:
        repo.get_contents.side_effect = Exception("404 Not Found")

    return repo


# ── filter_issues ─────────────────────────────────────────────────────────────

def test_filter_issues_returns_matching():
    issues = [
        _make_issue(1, "Bug A", ["ready-for-agent", "bug"]),
        _make_issue(2, "Feature B", ["enhancement"]),
    ]
    result = filter_issues(issues, LABEL_FILTER)
    assert len(result) == 1
    assert result[0].number == 1


def test_filter_issues_empty_filter_returns_all():
    issues = [
        _make_issue(1, "Bug A", ["bug"]),
        _make_issue(2, "Feature B", ["enhancement"]),
    ]
    result = filter_issues(issues, [])
    assert len(result) == 2


def test_filter_issues_no_match_returns_empty():
    issues = [_make_issue(1, "Bug A", ["bug"])]
    result = filter_issues(issues, LABEL_FILTER)
    assert result == []


def test_filter_issues_empty_issues():
    result = filter_issues([], LABEL_FILTER)
    assert result == []


# ── poll_repo ─────────────────────────────────────────────────────────────────

def test_poll_repo_writes_inbox_for_matching_issues():
    issue = _make_issue(42, "Crash", ["ready-for-agent", "bug"])
    repo = _make_repo(issues=[issue])

    with patch("src.poll_issues.write_inbox") as mock_write, \
         patch("src.poll_issues.translate_issue") as mock_translate:
        mock_translate.return_value = {
            "id": "INBOX-042",
            "title": "Crash",
            "status": "pending",
            "source": {"ref": issue.html_url, "type": "github_issue"},
        }
        poll_repo(repo, ".asp-task-inbox.json", LABEL_FILTER, PRIORITY_MAP, SLA_MAP)
        mock_write.assert_called_once()


def test_poll_repo_skips_repo_without_profile():
    repo = _make_repo(has_profile=False)
    with patch("src.poll_issues.write_inbox") as mock_write:
        poll_repo(repo, ".asp-task-inbox.json", LABEL_FILTER, PRIORITY_MAP, SLA_MAP)
        mock_write.assert_not_called()


def test_poll_repo_skips_repo_with_operator_disabled():
    repo = _make_repo()
    profile_file = MagicMock()
    profile_file.decoded_content = b"operator:\n  enabled: false\n"
    repo.get_contents.side_effect = lambda path: (
        profile_file if path == ".ai_profile" else MagicMock()
    )

    with patch("src.poll_issues.write_inbox") as mock_write:
        poll_repo(repo, ".asp-task-inbox.json", LABEL_FILTER, PRIORITY_MAP, SLA_MAP)
        mock_write.assert_not_called()


def test_poll_repo_no_matching_issues_does_not_write():
    issue = _make_issue(1, "Unlabelled", ["bug"])  # no ready-for-agent
    repo = _make_repo(issues=[issue])

    with patch("src.poll_issues.write_inbox") as mock_write:
        poll_repo(repo, ".asp-task-inbox.json", LABEL_FILTER, PRIORITY_MAP, SLA_MAP)
        mock_write.assert_not_called()


def test_poll_repo_uses_profile_label_filter_override():
    repo = _make_repo()
    profile_file = MagicMock()
    profile_file.decoded_content = b"operator:\n  enabled: true\n  label_filter: [bug]\n"
    repo.get_contents.side_effect = lambda path: (
        profile_file if path == ".ai_profile" else MagicMock()
    )

    issue = _make_issue(1, "Bug only", ["bug"])
    repo.get_issues.return_value = [issue]

    with patch("src.poll_issues.write_inbox") as mock_write, \
         patch("src.poll_issues.translate_issue") as mock_translate:
        mock_translate.return_value = {
            "id": "INBOX-001", "title": "Bug only", "status": "pending",
            "source": {"ref": issue.html_url, "type": "github_issue"},
        }
        poll_repo(repo, ".asp-task-inbox.json", LABEL_FILTER, PRIORITY_MAP, SLA_MAP)
        mock_write.assert_called_once()
