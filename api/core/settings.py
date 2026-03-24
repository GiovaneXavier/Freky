from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False

    database_url: str = "postgresql://freky:changeme@postgres:5432/freky"
    redis_url: str = "redis://redis:6379/0"

    model_path: str = "/app/model/weights/freky.onnx"
    confidence_threshold: float = 0.60
    high_confidence_threshold: float = 0.85

    scan_input_dir: str = "/scans/incoming"
    scan_archive_dir: str = "/scans/archive"

    class Config:
        env_file = ".env"


settings = Settings()
