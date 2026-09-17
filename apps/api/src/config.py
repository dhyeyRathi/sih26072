"""
SIH26072 — Thunderstorm & Lightning Nowcasting Platform
Application settings loaded from environment variables.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    database_url: str = ""

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_cors_origins: str = "http://localhost:3000"

    # Data directories
    data_raw_dir: str = "./data/raw"
    data_processed_dir: str = "./data/processed"
    model_artifacts_dir: str = "./ml/models"

    # MVP Region: Gujarat/Ahmedabad
    mvp_center_lat: float = 23.0225
    mvp_center_lon: float = 72.5714
    mvp_grid_size_km: int = 200
    mvp_grid_resolution_km: int = 1
    mvp_time_step_minutes: int = 10

    # Grid dimensions (derived: 200km / 1km = 200 cells)
    @property
    def grid_height(self) -> int:
        return self.mvp_grid_size_km // self.mvp_grid_resolution_km

    @property
    def grid_width(self) -> int:
        return self.mvp_grid_size_km // self.mvp_grid_resolution_km

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
