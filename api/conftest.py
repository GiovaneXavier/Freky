"""
Configuração global de testes — executado pelo pytest antes de qualquer import do app.
Define variáveis de ambiente necessárias para o ambiente de teste.
"""
import os

os.environ.setdefault("FREKY_ENV", "test")
