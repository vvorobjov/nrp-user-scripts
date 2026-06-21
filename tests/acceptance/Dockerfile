# [EBR2-96] Acceptance-suite runner image.
#
# Based on the official Playwright image, which ships chromium + all the OS
# libraries it needs preinstalled at a pinned version. The tag's Playwright
# version MUST match `playwright==` in requirements.txt (kept at 1.47.0). This
# avoids the `playwright install --with-deps` apt-font breakage on plain
# python-slim bases.
#
# Run it sharing haproxy's network namespace so the frontend's build-time-baked
# http://localhost:9000 proxy URL resolves to the proxy with no host port:
#   docker run --rm --network container:nrp-haproxy nrp-acceptance
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /suite

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default: run both suites, emit JUnit XML + a Playwright trace on failure.
ENTRYPOINT ["pytest"]
CMD ["-v", "--junitxml=/suite/results/junit.xml", "--tracing=retain-on-failure", "--output=/suite/results"]
