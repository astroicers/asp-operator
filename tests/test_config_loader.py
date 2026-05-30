import pytest
import os
import tempfile
import yaml
from src.config_loader import load_config, ConfigError


MINIMAL_CONFIG = {
    "version": "1.0",
    "authorized_owners": ["astroicers"],
    "github_token_env": "OPERATOR_GITHUB_TOKEN",
    "defaults": {
        "label_filter": ["ready-for-agent"],
        "priority_map": {"P0": ["critical"], "P1": ["high"], "P2": ["medium"], "P3": ["low"]},
        "sla_hours_map": {"P0": 0, "P1": 24, "P2": 72, "P3": 168},
    },
}


def write_config(tmp_path, data):
    p = tmp_path / "operator-config.yaml"
    p.write_text(yaml.dump(data))
    return str(p)


def test_load_config_returns_authorized_owners(tmp_path):
    path = write_config(tmp_path, MINIMAL_CONFIG)
    cfg = load_config(path)
    assert cfg.authorized_owners == ["astroicers"]


def test_load_config_returns_defaults(tmp_path):
    path = write_config(tmp_path, MINIMAL_CONFIG)
    cfg = load_config(path)
    assert cfg.defaults.label_filter == ["ready-for-agent"]
    assert cfg.defaults.sla_hours_map["P0"] == 0
    assert cfg.defaults.sla_hours_map["P3"] == 168


def test_load_config_returns_github_token_env(tmp_path):
    path = write_config(tmp_path, MINIMAL_CONFIG)
    cfg = load_config(path)
    assert cfg.github_token_env == "OPERATOR_GITHUB_TOKEN"


def test_load_config_missing_file_raises():
    with pytest.raises(ConfigError, match="not found"):
        load_config("/nonexistent/path.yaml")


def test_load_config_missing_authorized_owners_raises(tmp_path):
    bad = {k: v for k, v in MINIMAL_CONFIG.items() if k != "authorized_owners"}
    path = write_config(tmp_path, bad)
    with pytest.raises(ConfigError, match="authorized_owners"):
        load_config(path)


def test_load_config_empty_authorized_owners_raises(tmp_path):
    bad = {**MINIMAL_CONFIG, "authorized_owners": []}
    path = write_config(tmp_path, bad)
    with pytest.raises(ConfigError, match="authorized_owners"):
        load_config(path)


def test_load_config_authorized_owners_string_raises(tmp_path):
    bad = {**MINIMAL_CONFIG, "authorized_owners": "astroicers"}
    path = write_config(tmp_path, bad)
    with pytest.raises(ConfigError, match="authorized_owners"):
        load_config(path)


def test_get_token_from_env(tmp_path, monkeypatch):
    path = write_config(tmp_path, MINIMAL_CONFIG)
    monkeypatch.setenv("OPERATOR_GITHUB_TOKEN", "ghp_test123")
    cfg = load_config(path)
    assert cfg.get_token() == "ghp_test123"


def test_get_token_missing_env_raises(tmp_path, monkeypatch):
    path = write_config(tmp_path, MINIMAL_CONFIG)
    monkeypatch.delenv("OPERATOR_GITHUB_TOKEN", raising=False)
    cfg = load_config(path)
    with pytest.raises(ConfigError, match="OPERATOR_GITHUB_TOKEN"):
        cfg.get_token()
