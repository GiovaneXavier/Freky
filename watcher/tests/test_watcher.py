"""
Testes para o watcher de imagens de raio-X.

Cobre:
  - wait_for_file_ready   — arquivo estabiliza, nao existe, timeout
  - ScanHandler.on_created — ignora dirs, extensoes invalidas, envia arquivo valido
  - ScanHandler._send_to_api — sucesso, HTTP error, excecao inesperada
"""
import sys
import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import httpx

# Garante que o modulo watcher seja importavel sem instalar o pacote
sys.path.insert(0, str(Path(__file__).parent.parent))

from watcher import ScanHandler, wait_for_file_ready  # noqa: E402


# ──────────────────────────────────────────────────────────────
# wait_for_file_ready
# ──────────────────────────────────────────────────────────────

class TestWaitForFileReady:
    def test_arquivo_estavel_retorna_true(self, tmp_path):
        """Arquivo com tamanho constante deve retornar True."""
        f = tmp_path / "scan.jpg"
        f.write_bytes(b"\xff\xd8" + b"\x00" * 100)  # 102 bytes

        result = wait_for_file_ready(f, timeout=2)
        assert result is True

    def test_arquivo_inexistente_retorna_false(self, tmp_path):
        resultado = wait_for_file_ready(tmp_path / "fantasma.jpg", timeout=1)
        assert resultado is False

    def test_arquivo_vazio_aguarda_e_retorna_false(self, tmp_path):
        """Arquivo com tamanho 0 nunca e considerado pronto."""
        f = tmp_path / "empty.jpg"
        f.write_bytes(b"")

        resultado = wait_for_file_ready(f, timeout=1)
        assert resultado is False

    def test_arquivo_crescendo_espera_estabilizar(self, tmp_path):
        """
        Simula um arquivo sendo escrito: stat() retorna tamanhos diferentes
        nas primeiras chamadas, depois estabiliza.
        """
        f = tmp_path / "growing.jpg"
        f.write_bytes(b"\xff" * 500)

        sizes = [100, 200, 500, 500]
        call_count = 0

        original_stat = Path.stat

        def fake_stat(self):
            nonlocal call_count
            if self == f and call_count < len(sizes):
                s = MagicMock()
                s.st_size = sizes[call_count]
                call_count += 1
                return s
            return original_stat(self)

        with patch.object(Path, "stat", fake_stat):
            result = wait_for_file_ready(f, timeout=5)

        assert result is True


# ──────────────────────────────────────────────────────────────
# ScanHandler.on_created
# ──────────────────────────────────────────────────────────────

class TestScanHandlerOnCreated:
    def _make_event(self, src_path: str, is_directory: bool = False):
        event = MagicMock()
        event.src_path = src_path
        event.is_directory = is_directory
        return event

    def test_ignora_diretorio(self, tmp_path):
        handler = ScanHandler()
        event = self._make_event(str(tmp_path / "subdir"), is_directory=True)

        with patch.object(handler, "_send_to_api") as mock_send:
            handler.on_created(event)
            mock_send.assert_not_called()

    @pytest.mark.parametrize("nome", [
        "scan.png", "scan.bmp", "scan.gif", "scan.txt", "scan.pdf", "scan",
    ])
    def test_ignora_extensao_invalida(self, tmp_path, nome):
        handler = ScanHandler()
        f = tmp_path / nome
        f.write_bytes(b"data")
        event = self._make_event(str(f))

        with patch.object(handler, "_send_to_api") as mock_send:
            handler.on_created(event)
            mock_send.assert_not_called()

    @pytest.mark.parametrize("nome", ["scan.jpg", "scan.jpeg", "scan.tif", "scan.tiff",
                                       "SCAN.JPG", "SCAN.JPEG", "SCAN.TIF", "SCAN.TIFF"])
    def test_processa_extensao_valida(self, tmp_path, nome):
        handler = ScanHandler()
        f = tmp_path / nome
        f.write_bytes(b"\xff\xd8" + b"\x00" * 100)
        event = self._make_event(str(f))

        with patch("watcher.wait_for_file_ready", return_value=True), \
             patch.object(handler, "_send_to_api") as mock_send:
            handler.on_created(event)
            mock_send.assert_called_once_with(f)

    def test_nao_envia_se_arquivo_nao_ficar_pronto(self, tmp_path):
        handler = ScanHandler()
        f = tmp_path / "scan.jpg"
        f.write_bytes(b"\xff\xd8")
        event = self._make_event(str(f))

        with patch("watcher.wait_for_file_ready", return_value=False), \
             patch.object(handler, "_send_to_api") as mock_send:
            handler.on_created(event)
            mock_send.assert_not_called()


# ──────────────────────────────────────────────────────────────
# ScanHandler._send_to_api
# ──────────────────────────────────────────────────────────────

class TestSendToApi:
    def _handler(self):
        handler = ScanHandler()
        return handler

    def test_envia_post_com_arquivo(self, tmp_path):
        handler = self._handler()
        f = tmp_path / "scan.jpg"
        f.write_bytes(b"\xff\xd8" + b"\x00" * 100)

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "decision": "LIBERADO",
            "processing_time_ms": 42.0,
        }

        with patch("httpx.post", return_value=mock_response) as mock_post:
            handler._send_to_api(f)
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            # Verifica URL
            assert "/scans/" in args[0]
            # Verifica que o arquivo foi enviado
            assert "files" in kwargs
            assert "file" in kwargs["files"]

    def test_loga_decisao_apos_sucesso(self, tmp_path, caplog):
        import logging
        handler = self._handler()
        f = tmp_path / "good.jpg"
        f.write_bytes(b"\xff\xd8" + b"\x00" * 50)

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "decision": "VERIFICAR",
            "processing_time_ms": 88.5,
        }

        with patch("httpx.post", return_value=mock_response), \
             caplog.at_level(logging.INFO, logger="watcher"):
            handler._send_to_api(f)

        assert "VERIFICAR" in caplog.text
        assert "good.jpg" in caplog.text

    def test_captura_http_error_sem_propagar(self, tmp_path, caplog):
        import logging
        handler = self._handler()
        f = tmp_path / "scan.jpg"
        f.write_bytes(b"\xff\xd8")

        with patch("httpx.post", side_effect=httpx.HTTPError("timeout")), \
             caplog.at_level(logging.ERROR, logger="watcher"):
            handler._send_to_api(f)  # nao deve levantar excecao

        assert "Erro" in caplog.text

    def test_captura_excecao_generica_sem_propagar(self, tmp_path, caplog):
        import logging
        handler = self._handler()
        f = tmp_path / "scan.jpg"
        f.write_bytes(b"\xff\xd8")

        with patch("httpx.post", side_effect=RuntimeError("boom")), \
             caplog.at_level(logging.ERROR, logger="watcher"):
            handler._send_to_api(f)

        assert "Erro" in caplog.text

    def test_raise_for_status_em_erro_http(self, tmp_path, caplog):
        """Resposta 4xx/5xx deve ser capturada via raise_for_status."""
        import logging
        handler = self._handler()
        f = tmp_path / "scan.jpg"
        f.write_bytes(b"\xff\xd8")

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=MagicMock()
        )

        with patch("httpx.post", return_value=mock_response), \
             caplog.at_level(logging.ERROR, logger="watcher"):
            handler._send_to_api(f)

        assert "Erro" in caplog.text
