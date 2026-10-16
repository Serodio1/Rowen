# The web API's image (ADR 0009). Built in two stages: the first installs the
# dependencies and the project with uv, the second keeps only the result, so
# the image has neither uv nor the build files.

FROM python:3.14-slim-trixie AS build

# The same uv for everyone who builds the image.
RUN pip install --no-cache-dir --root-user-action=ignore uv==0.13.1

# Compile the Python files now, since the server cannot write them when it
# runs; copy the packages into the environment rather than linking them; and
# use the image's Python, never a downloaded one.
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# The dependencies first, in their own layer: Docker reuses it as long as
# pyproject.toml and uv.lock do not change, so a code change does not install
# them again. --locked fails if uv.lock is out of date, and --no-dev leaves out
# the tools that only development needs.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

# Then the code. --no-editable copies the project into the environment, so the
# next stage only needs the environment.
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

FROM python:3.14-slim-trixie

# The server runs as a user with no special rights, not as root.
RUN useradd --system --no-create-home rowen

COPY --from=build /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

USER rowen
EXPOSE 8000

# Docker Compose asks this every few seconds to know whether the API is ready.
HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/decks', timeout=2)"]

# One process only: matches are kept in that process's memory, so a second
# worker would not know them. 0.0.0.0 lets the other containers reach the API;
# Docker Compose does not publish its port on the computer.
CMD ["uvicorn", "rowen.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
