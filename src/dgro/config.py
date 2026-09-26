"""Application settings, read from environment variables and an optional `.env` file."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="DGRO_", extra="ignore")

    # --- AI -----------------------------------------------------------------------------------
    # "auto" uses Claude when an API key is configured and falls back to offline demo mode otherwise.
    llm: Literal["auto", "anthropic", "fake"] = "auto"
    model: str = "claude-opus-5"
    anthropic_api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("ANTHROPIC_API_KEY", "DGRO_ANTHROPIC_API_KEY")
    )
    # Server-side retry on another model when a request is declined by safety classifiers.
    refusal_fallback: bool = True
    llm_timeout_seconds: float = 600.0
    web_search_max_uses: int = 6
    max_vendors: int = 8

    # --- Storage & server ---------------------------------------------------------------------
    data_dir: Path = Path("data")
    host: str = "127.0.0.1"
    port: int = 8000
    workers: int = 2
    log_level: str = "INFO"

    # --- Requester defaults (who the vendor emails come from) -----------------------------------
    requester_name: str = ""
    requester_email: str = ""
    requester_phone: str = ""
    requester_company: str = ""

    # --- Email ----------------------------------------------------------------------------------
    # sandbox: nothing leaves your machine; vendor replies are simulated in the UI.
    # smtp: real sending over SMTP and reply collection over IMAP.
    email_mode: Literal["sandbox", "smtp"] = "sandbox"
    email_from: str = ""
    # Testing aid for smtp mode: deliver every outgoing email to this address instead of the vendor.
    email_redirect_to: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_security: Literal["starttls", "ssl", "none"] = "starttls"
    smtp_username: str = ""
    smtp_password: str = ""
    imap_host: str = ""
    imap_port: int = 993
    imap_username: str = ""
    imap_password: str = ""
    imap_folder: str = "INBOX"
    inbox_poll_seconds: int = 180
    send_delay_seconds: float = 2.0

    # --- Contact scraper ------------------------------------------------------------------------
    scrape_max_pages: int = 6
    scrape_timeout_seconds: float = 12.0
    scrape_allow_private_hosts: bool = False

    @property
    def db_path(self) -> Path:
        return self.data_dir / "dgro.db"

    @property
    def outbox_dir(self) -> Path:
        return self.data_dir / "outbox"

    @property
    def effective_llm(self) -> Literal["anthropic", "fake"]:
        if self.llm != "auto":
            return self.llm
        if self.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
            return "anthropic"
        return "fake"

    @property
    def sender_address(self) -> str:
        return self.email_from or self.smtp_username or self.requester_email

    @property
    def imap_user(self) -> str:
        return self.imap_username or self.smtp_username

    @property
    def imap_pass(self) -> str:
        return self.imap_password or self.smtp_password


@lru_cache
def get_settings() -> Settings:
    return Settings()
