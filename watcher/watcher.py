"""
Watcher — monitora a pasta onde o Xport da HI-SCAN 6040i deposita as imagens.
Quando um novo arquivo JPEG/TIFF aparece, envia para a API de deteccao.
"""
import os
import time
import logging
import httpx
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

API_URL = os.getenv("API_URL", "http://api:8000")
SCAN_INPUT_DIR = os.getenv("SCAN_INPUT_DIR", "/scans/incoming")
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".tif", ".tiff"}


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

    def _send_to_api(self, path: Path):
        try:
            with path.open("rb") as f:
                response = httpx.post(
                    f"{API_URL}/scans/",
                    files={"file": (path.name, f, "image/jpeg")},
                    timeout=30.0,
                )
            response.raise_for_status()
            result = response.json()
            log.info(
                f"Scan processado: {path.name} → "
                f"decisao={result['decision']} "
                f"({result['processing_time_ms']:.0f}ms)"
            )
        except httpx.HTTPError as e:
            log.error(f"Erro ao enviar scan para API: {e}")
        except Exception as e:
            log.error(f"Erro inesperado: {e}")


def main():
    input_dir = Path(SCAN_INPUT_DIR)
    input_dir.mkdir(parents=True, exist_ok=True)

    log.info(f"Monitorando pasta: {input_dir}")
    log.info(f"API: {API_URL}")

    observer = Observer()
    observer.schedule(ScanHandler(), str(input_dir), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
