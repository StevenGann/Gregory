# Gregory - Smart House AI
# Multi-stage build for lean runtime image

FROM python:3.12-slim AS builder

WORKDIR /build

# Install build deps
RUN pip install --no-cache-dir build

# Copy project
COPY pyproject.toml ./
COPY src/ ./src/

# Build wheel
RUN python -m build --wheel

# ---
# Runtime stage
# ---
FROM python:3.12-slim

WORKDIR /app

# Create non-root user
RUN useradd --create-home --shell /bin/bash gregory

# Install runtime deps only (from wheel)
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl \
    && rm /tmp/*.whl

# Notes and memory directories (mount volumes here)
RUN mkdir -p /app/notes /app/memory && chown -R gregory:gregory /app

USER gregory

ENV NOTES_PATH=/app/notes
ENV MEMORY_PATH=/app/memory
EXPOSE 8000

CMD ["uvicorn", "gregory.main:app", "--host", "0.0.0.0", "--port", "8000"]
