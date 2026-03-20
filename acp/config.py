"""ACP global configuration — loaded from environment variables or .env file."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ACP_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Core ──────────────────────────────────────────────────────────────────
    env: Literal["development", "staging", "production"] = "development"
    # Stable local default so encrypted signing keys survive app restarts in demo/dev.
    secret_key: str = "acp-dev-secret-key-change-me"
    admin_token: str = "acp-demo-admin-token"  # bootstrap admin API token for local demo/dev

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./acp.db"

    # ── Proxy ─────────────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000

    # ── Upstream LLM endpoints ────────────────────────────────────────────────
    anthropic_base_url: str = "https://api.anthropic.com"
    openai_base_url: str = "https://api.openai.com"

    # ── Identity ──────────────────────────────────────────────────────────────
    jwt_algorithm: str = "RS256"
    jwt_default_expiry_hours: int = 24
    jwt_rotation_overlap_hours: int = 1
    revocation_cache_ttl_seconds: int = 60
    rsa_key_size: int = 2048

    # ── Policy ────────────────────────────────────────────────────────────────
    policy_eval_timeout_ms: int = 10
    policy_default_action: Literal["deny", "allow"] = "deny"

    # ── Approvals ─────────────────────────────────────────────────────────────
    approval_default_timeout_minutes: int = 30
    approval_default_timeout_action: Literal["deny", "approve", "escalate"] = "deny"
    slack_webhook_url: str = ""
    slack_bot_token: str = ""

    # ── Budget ────────────────────────────────────────────────────────────────
    budget_accounting_lag_seconds: int = 5

    # ── Observability ─────────────────────────────────────────────────────────
    trace_retention_days: int = 90
    pii_redaction_enabled: bool = False

    # ── Replay ────────────────────────────────────────────────────────────────
    replay_link_expiry_days: int = 7

    # ── Audit ─────────────────────────────────────────────────────────────────
    audit_retention_days: int = 2555  # ~7 years for enterprise compliance

    # ── Shadow agent detection ────────────────────────────────────────────────
    shadow_detection_window_minutes: int = 5

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def data_dir(self) -> Path:
        d = Path("./acp_data")
        d.mkdir(exist_ok=True)
        return d


settings = Settings()
