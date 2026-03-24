.PHONY: help up down dev staging-up staging-down staging-logs staging-ps monitoring-up monitoring-down monitoring-open test lint mock-scans train train-docker augment validate-dataset evaluate export infer clean

# Variaveis
COMPOSE         = docker compose
COMPOSE_DEV     = docker compose -f docker-compose.yml -f docker-compose.dev.yml
COMPOSE_STAGING = docker compose -f docker-compose.yml -f docker-compose.staging.yml --env-file .env.staging
API_DIR      = api
MODEL_DIR    = model

help:
	@echo ""
	@echo "  Freky — X-Ray Item Detection"
	@echo ""
	@echo "  Producao:"
	@echo "    make up              Sobe todos os servicos"
	@echo "    make down            Para todos os servicos"
	@echo "    make logs            Mostra logs em tempo real"
	@echo ""
	@echo "  Monitoramento:"
	@echo "    make monitoring-up   Sobe Prometheus (9090) + Grafana (3001)"
	@echo "    make monitoring-down Para os servicos de monitoramento"
	@echo "    make monitoring-open Abre Grafana no browser"
	@echo ""
	@echo "  Homologacao (staging):"
	@echo "    make staging-up      Sobe stack de staging (porta 3001 / 8001)"
	@echo "    make staging-down    Para stack de staging"
	@echo "    make staging-logs    Logs em tempo real do staging"
	@echo "    make staging-ps      Status dos servicos de staging"
	@echo "    make staging-validate Valida pipeline no staging"
	@echo ""
	@echo "  Desenvolvimento:"
	@echo "    make dev         Sobe stack de dev (hot-reload)"
	@echo "    make test        Roda testes da API"
	@echo "    make lint        Roda ruff no codigo"
	@echo ""
	@echo "  Dados / Modelo:"
	@echo "    make mock-scans      Gera scans sinteticos para teste"
	@echo "    make validate-dataset Valida dataset HiXray antes do treino"
	@echo "    make augment         Augmenta dataset de treino (fator 3x)"
	@echo "    make train           Treino local (requer GPU)"
	@echo "    make train-docker    Treino em container Docker com GPU"
	@echo "    make evaluate        Avalia modelo (mAP, precision, recall)"
	@echo "    make infer           Inferencia em pasta de scans"
	@echo "    make export          Exporta melhor checkpoint para ONNX"
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

# === Monitoramento ================================================

monitoring-up:
	$(COMPOSE) up -d prometheus grafana redis-exporter

monitoring-down:
	$(COMPOSE) stop prometheus grafana redis-exporter

monitoring-open:
	@echo "Grafana:    http://localhost:3001  (admin/admin)"
	@echo "Prometheus: http://localhost:9090"
	@xdg-open http://localhost:3001 2>/dev/null || open http://localhost:3001 2>/dev/null || true

# === Homologação (staging) ========================================

staging-up:
	@test -f .env.staging || (echo "[ERRO] .env.staging nao encontrado. Copie .env.staging e ajuste as credenciais." && exit 1)
	$(COMPOSE_STAGING) up -d --build

staging-down:
	$(COMPOSE_STAGING) down

staging-logs:
	$(COMPOSE_STAGING) logs -f

staging-ps:
	$(COMPOSE_STAGING) ps

staging-validate:
	@echo "Validando pipeline no staging..."
	python scripts/validate_pipeline.py \
		--model model/weights/freky.onnx \
		--synthetic \
		--output /tmp/staging-validation.json
	@echo "Resultado salvo em /tmp/staging-validation.json"

staging-clean:
	$(COMPOSE_STAGING) down -v --remove-orphans

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

validate-dataset:
	python $(MODEL_DIR)/data/scripts/validate_dataset.py \
		--dataset-dir $(MODEL_DIR)/data/hixray_yolo

validate-dataset-fix:
	python $(MODEL_DIR)/data/scripts/validate_dataset.py \
		--dataset-dir $(MODEL_DIR)/data/hixray_yolo --fix

augment:
	@test -d $(MODEL_DIR)/data/hixray_yolo/train || \
		(echo "Dataset nao encontrado. Rode: make convert-dataset HIXRAY_DIR=..." && exit 1)
	python $(MODEL_DIR)/data/scripts/augment_xray.py \
		--input-dir $(MODEL_DIR)/data/hixray_yolo/train \
		--output-dir $(MODEL_DIR)/data/hixray_augmented/train \
		--factor 3 \
		--severity medium
	cp $(MODEL_DIR)/data/hixray_yolo/dataset.yaml $(MODEL_DIR)/data/hixray_augmented/dataset.yaml
	cp -r $(MODEL_DIR)/data/hixray_yolo/test $(MODEL_DIR)/data/hixray_augmented/test

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
		--model-size m \
		--run-name freky-v1

train-augmented:
	@test -f $(MODEL_DIR)/data/hixray_augmented/dataset.yaml || \
		(echo "Dataset aumentado nao encontrado. Rode: make augment" && exit 1)
	python $(MODEL_DIR)/training/train.py \
		--data $(MODEL_DIR)/data/hixray_augmented/dataset.yaml \
		--epochs 80 \
		--model-size m \
		--run-name freky-v1-augmented

train-docker:
	docker build -f docker/train.Dockerfile -t freky-train .
	docker run --gpus all --rm \
		-v $(PWD)/$(MODEL_DIR):/workspace/$(MODEL_DIR) \
		freky-train model/training/train.py \
		--data $(MODEL_DIR)/data/hixray_yolo/dataset.yaml \
		--epochs 50 --model-size m

evaluate:
	@test -n "$(WEIGHTS)" || (echo "WEIGHTS nao definido. Use: make evaluate WEIGHTS=runs/.../best.pt" && exit 1)
	python $(MODEL_DIR)/training/evaluate.py \
		--weights $(WEIGHTS) \
		--data $(MODEL_DIR)/data/hixray_yolo/dataset.yaml

infer:
	@test -n "$(WEIGHTS)" || (echo "WEIGHTS nao definido. Use: make infer WEIGHTS=model/runs/.../best.pt SOURCE=scans/incoming/" && exit 1)
	@test -n "$(SOURCE)" || (echo "SOURCE nao definido. Use: make infer WEIGHTS=... SOURCE=scans/incoming/" && exit 1)
	python $(MODEL_DIR)/training/infer.py \
		--weights $(WEIGHTS) \
		--source $(SOURCE) \
		--output-dir scans/annotated \
		--conf 0.60

export:
	@test -n "$(WEIGHTS)" || (echo "WEIGHTS nao definido. Use: make export WEIGHTS=model/runs/.../best.pt" && exit 1)
	python $(MODEL_DIR)/export/export_onnx.py \
		--weights $(WEIGHTS) \
		--output-dir $(MODEL_DIR)/weights

# === Limpeza ======================================================

clean:
	$(COMPOSE) down -v --remove-orphans
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -name "*.pyc" -delete 2>/dev/null; true
