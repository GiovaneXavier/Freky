from pydantic import field_validator
from pydantic_settings import BaseSettings

_INSECURE_JWT_DEFAULT = "change-me-in-production-use-a-long-random-string"


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

    # CORS — lista de origens permitidas separadas por vírgula
    allowed_origins: str = "http://localhost:3000,http://localhost:5173,http://dashboard"

    # Upload — tamanho máximo em bytes (padrão: 50 MB)
    max_upload_bytes: int = 50 * 1024 * 1024

    scan_input_dir: str = "/scans/incoming"
    scan_archive_dir: str = "/scans/archive"

    # Autenticação JWT
    jwt_secret_key: str = "change-me-in-production-use-a-long-random-string"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480  # 8 horas

    # Usuários do sistema — JSON: [{"username":"x","password":"y","role":"operator"}]
    # Roles: "admin" (acesso total) | "operator" (somente leitura + feedback)
    freky_users: str = '[{"username":"admin","password":"admin","role":"admin"}]'

    @field_validator("jwt_secret_key")
    @classmethod
    def _validate_jwt_secret(cls, v: str) -> str:
        import os
        # Ignora validação em ambiente de testes
        if os.getenv("FREKY_ENV") == "test":
            return v
        if v == _INSECURE_JWT_DEFAULT:
            raise ValueError(
                "JWT_SECRET_KEY está com o valor padrão inseguro. "
                "Defina a variável de ambiente JWT_SECRET_KEY com um segredo forte antes de iniciar."
            )
        if len(v) < 32:
            raise ValueError("JWT_SECRET_KEY deve ter no mínimo 32 caracteres.")
        return v

    class Config:
        env_file = ".env"


settings = Settings()
