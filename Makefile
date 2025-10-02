.PHONY: api-dev web-dev

# Start the FastAPI development server
api-dev:
	cd api && uvicorn app.main:app --reload

# Start the React development server
web-dev:
	cd web && npm run dev



