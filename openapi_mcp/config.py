"""Server configuration: file (YAML/TOML) merged with CLI flags. Secrets only come from env vars."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .tools import ToolDef


@dataclass
class AuthConfig:
    type: str = "none"          # none | bearer | api_key
    env: str | None = None      # name of the env var holding the secret
    header: str | None = None   # api_key in a header (e.g. X-API-Key)
    query: str | None = None    # api_key in the query string (e.g. api_key)

    def secret(self) -> str | None:
        if self.type == "none":
            return None
        if not self.env:
            raise ValueError("auth.env must name the environment variable that holds the secret")
        value = os.environ.get(self.env)
        if not value:
            raise ValueError(f"environment variable {self.env} is not set")
        return value


@dataclass
class Config:
    spec: str = ""
    base_url: str | None = None
    allow_write: bool = False
    include: list[str] = field(default_factory=list)   # operationIds, tool names or "tag:<tag>"
    exclude: list[str] = field(default_factory=list)
    timeout: float = 30.0
    max_response_chars: int = 20_000
    auth: AuthConfig = field(default_factory=AuthConfig)
    server_name: str = "openapi-mcp"

    @classmethod
    def from_file(cls, path: str) -> "Config":
        p = Path(path)
        raw: dict[str, Any] = tomllib.loads(p.read_text()) if p.suffix == ".toml" else yaml.safe_load(p.read_text()) or {}
        auth = AuthConfig(**(raw.pop("auth", None) or {}))
        cfg = cls(**raw, auth=auth)
        if cfg.spec and not cfg.spec.startswith(("http://", "https://")) and not Path(cfg.spec).is_absolute():
            cfg.spec = str((p.parent / cfg.spec).resolve())
        return cfg

    def _matches(self, tool: ToolDef, rules: list[str]) -> bool:
        for rule in rules:
            if rule.startswith("tag:") and rule[4:] in tool.tags:
                return True
            if rule in (tool.name, tool.operation_id):
                return True
        return False

    def select(self, tools: list[ToolDef]) -> list[ToolDef]:
        """Apply read-only default, allowlist and denylist."""
        out = []
        for t in tools:
            if t.is_write and not self.allow_write:
                continue
            if self.include and not self._matches(t, self.include):
                continue
            if self._matches(t, self.exclude):
                continue
            out.append(t)
        return out
