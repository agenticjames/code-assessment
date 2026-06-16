# Biggy worker — claims biggy:jobs and runs the engine (docs/PHASE2.md §1).
# Build from the REPO ROOT (it needs workspaces/ alongside src/cli):
#   docker build -f src/cli/Dockerfile -t biggy-worker .
FROM python:3.11-slim

WORKDIR /app
COPY src/cli/ /app/src/cli/
COPY workspaces/ /app/workspaces/

RUN pip install --no-cache-dir -e "/app/src/cli[worker]"

# The vault the engine + source/topology tools read. DATABASE_URL / REDIS_URL / GEMINI_API_KEY
# (or BIGGY_FAKE_RUN=1) are supplied by the environment (e.g. Railway service variables).
ENV BIGGY_WORKSPACES_ROOT=/app/workspaces

CMD ["python", "-m", "biggy.worker"]
