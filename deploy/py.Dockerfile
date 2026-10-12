# Worker and inference (same image; choose the module with the command). CPU by default.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.11.9 /uv /usr/local/bin/uv
WORKDIR /app/py
COPY py/pyproject.toml py/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY py/kbpy ./kbpy
ENV PATH=/app/py/.venv/bin:$PATH HF_HOME=/models
# Optional: bake the pinned weights into the image (otherwise mount /models and download once).
ARG BAKE_MODEL=0
RUN if [ "$BAKE_MODEL" = "1" ]; then python -c "from huggingface_hub import snapshot_download; snapshot_download('google/embeddinggemma-2', revision='914f7f89142e33e77833254d9c9b90c3cef7303b')"; fi
RUN useradd -m kb && mkdir -p /models && chown kb /models
USER kb
CMD ["python", "-m", "kbpy.worker"]
