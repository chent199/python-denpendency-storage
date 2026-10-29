#!/usr/bin/env bash
set -euo pipefail
cd /workspace/python-denpendency-storage
export UV_CACHE_DIR=/workspace/offline-delivery/uv-cache
export DOCKER_CONFIG=/workspace/offline-delivery/docker-config
mkdir -p "$UV_CACHE_DIR" "$DOCKER_CONFIG"
if [ ! -f dist/bundle/manifest.json ]; then
  python3 tools/prepare.py --output dist/bundle fastapi deepagents aiofiles httpx loguru python-dotenv python-multipart requests uvicorn openai langchain-openai pydantic openpyxl python-docx pandas numpy pypdf Pillow beautifulsoup4 pydantic-settings pytest
fi
if [ ! -d dist/bundle/runtime-cache/tiktoken ]; then
  python3 tools/tokenizer_cache.py dist/bundle
fi
python3 - <<'PY'
from tools.repo import verify
verify('dist/bundle')
PY
if ! docker image inspect python:3.12.8-slim-bookworm@sha256:2199a62885a12290dc9c5be3ca0681d367576ab7bf037da120e564723292a2f0 >/dev/null 2>&1; then
  docker pull python:3.12.8-slim-bookworm@sha256:2199a62885a12290dc9c5be3ca0681d367576ab7bf037da120e564723292a2f0
fi
docker build --network=none --pull=false -t offline-pypi:1.3 .
