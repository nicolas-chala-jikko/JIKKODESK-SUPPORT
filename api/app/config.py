from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False)
    DATABASE_URL: str = "postgresql://zendesk:zendesk123@localhost:5432/zendesk_clone"
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str = "dev-secret-change-in-prod"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60*24
    EMAIL_IMAP_HOST: str = "imap.gmail.com"
    EMAIL_IMAP_PORT: int = 993
    EMAIL_IMAP_USER: str = "soporte@jikkosoft.com"
    EMAIL_IMAP_PASS: str = ""
    EMAIL_IMAP_FOLDER: str = "INBOX"
    EMAIL_POLL_INTERVAL: int = 60
    EMAIL_SMTP_HOST: str = "smtp.gmail.com"
    EMAIL_SMTP_PORT: int = 587
    EMAIL_SMTP_USER: str = "nicolas.chala@jikkosoft.com"
    EMAIL_SMTP_PASS: str = ""
    EMAIL_FROM: str = "nicolas.chala@jikkosoft.com"
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REFRESH_TOKEN: str = ""
    GOOGLE_ACCESS_TOKEN: str = ""
    OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/v2/email/oauth/callback"

settings = Settings()
