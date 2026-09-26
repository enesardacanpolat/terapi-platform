from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    secret_key: str
    debug: bool = False
    demo_mode: bool = False

    access_token_expire_minutes: int = 30
    jwt_algorithm: str = "HS256"


settings = Settings()