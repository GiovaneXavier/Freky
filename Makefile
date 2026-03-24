.PHONY: help up down dev test lint mock-scans train export clean

# Variaveis
COMPOSE      = docker compose
COMPOSE_DEV  = docker compose -f docker-compose.yml -f docker-compose.dev.yml
API_DIR      = api
MODEL_DIR    = model

help:
	@echo ""
	@echo "  Freky — X-Ray Item Detection"
	@echo ""
	@echo "  Producao:"
	@echo "    make up          Sobe todos os servicos"
	@echo "    make down        Para todos os servicos"
	@echo "    make logs        Mostra logs em tempo real"
	@echo ""
	@echo "  Desenvolvimento:"
	@echo "    make dev         Sobe stack de dev (hot-reload)"
	@echo "    make test        Roda testes da API"
	@echo "    make lint        Roda ruff no codigo"
	@echo ""
	@echo "  Dados / Modelo:"
	@echo "    make mock-scans  Gera scans sinteticos para teste"
	@echo "    make train       Inicia treinamento do modelo"
	@echo "    make export      Exporta melhor checkpoint para ONNX"
	@echo ""
	@echo "  Outros:"
	@echo "    make clean       Remove containers e volumes"
	@echo ""

# === Producao =====================================================

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

restart:
	$(COMPOSE) restart

# === Desenvolvimento ==============================================

dev:
	$(COMPOSE_DEV) up --build

test:
	cd $(API_DIR) && pip install -q -r requirements-dev.txt && \
	pytest -v --cov=. --cov-report=term-missing

lint:
	ruff check $(API_DIR) watcher

# === Dados / Modelo ===============================================

mock-scans:
	@echo "Gerando 30 scans sinteticos em scans/incoming..."
	mkdir -p scans/incoming
	python $(MODEL_DIR)/data/scripts/generate_mock_scans.py \
		--count 30 \
		--output-dir scans/incoming \
		--interval 0.5

mock-scans-fast:
	mkdir -p scans/incoming
	python $(MODEL_DIR)/data/scripts/generate_mock_scans.py \
		--count 30 \
		--output-dir scans/incoming

convert-dataset:
	@test -n "$(HIXRAY_DIR)" || (echo "HIXRAY_DIR nao definido. Use: make convert-dataset HIXRAY_DIR=/path/to/HiXray" && exit 1)
	python $(MODEL_DIR)/data/scripts/convert_hixray_to_yolo.py \
		--hixray-dir $(HIXRAY_DIR) \
		--output-dir $(MODEL_DIR)/data/hixray_yolo

train:
	@test -f $(MODEL_DIR)/data/hixray_yolo/dataset.yaml || \
		(echo "Dataset nao encontrado. Rode: make convert-dataset HIXRAY_DIR=..." && exit 1)
	python $(MODEL_DIR)/training/train.py \
		--data $(MODEL_DIR)/data/hixray_yolo/dataset.yaml \
		--epochs 50 \
		--model-size m

evaluate:
	@test -n "$(WEIGHTS)" || (echo "WEIGHTS nao definido. Use: make evaluate WEIGHTS=runs/.../best.pt" && exit 1)
	python $(MODEL_DIR)/training/evaluate.py \
		--weights $(WEIGHTS) \
		--data $(MODEL_DIR)/data/hixray_yolo/dataset.yaml

export:
	@test -n "$(WEIGHTS)" || (echo "WEIGHTS nao definido. Use: make export WEIGHTS=runs/.../best.pt" && exit 1)
	python $(MODEL_DIR)/export/export_onnx.py \
		--weights $(WEIGHTS) \
		--output-dir $(MODEL_DIR)/weights

# === Limpeza ======================================================

clean:
	$(COMPOSE) down -v --remove-orphans
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -name "*.pyc" -delete 2>/dev/null; true
