.PHONY: run test docker-up docker-down deploy destroy clean

# --- Local Development ---
run:
	python app.py

test:
	pytest tests/ -v

# --- Docker ---
docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

# --- AWS Infrastructure (costs money! use destroy when done) ---
deploy:
	cd terraform && terraform init && terraform apply -auto-approve

destroy:
	cd terraform && terraform destroy -auto-approve

# --- Cleanup ---
clean:
	docker compose down --rmi all 2>/dev/null || true
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true