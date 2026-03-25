"""
Watcher — monitora a pasta onde o Xport da HI-SCAN 6040i deposita as imagens.
Quando um novo arquivo JPEG/TIFF aparece, envia para a API de deteccao.
"""
import os
import time
import logging
import httpx
from pathlib import Path
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler, FileCreatedEvent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

API_URL = os.getenv("API_URL", "http://api:8000")
SCAN_INPUT_DIR = os.getenv("SCAN_INPUT_DIR", "/scans/incoming")
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".tif", ".tiff", ".png"}

# Autenticação
WATCHER_USERNAME = os.getenv("WATCHER_USERNAME", "")
WATCHER_PASSWORD = os.getenv("WATCHER_PASSWORD", "")

# Retry
MAX_RETRIES = int(os.getenv("WATCHER_MAX_RETRIES", "4"))
RETRY_BASE_DELAY = float(os.getenv("WATCHER_RETRY_BASE_DELAY", "2.0"))  # segundos


def get_token() -> str | None:
    """Autentica na API e retorna o JWT token."""
    if not WATCHER_USERNAME or not WATCHER_PASSWORD:
        return None
    try:
        r = httpx.post(
            f"{API_URL}/auth/login",
            data={"username": WATCHER_USERNAME, "password": WATCHER_PASSWORD},
            timeout=10.0,
        )
        r.raise_for_status()
        token = r.json().get("access_token")
        log.info("Autenticado na API como '%s'", WATCHER_USERNAME)
        return token
    except Exception as e:
        log.error("Falha ao autenticar na API: %s", e)
        return None


def wait_for_file_ready(path: Path, timeout: int = 10) -> bool:
    """
    Aguarda o arquivo estar completamente escrito antes de processar.
    O Xport pode demorar alguns instantes para fechar o arquivo.
    """
    start = time.time()
    last_size = -1
    while time.time() - start < timeout:
        try:
            current_size = path.stat().st_size
            if current_size == last_size and current_size > 0:
                return True
            last_size = current_size
        except FileNotFoundError:
            return False
        time.sleep(0.2)
    return False


class ScanHandler(FileSystemEventHandler):
    def __init__(self, token: str | None = None):
        super().__init__()
        self._token = token

    def _auth_headers(self) -> dict:
        if self._token:
            return {"Authorization": f"Bearer {self._token}"}
        return {}

    def on_created(self, event: FileCreatedEvent):
        if event.is_directory:
            return

        path = Path(event.src_path)
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return

        log.info(f"Novo scan detectado: {path.name}")

        if not wait_for_file_ready(path):
            log.warning(f"Arquivo nao ficou pronto a tempo: {path.name}")
            return

        self._send_to_api(path)

    def _refresh_token(self):
        """Renova o token JWT."""
        new_token = get_token()
        if new_token:
            self._token = new_token

    def _send_to_api(self, path: Path):
        delay = RETRY_BASE_DELAY
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                with path.open("rb") as f:
                    response = httpx.post(
                        f"{API_URL}/scans/",
                        files={"file": (path.name, f, "image/jpeg")},
                        headers=self._auth_headers(),
                        timeout=30.0,
                    )
                response.raise_for_status()
                result = response.json()
                log.info(
                    "Scan processado: %s → decisao=%s (%.0fms)",
                    path.name,
                    result["decision"],
                    result["processing_time_ms"],
                )
                return
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    log.warning("Token expirado, renovando...")
                    self._refresh_token()
                    continue
                log.error(
                    "Erro HTTP %d ao enviar %s (tentativa %d/%d): %s",
                    e.response.status_code,
                    path.name,
                    attempt,
                    MAX_RETRIES,
                    e,
                )
                if 400 <= e.response.status_code < 500:
                    return
            except (httpx.RequestError, Exception) as e:
                log.warning(
                    "Falha ao enviar %s (tentativa %d/%d): %s",
                    path.name,
                    attempt,
                    MAX_RETRIES,
                    e,
                )

            if attempt < MAX_RETRIES:
                log.info("Aguardando %.1fs antes de tentar novamente...", delay)
                time.sleep(delay)
                delay *= 2

        log.error(
            "Scan %s não pôde ser enviado após %d tentativas. Arquivo mantido em: %s",
            path.name,
            MAX_RETRIES,
            path,
        )


def main():
    input_dir = Path(SCAN_INPUT_DIR)
    input_dir.mkdir(parents=True, exist_ok=True)

    log.info(f"Monitorando pasta: {input_dir}")
    log.info(f"API: {API_URL}")

    token = get_token()

    observer = PollingObserver()
    observer.schedule(ScanHandler(token=token), str(input_dir), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
