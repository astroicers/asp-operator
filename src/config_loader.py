import os
import yaml
from dataclasses import dataclass, field
from typing import List, Dict


class ConfigError(Exception):
    pass


@dataclass
class Defaults:
    label_filter: List[str]
    priority_map: Dict[str, List[str]]
    sla_hours_map: Dict[str, int]


@dataclass
class Config:
    authorized_owners: List[str]
    github_token_env: str
    defaults: Defaults

    def get_token(self) -> str:
        token = os.environ.get(self.github_token_env)
        if not token:
            raise ConfigError(
                f"{self.github_token_env} environment variable not set"
            )
        return token


def load_config(path: str) -> Config:
    if not os.path.exists(path):
        raise ConfigError(f"Config file not found: {path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    owners = data.get("authorized_owners")
    if not isinstance(owners, list) or not owners:
        raise ConfigError("authorized_owners must be a non-empty list")

    defaults_data = data.get("defaults", {})
    defaults = Defaults(
        label_filter=defaults_data.get("label_filter", ["ready-for-agent"]),
        priority_map=defaults_data.get("priority_map", {}),
        sla_hours_map=defaults_data.get("sla_hours_map", {"P0": 0, "P1": 24, "P2": 72, "P3": 168}),
    )

    return Config(
        authorized_owners=owners,
        github_token_env=data.get("github_token_env", "OPERATOR_GITHUB_TOKEN"),
        defaults=defaults,
    )
