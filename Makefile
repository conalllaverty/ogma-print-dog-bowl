.PHONY: dev api web install generate-test

install:
	python3 -m venv .venv
	.venv/bin/pip install -r backend/requirements.txt
	cd web && npm install

api:
	cd backend && ../.venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port $${PORT:-8000}

web:
	cd web && PIPELINE_API_URL=$${PIPELINE_API_URL:-http://127.0.0.1:8000} npm run dev

dev:
	@echo "Run 'make api' and 'make web' in two terminals (or use scripts/dev.sh)"

generate-test:
	.venv/bin/python backend/generator/pipeline.py --name MAX --out data/jobs/cli-max

