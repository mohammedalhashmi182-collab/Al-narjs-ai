from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_json: bool = Field(default=False, alias="LOG_JSON")
    timezone: str = Field(default="UTC", alias="TIMEZONE")

    database_url: str = Field(
        default="sqlite+aiosqlite:///ai_agent_system.db",
        alias="DATABASE_URL",
    )
    database_echo: bool = Field(default=False, alias="DATABASE_ECHO")

    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_default_model: str = Field(default="deepseek-r1", alias="OLLAMA_DEFAULT_MODEL")
    ollama_timeout: float = Field(default=120.0, alias="OLLAMA_TIMEOUT")
    ollama_max_connections: int = Field(default=10, alias="OLLAMA_MAX_CONNECTIONS")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    openai_default_model: str = Field(default="gpt-4o-mini", alias="OPENAI_DEFAULT_MODEL")

    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")
    groq_default_model: str = Field(default="llama-3.1-70b-versatile", alias="GROQ_DEFAULT_MODEL")

    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_default_model: str = Field(default="claude-3-5-sonnet-20241022", alias="ANTHROPIC_DEFAULT_MODEL")

    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_base_url: str = Field(default="https://generativelanguage.googleapis.com/v1beta/openai", alias="GEMINI_BASE_URL")
    gemini_default_model: str = Field(default="gemini-3.6-flash", alias="GEMINI_DEFAULT_MODEL")

    moonshot_api_key: str | None = Field(default=None, alias="MOONSHOT_API_KEY")
    moonshot_base_url: str = Field(default="https://api.moonshot.ai/v1", alias="MOONSHOT_BASE_URL")
    moonshot_default_model: str = Field(default="kimi-k2.7-code", alias="MOONSHOT_DEFAULT_MODEL")

    code_executor_timeout: int = Field(default=30, alias="CODE_EXECUTOR_TIMEOUT")

    secret_key: str = Field(alias="SECRET_KEY")
    algorithm: str = Field(default="HS256", alias="ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")

    cors_origins: list[str] = Field(default=["https://karmaai.online", "https://www.karmaai.online", "http://localhost:3000", "http://localhost:8000"], alias="CORS_ORIGINS")

    domain: str = Field(default="karmaai.online", alias="DOMAIN")
    www_domain: str = Field(default="www.karmaai.online", alias="WWW_DOMAIN")

    scheduler_timezone: str = Field(default="UTC", alias="SCHEDULER_TIMEZONE")
    scheduler_max_instances: int = Field(default=1, alias="SCHEDULER_MAX_INSTANCES")

    queue_worker_concurrency: int = Field(default=4, alias="QUEUE_WORKER_CONCURRENCY")
    queue_max_retries: int = Field(default=3, alias="QUEUE_MAX_RETRIES")
    queue_retry_delay: float = Field(default=5.0, alias="QUEUE_RETRY_DELAY")

    # Moyasar (Saudi payment gateway) — leave empty for bank-transfer fallback
    moyasar_api_secret: str | None = Field(default=None, alias="MOYASAR_API_SECRET")
    moyasar_publishable_key: str | None = Field(default=None, alias="MOYASAR_PUBLISHABLE_KEY")
    payment_success_url: str = Field(default="/payment/success", alias="PAYMENT_SUCCESS_URL")
    payment_failure_url: str = Field(default="/payment/failure", alias="PAYMENT_FAILURE_URL")

    # PayPal (international checkout)
    paypal_client_id: str | None = Field(default=None, alias="PAYPAL_CLIENT_ID")
    paypal_client_secret: str | None = Field(default=None, alias="PAYPAL_CLIENT_SECRET")
    paypal_mode: str = Field(default="sandbox", alias="PAYPAL_MODE")  # sandbox | live
    paypal_currency: str = Field(default="SAR", alias="PAYPAL_CURRENCY")
    paypal_webhook_id: str | None = Field(default=None, alias="PAYPAL_WEBHOOK_ID")
    # SAR -> USD rate used only for the PayPal (USD) charge; KSA pegs 3.75 SAR/USD
    paypal_sar_usd_rate: float = Field(default=0.2667, alias="PAYPAL_SAR_USD_RATE")

    # Launch promo (single code, percentage off first charge) — disabled when PROMO_CODE empty
    promo_code: str | None = Field(default=None, alias="PROMO_CODE")
    promo_percent: int = Field(default=50, alias="PROMO_PERCENT")
    promo_expires: str | None = Field(default=None, alias="PROMO_EXPIRES")  # ISO date, e.g. 2026-09-10

    # Privacy-friendly analytics: set IDs to inject tags, else nothing is loaded
    meta_pixel_id: str | None = Field(default=None, alias="META_PIXEL_ID")
    meta_ad_account_id: str | None = Field(default=None, alias="META_AD_ACCOUNT_ID")
    gtag_id: str | None = Field(default=None, alias="GTAG_ID")

    # VAT (KSA, applied to Saudi-facing invoices)
    vat_rate: float = Field(default=0.15, alias="VAT_RATE")

    # Owner dashboard gate — must be set via env, never a built-in default
    owner_password: str = Field(alias="OWNER_PASSWORD")

    # Email (SMTP) — Gmail example
    smtp_host: str = Field(default="smtp.gmail.com", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str = Field(default="", alias="SMTP_USERNAME")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    smtp_from: str = Field(default="", alias="SMTP_FROM")
    mail_reply_to: str = Field(default="", alias="MAIL_REPLY_TO")
    brevo_api_key: str = Field(default="", alias="BREVO_API_KEY")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
