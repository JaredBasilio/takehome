.PHONY: dev backend frontend install reset

dev:
	@echo "Starting backend on :8000 and frontend on :5173"
	@make -j2 backend frontend

backend:
	cd backend && .venv/bin/uvicorn main:app --port 8000

frontend:
	cd frontend && npm run dev

install:
	cd backend && /usr/bin/python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
	cd frontend && npm install

reset:
	rm -f backend/data/app.db
	@echo "DB deleted — restart backend to reseed"
