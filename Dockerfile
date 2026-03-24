FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN uv pip install --system .

ENTRYPOINT ["jellyfin-strm"]
CMD ["--help"]
