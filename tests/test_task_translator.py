import json
import pytest
from pathlib import Path
from src.task_translator import translate_issue, classify_type, map_priority, map_sla


FIXTURES = Path(__file__).parent / "fixtures"


def load_issue():
    return json.loads((FIXTURES / "sample_issue.json").read_text())


def default_priority_map():
    return {"P0": ["critical", "urgent"], "P1": ["high"], "P2": ["medium"], "P3": ["low"]}


def default_sla_map():
    return {"P0": 0, "P1": 24, "P2": 72, "P3": 168}


# ── classify_type ─────────────────────────────────────────────────────────────

def test_classify_type_bug_label():
    issue = {"labels": [{"name": "bug"}], "title": "something broken", "body": ""}
    assert classify_type(issue) == "BUGFIX"


def test_classify_type_feature_label():
    issue = {"labels": [{"name": "enhancement"}], "title": "add dark mode", "body": ""}
    assert classify_type(issue) == "NEW_FEATURE"


def test_classify_type_title_keyword_fix():
    issue = {"labels": [], "title": "fix login timeout", "body": ""}
    assert classify_type(issue) == "BUGFIX"


def test_classify_type_title_keyword_feat():
    issue = {"labels": [], "title": "add export feature", "body": ""}
    assert classify_type(issue) == "NEW_FEATURE"


def test_classify_type_default_general():
    issue = {"labels": [], "title": "some question", "body": ""}
    assert classify_type(issue) == "GENERAL"


# ── map_priority ──────────────────────────────────────────────────────────────

def test_map_priority_high_label():
    labels = ["bug", "high"]
    assert map_priority(labels, default_priority_map()) == "P1"


def test_map_priority_critical_label():
    labels = ["critical"]
    assert map_priority(labels, default_priority_map()) == "P0"


def test_map_priority_no_match_defaults_p2():
    labels = ["documentation"]
    assert map_priority(labels, default_priority_map()) == "P2"


# ── map_sla ───────────────────────────────────────────────────────────────────

def test_map_sla_p0():
    assert map_sla("P0", default_sla_map()) == 0


def test_map_sla_p1():
    assert map_sla("P1", default_sla_map()) == 24


def test_map_sla_unknown_defaults_168():
    assert map_sla("P9", default_sla_map()) == 168


# ── translate_issue ───────────────────────────────────────────────────────────

def test_translate_issue_id_format():
    issue = load_issue()
    task = translate_issue(issue, default_priority_map(), default_sla_map())
    assert task["id"] == "INBOX-042"


def test_translate_issue_title():
    issue = load_issue()
    task = translate_issue(issue, default_priority_map(), default_sla_map())
    assert task["title"] == issue["title"]


def test_translate_issue_status_pending():
    issue = load_issue()
    task = translate_issue(issue, default_priority_map(), default_sla_map())
    assert task["status"] == "pending"


def test_translate_issue_source_ref():
    issue = load_issue()
    task = translate_issue(issue, default_priority_map(), default_sla_map())
    assert task["source"]["ref"] == issue["html_url"]
    assert task["source"]["type"] == "github_issue"


def test_translate_issue_description_truncated():
    issue = {**load_issue(), "body": "x" * 600}
    task = translate_issue(issue, default_priority_map(), default_sla_map())
    assert len(task["description"]) <= 500


def test_translate_issue_description_none_body():
    issue = {**load_issue(), "body": None}
    task = translate_issue(issue, default_priority_map(), default_sla_map())
    assert task["description"] == ""


def test_translate_issue_required_keys():
    issue = load_issue()
    task = translate_issue(issue, default_priority_map(), default_sla_map())
    for key in ["id", "title", "type", "priority", "status", "sla_hours", "source", "triggered_by", "description"]:
        assert key in task, f"Missing key: {key}"
