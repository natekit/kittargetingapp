import os
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173,https://web-i2xumnks2-nates-projects-b0f17eca.vercel.app"
    APP_ENV: str = "dev"
    TZ: str = "America/New_York"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Parse CORS_ORIGINS from comma-separated string
        if isinstance(self.CORS_ORIGINS, str):
            self.CORS_ORIGINS = [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
        else:
            self.CORS_ORIGINS = [
                "http://localhost:3000",
                "http://localhost:5173", 
                "https://web-i2xumnks2-nates-projects-b0f17eca.vercel.app"
            ]


settings = Settings()

