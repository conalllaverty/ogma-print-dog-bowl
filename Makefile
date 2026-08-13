.PHONY: install api web dev test smoke pytest images generate-test

install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt
	cd studio/web && npm ci

# One command: installs anything missing, then runs API + web together.
dev:
	bash studio/dev.sh

api:
	cd studio && PYTHONPATH=$$PWD ../.venv/bin/python -m uvicorn api.main:app --reload --host 0.0.0.0 --port $${PORT:-8000}

web:
	cd studio/web && PIPELINE_API_URL=$${PIPELINE_API_URL:-http://127.0.0.1:8000} npm run dev

# Every generator across every product must still import.
smoke:
	.venv/bin/python tests/smoke_imports.py

# Unit tests — retention, rate limiting, the name-fit agreement check.
pytest:
	.venv/bin/python -m pytest tests -q

# Behaviour fingerprint. Run before AND after a refactor, then diff the JSON.
test:
	.venv/bin/python tests/goldens.py /tmp/goldens-after.json /tmp/goldenjobs

# What CI builds, and what Railway will deploy. See DEPLOY.md.
images:
	docker build -f studio/Dockerfile -t ogma-studio-api .
	docker build -t ogma-studio-web studio/web

generate-test:
	.venv/bin/python products/dog-bowl/generator/pipeline.py --name MAX --out out/cli-max
