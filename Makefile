SHELL := /bin/zsh

PY ?= python3
PIP ?= $(PY) -m pip

INTEGRATED_DIR := backend/services/integrated_investment_service
CHART_DIR := backend/services/chart_canslim_service
KIS_DIR := backend/services/kis_trading_diagnostics
INTEGRATED_UI_DIR := frontend/integrated_ui
CHART_UI_DIR := frontend/chart_canslim_ui

.PHONY: help install-all install-integrated install-chart install-kis \
	run-integrated-api run-chart-api run-integrated-cli run-chart-cli run-kis-cli \
	serve-integrated-ui serve-chart-ui

help:
	@echo "Available targets:"
	@echo "  make install-all            # install dependencies for all backend services"
	@echo "  make install-integrated     # install integrated service dependencies"
	@echo "  make install-chart          # install chart canslim service dependencies"
	@echo "  make install-kis            # install KIS diagnostics dependencies"
	@echo "  make run-integrated-api     # run integrated FastAPI on :8000"
	@echo "  make run-chart-api          # run chart FastAPI on :8001"
	@echo "  make run-integrated-cli     # run integrated CLI"
	@echo "  make run-chart-cli          # run chart CLI"
	@echo "  make run-kis-cli            # run KIS diagnostics CLI"
	@echo "  make serve-integrated-ui    # serve integrated static UI on :3000"
	@echo "  make serve-chart-ui         # serve chart static UI on :3001"

install-all: install-integrated install-chart install-kis

install-integrated:
	$(PIP) install -r $(INTEGRATED_DIR)/requirements.txt
	$(PIP) install -r $(INTEGRATED_DIR)/server/requirements.txt

install-chart:
	$(PIP) install -r $(CHART_DIR)/requirements.txt

install-kis:
	$(PIP) install -r $(KIS_DIR)/requirements.txt

run-integrated-api:
	cd $(INTEGRATED_DIR) && $(PY) -m uvicorn server.app:app --reload --host 0.0.0.0 --port 8000

run-chart-api:
	cd $(CHART_DIR) && $(PY) -m uvicorn api:app --reload --host 0.0.0.0 --port 8001

run-integrated-cli:
	cd $(INTEGRATED_DIR) && $(PY) main.py

run-chart-cli:
	cd $(CHART_DIR) && $(PY) main.py

run-kis-cli:
	cd $(KIS_DIR) && $(PY) main.py

serve-integrated-ui:
	cd $(INTEGRATED_UI_DIR) && $(PY) -m http.server 3000

serve-chart-ui:
	cd $(CHART_UI_DIR) && $(PY) -m http.server 3001
