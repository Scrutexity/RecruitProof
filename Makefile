# RecruitProof Makefile — one-command operations
# ----------------------------------------------------------------------------
# Common dev / build / test / deploy tasks. Run `make help` for the full list.
#
# Requirements: Python 3.10+, pip, docker, docker-compose (for container tasks)

.PHONY: help install dev build-index search benchmark test lint format typecheck \
	docker-build docker-run docker-stop docker-logs docker-shell \
	demo-data demo-pdfs dashboard clean backup restore

PYTHON ?= python
PORT   ?= 8000

help:  ## Show this help message
	@echo "┌─────────────────────────────────────────────────────────────────┐"
	@echo "│  RecruitProof — One-Command Operations                         │"
	@echo "│  Open-source enterprise candidate intelligence                 │"
	@echo "└─────────────────────────────────────────────────────────────────┘"
	@echo ""
	@echo "  START HERE (3 commands, ~5 minutes):"
	@echo ""
	@echo "    make install        Install Python dependencies"
	@echo "    make demo-data      Generate 10,000 synthetic resumes + build the index"
	@echo "    make dev            Start the API server at http://localhost:8000"
	@echo ""
	@echo "  ─────────────────────────────────────────────────────────────────"
	@echo ""
	@echo "  VISUAL DEMO:"
	@echo "    make dashboard      Launch the Next.js enterprise demo dashboard"
	@echo "    make demo-pdfs      Generate the 3 sample PDFs (shortlist, ROI, deletion cert)"
	@echo ""
	@echo "  SEARCH & BENCHMARK:"
	@echo "    make search         Run a sample search against the built index"
	@echo "    make benchmark      Run 20-iteration p50/p95 latency benchmark"
	@echo "    make build-index    Rebuild the FAISS + BM25 hybrid index"
	@echo ""
	@echo "  QUALITY (for developers):"
	@echo "    make test           Run the pytest test suite"
	@echo "    make lint           Check code style (flake8 + black + isort)"
	@echo "    make format         Auto-format the code"
	@echo "    make typecheck      Run mypy type checking"
	@echo ""
	@echo "  DOCKER (production deployment):"
	@echo "    make docker-build   Build the production Docker image"
	@echo "    make docker-run     Run via docker-compose (detached, port 8000)"
	@echo "    make docker-stop    Stop the running containers"
	@echo "    make docker-logs    Tail container logs"
	@echo "    make docker-shell   Open a shell inside the running container"
	@echo ""
	@echo "  BACKUP & RESTORE:"
	@echo "    make backup         Create an encrypted timestamped backup"
	@echo "    make restore        Restore from the latest backup (interactive)"
	@echo ""
	@echo "  CLEANUP:"
	@echo "    make clean          Remove caches, pycache, build artifacts"
	@echo ""
	@echo "  ─────────────────────────────────────────────────────────────────"
	@echo "  Docs: README.md (sales) · BUSINESS.md (CFO) · DEPLOYMENT.md (ops)"
	@echo "  Repo: https://github.com/Scrutexity/RecruitProof"
	@echo ""

install:  ## Install Python dependencies
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m pip install pytest black isort flake8 mypy
	@echo "✓ Dependencies installed. Run 'make demo-data' to generate test data."

dev:  ## Start FastAPI dev server with hot reload
	$(PYTHON) -m uvicorn api_server:app --host 0.0.0.0 --port $(PORT) --reload

build-index:  ## Build FAISS + BM25 hybrid index from data/candidates.jsonl
	@if [ ! -f data/candidates.jsonl ]; then \
	        echo "No data/candidates.jsonl found. Run 'make demo-data' first."; exit 1; \
	fi
	$(PYTHON) precompute.py --candidates data/candidates.jsonl --output output/ \
	        --model mini --index flat --hybrid

search:  ## Run a sample search
	@if [ ! -f output/candidates.faiss ]; then \
	        echo "No index found. Run 'make build-index' first."; exit 1; \
	fi
	$(PYTHON) search.py --jd data/sample_jd.txt --top 10 --hybrid \
	        --candidates data/candidates.jsonl

benchmark:  ## Run 20-iteration benchmark
	$(PYTHON) search.py --jd data/sample_jd.txt --benchmark 20 --candidates data/candidates.jsonl

test:  ## Run pytest test suite
	$(PYTHON) -m pytest tests/ -v --tb=short

lint:  ## Run flake8 + black --check + isort --check
	$(PYTHON) -m flake8 *.py tests/ scripts/ --max-line-length=100 --max-complexity=15
	$(PYTHON) -m black --check --line-length=100 *.py tests/ scripts/
	$(PYTHON) -m isort --check --profile=black *.py tests/ scripts/

format:  ## Auto-format with black + isort
	$(PYTHON) -m black --line-length=100 *.py tests/ scripts/
	$(PYTHON) -m isort --profile=black *.py tests/ scripts/

typecheck:  ## Run mypy on core modules
	$(PYTHON) -m mypy --strict ranker.py hybrid_retrieval.py jd_parser.py

# ---- Docker ----

docker-build:  ## Build the production Docker image
	docker build -t scrutexity/recruitproof:0.3.0 -t scrutexity/recruitproof:latest .

docker-run:  ## Run via docker-compose (detached)
	docker-compose up -d
	@echo "✓ Container started. Health check at http://localhost:8000/health"
	@echo "  Logs: make docker-logs    Shell: make docker-shell    Stop: make docker-stop"

docker-stop:  ## Stop the running containers
	docker-compose down

docker-logs:  ## Tail container logs
	docker-compose logs -f recruitproof

docker-shell:  ## Open a shell inside the running container
	docker-compose exec recruitproof /bin/bash

# ---- Demo assets ----

demo-data:  ## Generate 10,000 synthetic resumes + build hybrid index
	$(PYTHON) generate_synthetic_data.py --count 10000 --out data/candidates.jsonl
	$(PYTHON) precompute.py --candidates data/candidates.jsonl --output output/ \
	        --model mini --index flat --hybrid
	@echo "✓ Demo data ready. Run 'make dev' to start the API server."

demo-pdfs:  ## Generate the 3 demo PDFs (shortlist, ROI, deletion cert)
	$(PYTHON) demo/generate_demo_pdfs.py --out demo/
	@echo "✓ Demo PDFs generated in demo/"

dashboard:  ## Launch the Next.js enterprise demo dashboard (recproof/)
	@echo "Launching RecruitProof Enterprise Demo Dashboard..."
	@echo ""
	@echo "  The dashboard runs at http://localhost:3000"
	@echo "  All numbers are synthetic until you wire it to the real API."
	@echo "  See recproof/INSTALL.md for setup details."
	@echo ""
	@if [ ! -d recproof/node_modules ]; then \
	        echo "  Installing dashboard dependencies (first run only)..."; \
	        cd recproof && npm install; \
	fi
	@cd recproof && npm run dev

# ---- Backup ----

backup:  ## Create an encrypted timestamped backup of /data
	$(PYTHON) backup.py --output /data/backups/ --encrypt
	@echo "✓ Backup created. Older backups (30+ days) are pruned automatically."

restore:  ## Restore from the latest backup (interactive)
	@LATEST=$$(ls -t /data/backups/*.tar.gz 2>/dev/null | head -1); \
	if [ -z "$$LATEST" ]; then echo "No backups found in /data/backups/"; exit 1; fi; \
	read -p "Restore from $$LATEST? This will OVERWRITE /data. Type YES to confirm: " confirm; \
	if [ "$$confirm" = "YES" ]; then \
	        $(PYTHON) backup.py --restore "$$LATEST"; \
	else echo "Restore cancelled."; fi

# ---- Cleanup ----

clean:  ## Remove caches, pycache, build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .flake8
	@echo "✓ Cleaned."
