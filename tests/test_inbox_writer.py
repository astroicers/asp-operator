import json
import pytest
from unittest.mock import MagicMock, patch, call
from src.inbox_writer import write_inbox, deduplicate, InboxWriteError


EXISTING_TASKS = [
    {
        "id": "INBOX-001",
        "title": "Old bug",
        "status": "pending",
        "source": {"ref": "https://github.com/org/repo/issues/1", "type": "github_issue"},
    }
]

NEW_TASK = {
    "id": "INBOX-42",
    "title": "New crash",
    "status": "pending",
    "source": {"ref": "https://github.com/org/repo/issues/42", "type": "github_issue"},
}

DUPLICATE_TASK = {
    "id": "INBOX-001",
    "title": "Old bug again",
    "status": "pending",
    "source": {"ref": "https://github.com/org/repo/issues/1", "type": "github_issue"},
}


# ── deduplicate ───────────────────────────────────────────────────────────────

def test_deduplicate_keeps_new_task():
    result = deduplicate(EXISTING_TASKS, [NEW_TASK])
    refs = [t["source"]["ref"] for t in result]
    assert "https://github.com/org/repo/issues/42" in refs


def test_deduplicate_removes_duplicate():
    result = deduplicate(EXISTING_TASKS, [DUPLICATE_TASK])
    assert len(result) == len(EXISTING_TASKS)


def test_deduplicate_preserves_existing():
    result = deduplicate(EXISTING_TASKS, [NEW_TASK])
    refs = [t["source"]["ref"] for t in result]
    assert "https://github.com/org/repo/issues/1" in refs


def test_deduplicate_multiple_new_tasks():
    new_tasks = [NEW_TASK, DUPLICATE_TASK]
    result = deduplicate(EXISTING_TASKS, new_tasks)
    assert len(result) == 2  # 1 existing + 1 genuinely new


def test_deduplicate_empty_existing():
    result = deduplicate([], [NEW_TASK])
    assert len(result) == 1


def test_deduplicate_empty_new():
    result = deduplicate(EXISTING_TASKS, [])
    assert result == EXISTING_TASKS


# ── write_inbox (GitHub API) ──────────────────────────────────────────────────

def _make_mock_repo(existing_content=None):
    repo = MagicMock()
    if existing_content is None:
        # File does not exist
        repo.get_contents.side_effect = Exception("404 Not Found")
    else:
        content_file = MagicMock()
        content_file.decoded_content = json.dumps(existing_content).encode()
        content_file.sha = "abc123"
        repo.get_contents.return_value = content_file
    return repo


def test_write_inbox_creates_file_when_not_exists():
    repo = _make_mock_repo(existing_content=None)
    write_inbox(repo, ".asp-task-inbox.json", [NEW_TASK])
    repo.create_file.assert_called_once()
    args, kwargs = repo.create_file.call_args
    written = json.loads(kwargs["content"])
    assert written[0]["id"] == "INBOX-42"


def test_write_inbox_updates_file_when_exists():
    repo = _make_mock_repo(existing_content=EXISTING_TASKS)
    write_inbox(repo, ".asp-task-inbox.json", [NEW_TASK])
    repo.update_file.assert_called_once()
    args, kwargs = repo.update_file.call_args
    written = json.loads(kwargs["content"])
    refs = [t["source"]["ref"] for t in written]
    assert "https://github.com/org/repo/issues/42" in refs
    assert "https://github.com/org/repo/issues/1" in refs


def test_write_inbox_skips_commit_when_no_new_tasks():
    repo = _make_mock_repo(existing_content=EXISTING_TASKS)
    write_inbox(repo, ".asp-task-inbox.json", [DUPLICATE_TASK])
    repo.create_file.assert_not_called()
    repo.update_file.assert_not_called()


def test_write_inbox_commit_message_format():
    repo = _make_mock_repo(existing_content=None)
    write_inbox(repo, ".asp-task-inbox.json", [NEW_TASK])
    _, kwargs = repo.create_file.call_args
    assert kwargs["message"] == "chore(inbox): create asp-task-inbox via asp-operator"
