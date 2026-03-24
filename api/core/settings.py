from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False

    database_url: str = (
        "mssql://freky:changeme@sqlserver:1433/freky"
        "?driver=ODBC+Driver+18+for+SQL+Server"
        "&TrustServerCertificate=yes"
    )
    redis_url: str = "redis://redis:6379/0"

    model_path: str = "/app/model/weights/freky.onnx"
    confidence_threshold: float = 0.60
    high_confidence_threshold: float = 0.85

    # Thresholds por classe — itens críticos (segurança) usam limiar menor
    # para reduzir falsos negativos; itens não críticos usam limiar maior.
    # Sobrescreve confidence_threshold quando a classe está presente.
    class_confidence_thresholds: dict[str, float] = {
        "portable_charger_1": 0.55,
        "portable_charger_2": 0.55,
        "mobile_phone": 0.50,
        "laptop": 0.65,
        "tablet": 0.60,
        "cosmetic": 0.75,
        "water": 0.70,
        "nonmetallic_lighter": 0.55,
    }

    scan_input_dir: str = "/scans/incoming"
    scan_archive_dir: str = "/scans/archive"

    class Config:
        env_file = ".env"


settings = Settings()
