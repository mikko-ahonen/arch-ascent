# PIM Development Makefile

.PHONY: build run repl test clean shell

# Build the Docker image
build:
	docker compose build

# Start the development container
run:
	docker compose up -d

# Connect to SBCL REPL
repl:
	docker compose exec pim rlwrap sbcl

# Run with project loaded
repl-load:
	docker compose exec pim rlwrap sbcl --eval '(ql:quickload :pim)' 

# Run tests
test:
	docker compose exec pim sbcl --non-interactive \
		--eval '(ql:quickload :pim)' \
		--eval '(asdf:test-system :pim)' \
		--eval '(quit)'

# Shell access to container
shell:
	docker compose exec pim bash

# Stop the container
stop:
	docker compose down

# Clean up everything
clean:
	docker compose down -v
	docker rmi pim-dev 2>/dev/null || true

# Watch source files and reload (requires inotify-tools in container)
watch:
	@echo "Watching src/ for changes..."
	@while true; do \
		inotifywait -r -e modify,create,delete src/; \
		echo "Reloading..."; \
		docker compose exec pim sbcl --non-interactive \
			--eval '(ql:quickload :pim :force t)' \
			--eval '(quit)'; \
	done
