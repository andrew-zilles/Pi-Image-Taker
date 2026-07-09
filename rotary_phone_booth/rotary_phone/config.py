from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.local.yaml"


@dataclass
class Config:
    raw: dict

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        path = path or DEFAULT_CONFIG_PATH
        if not path.exists():
            raise FileNotFoundError(
                f"{path} not found. Copy config.example.yaml to config.local.yaml and edit it."
            )
        with open(path) as f:
            return cls(raw=yaml.safe_load(f))

    def __getitem__(self, key):
        return self.raw[key]

    @property
    def smtp_app_password(self) -> str:
        password = os.environ.get("SMTP_APP_PASSWORD")
        if not password:
            raise RuntimeError(
                "Set the SMTP_APP_PASSWORD environment variable (a Gmail app password, not your login password)."
            )
        return password
