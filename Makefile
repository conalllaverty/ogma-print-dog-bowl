.PHONY: install api web dev test smoke generate-test

install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt
	cd products/dog-bowl/web && npm install

api:
	cd products/dog-bowl && ../../.venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port $${PORT:-8000}

web:
	cd products/dog-bowl/web && PIPELINE_API_URL=$${PIPELINE_API_URL:-http://127.0.0.1:8000} npm run dev

dev:
	@echo "Run 'make api' and 'make web' in two terminals (or products/dog-bowl/dev.sh)"

# Every generator across every product must still import.
smoke:
	.venv/bin/python tests/smoke_imports.py

# Behaviour fingerprint. Run before AND after a refactor, then diff the JSON.
test:
	.venv/bin/python tests/goldens.py /tmp/goldens-after.json /tmp/goldenjobs

generate-test:
	.venv/bin/python products/dog-bowl/generator/pipeline.py --name MAX --out out/cli-max
