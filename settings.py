from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    mongodb_uri: str
    jwt_secret_key: str | None = None
    jwt_algorithm: str 
    access_token_expire_minutes: int 
    LOG_LEVEL: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    
settings = Settings()

__all__ = ["settings"]