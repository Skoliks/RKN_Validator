from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Site Compliance Checker"
    app_env: str = "local"
    app_version: str = "0.1.0"
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = False
    log_level: str = "INFO"
    max_pages_per_site: int = 5
    request_timeout_seconds: float = 10
    max_requests_per_site: int = 15
    enable_browser_check: bool = False
    browser_timeout_seconds: float = 15
    browser_navigation_wait_until: str = "networkidle"
    browser_max_network_requests: int = 200
    enable_cookie_interaction_check: bool = False
    cookie_interaction_timeout_seconds: float = 10
    cookie_interaction_text_limit: int = 3000

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
