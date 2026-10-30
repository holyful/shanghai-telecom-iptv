# Environment Configuration Implementation Plan

> For agentic workers: use superpowers:executing-plans; verify each task before moving on.

**Goal:** Run the published HomeCast image using Docker environment variables and one data volume, with udpxy remaining external.

**Architecture:** A shared typed configuration loader reads HOMECAST_* environment values with documented defaults. The server and container health check use the same loader. Explicit scheduling variables override persisted UI settings and are read-only in the UI. There is no JSON configuration or secret-file layer. The configured public URL controls subscription links; active client paths and channel mappings are retained.

**Tech Stack:** Existing Python standard library, vanilla browser UI, Docker and GitHub Actions.

**Spec:** User approved environment-based Compose deployment using a prebuilt image, explicitly excluded a Docker management panel and bundled udpxy, and requested a separate optional source-build workflow. Document external udpxy setup and end-to-end checks; do not change the household network or udpxy service.

## Approaches

- Selected: environment-only image and external udpxy.
- Rejected by user: JSON compatibility and secret-file configuration layers.
- Excluded by user: bundle udpxy or manage VLANs from HomeCast.

## Constraints

- No credentials in public code, image layers, logs, examples or CI.
- Preserve Apple TV URLs, Jellyfin exports and user/library permissions.
- Keep Linux/macOS shell documentation and add PowerShell guidance where relevant.
- Integrate on codex/docker-deployment in an isolated checkout; preserve the original working directory and unrelated docs/clients.md edit.
- Do not overwrite v0.1.0. Prepare v0.2.0 through PR and required CI checks.

## Review Focus

- Missing/malformed/empty environment values must fail safely, without echoing secrets.
- Boolean false and explicit environment schedule values must not be overridden by persisted data.
- No JSON fallback; account values must come from environment variables. Preserve active channel mappings in the data volume.
- Health checks must work without a mounted config file.
- Default Compose must pull the published image, not require a source checkout/build.

## Tasks

### 1. Typed Configuration And Health Check

Files: iptv_lan/config.py, iptv_lan/healthcheck.py, iptv_lan/server.py, Dockerfile, tests/test_config.py.

- [x] Verify env-only loading, precedence, strict types, safe errors and rejection of unsupported configuration variables.
- [x] Implement load_config(environ=None), ConfigError and a shared-config health check.
- [x] Verify the unit suite; retain existing endpoint output baselines.

### 2. Schedule Ownership

Files: iptv_lan/service.py, iptv_lan/static/app.js, tests/test_service.py, tests/frontend.test.cjs.

- [x] Add failing tests for explicit env schedule ownership and UI locking.
- [x] Preserve ordinary persisted UI settings; reject mutations to env-owned values and disable only corresponding UI controls.
- [x] Run backend and browser regression suites.

### 3. Container Delivery And External udpxy Guide

Files: compose.yaml, README.md, docs/configuration.md, docs/udpxy.md, docs/network.md, tests/docker_smoke.py, .github/workflows/publish.yaml, version/changelog files.

- [x] Replace default local-build Compose with published image, environment fields and named data volume.
- [x] Document prebuilt-image Compose, separate compose.build.yaml and environment settings; no new Docker management UI.
- [x] Verify udpxy flags/UCI names against upstream sources; document source/bind interfaces, LAN access, health versus actual stream and bounded diagnostics.
- [x] Add and run real-container env-only/persistent-schedule/health-check smoke tests and CI integration.
- [ ] Review diff, scan public content/history, create PR, then release/deploy only after required checks and applicable approval.

### 4. HTTP Subscription Links

Files: iptv_lan/static/{index.html,app.js,styles.css,README.md}, tests/frontend.test.cjs, docs/clients.md.

- [x] Add failing tests for visible absolute URLs, clipboard success/failure, no unintended downloads, and mobile layout.
- [x] Replace primary download actions with a subscription dialog; keep file download as an explicit secondary action.
- [x] Verify browser tests and desktop/mobile screenshots; preserve existing endpoint paths.
