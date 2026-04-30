from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str = Field(..., alias="BOT_TOKEN")

    admin_user_ids: str = Field(default="", alias="ADMIN_USER_IDS")
    admin_usernames: str = Field(default="bear1berry", alias="ADMIN_USERNAMES")

    app_name: str = Field(default="Менеджер ИИ", alias="APP_NAME")
    env: Literal["dev", "prod"] = Field(default="dev", alias="ENV")
    timezone: str = Field(default="Europe/Moscow", alias="TIMEZONE")

    database_path: str = Field(default="data/manager_ai.sqlite3", alias="DATABASE_PATH")
    exports_dir: str = Field(default="exports", alias="EXPORTS_DIR")
    logs_dir: str = Field(default="logs", alias="LOGS_DIR")

    mini_app_url: str = Field(default="", alias="MINI_APP_URL")
    mini_app_api_enabled: bool = Field(default=True, alias="MINI_APP_API_ENABLED")
    mini_app_api_host: str = Field(default="127.0.0.1", alias="MINI_APP_API_HOST")
    mini_app_api_port: int = Field(default=8088, alias="MINI_APP_API_PORT")
    mini_app_auth_required: bool = Field(default=True, alias="MINI_APP_AUTH_REQUIRED")
    mini_app_cors_origins: str = Field(default="", alias="MINI_APP_CORS_ORIGINS")

    llm_base_url: str = Field(default="https://api.deepseek.com", alias="LLM_BASE_URL")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_model: str = Field(default="deepseek-chat", alias="LLM_MODEL")
    llm_fast_model: str = Field(default="deepseek-chat", alias="LLM_FAST_MODEL")
    llm_heavy_model: str = Field(default="deepseek-chat", alias="LLM_HEAVY_MODEL")
    llm_fallback_model: str = Field(default="deepseek-chat", alias="LLM_FALLBACK_MODEL")
    llm_timeout_seconds: int = Field(default=60, alias="LLM_TIMEOUT_SECONDS")

    web_search_enabled: bool = Field(default=False, alias="WEB_SEARCH_ENABLED")
    web_search_provider: Literal["tavily", "serper", "brave"] = Field(default="tavily", alias="WEB_SEARCH_PROVIDER")
    web_search_max_results: int = Field(default=5, alias="WEB_SEARCH_MAX_RESULTS")
    web_search_timeout_seconds: int = Field(default=20, alias="WEB_SEARCH_TIMEOUT_SECONDS")

    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")
    tavily_base_url: str = Field(default="https://api.tavily.com", alias="TAVILY_BASE_URL")

    serper_api_key: str = Field(default="", alias="SERPER_API_KEY")
    serper_base_url: str = Field(default="https://google.serper.dev", alias="SERPER_BASE_URL")

    brave_api_key: str = Field(default="", alias="BRAVE_API_KEY")
    brave_base_url: str = Field(default="https://api.search.brave.com", alias="BRAVE_BASE_URL")

    yandex_speechkit_api_key: str = Field(default="", alias="YANDEX_SPEECHKIT_API_KEY")
    yandex_speechkit_folder_id: str = Field(default="", alias="YANDEX_SPEECHKIT_FOLDER_ID")
    yandex_stt_language: str = Field(default="ru-RU", alias="YANDEX_STT_LANGUAGE")

    free_daily_text_limit: int = Field(default=20, alias="FREE_DAILY_TEXT_LIMIT")
    free_daily_voice_limit: int = Field(default=3, alias="FREE_DAILY_VOICE_LIMIT")

    pro_daily_text_limit: int = Field(default=300, alias="PRO_DAILY_TEXT_LIMIT")
    pro_daily_voice_limit: int = Field(default=50, alias="PRO_DAILY_VOICE_LIMIT")

    business_daily_text_limit: int = Field(default=1000, alias="BUSINESS_DAILY_TEXT_LIMIT")
    business_daily_voice_limit: int = Field(default=200, alias="BUSINESS_DAILY_VOICE_LIMIT")

    max_export_file_mb: int = Field(default=45, alias="MAX_EXPORT_FILE_MB")
    auto_backup_enabled: bool = Field(default=False, alias="AUTO_BACKUP_ENABLED")
    auto_backup_interval_hours: int = Field(default=24, alias="AUTO_BACKUP_INTERVAL_HOURS")
    auto_backup_keep_files: int = Field(default=30, alias="AUTO_BACKUP_KEEP_FILES")
    auto_backup_start_delay_seconds: int = Field(default=120, alias="AUTO_BACKUP_START_DELAY_SECONDS")
    pdf_font_path: str = Field(default="", alias="PDF_FONT_PATH")

    @property
    def admin_ids(self) -> set[int]:
        result: set[int] = set()
        for raw in self.admin_user_ids.split(","):
            raw = raw.strip()
            if raw.isdigit():
                result.add(int(raw))
        return result

    @property
    def admin_names(self) -> set[str]:
        result: set[str] = set()
        for raw in self.admin_usernames.split(","):
            cleaned = raw.strip().lstrip("@").lower()
            if cleaned:
                result.add(cleaned)
        return result

    def is_admin(self, telegram_id: int | None, username: str | None) -> bool:
        if telegram_id is not None and telegram_id in self.admin_ids:
            return True

        cleaned_username = (username or "").strip().lstrip("@").lower()
        return bool(cleaned_username and cleaned_username in self.admin_names)

    @property
    def database_file(self) -> Path:
        return Path(self.database_path)

    @property
    def exports_path(self) -> Path:
        return Path(self.exports_dir)

    @property
    def logs_path(self) -> Path:
        return Path(self.logs_dir)

    @property
    def max_export_file_bytes(self) -> int:
        return self.max_export_file_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
