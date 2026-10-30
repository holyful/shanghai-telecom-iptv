# Contributing

HomeCast currently targets Shanghai Telecom only. Before expanding provider or
network support, open an issue describing the protocol and test environment
without including real subscriber information.

## Branches and Reviews

- `main` is the integration branch. Do not push feature code directly to it.
- Use a short-lived `feat/`, `fix/`, or `docs/` branch. Automated Codex work uses
  `codex/` branches.
- Keep commits scoped and use descriptive conventional commit subjects.
- Open a pull request. Include tests, deployment impact, security impact, and
  rollback instructions. Require passing CI before merging.
- Prefer squash merges, delete merged feature branches, and never force-push
  `main` or rewrite published release tags.
- Releases use `vMAJOR.MINOR.PATCH`. Publish only from a tested commit on `main`.

## Validation

```bash
python -m pip install -r requirements.lock
python -m pip install --no-deps .
python -m unittest discover -s tests -v
npm install --no-save playwright@1.58.2
npx playwright install chromium
FRONTEND_BROWSER=chromium node --test tests/frontend.test.cjs
docker build -t homecast-review .
python tests/docker_smoke.py homecast-review
docker compose config --quiet
docker compose -f compose.yaml -f compose.build.yaml config --quiet
```

PowerShell uses `$env:FRONTEND_BROWSER = 'chromium'` before the same Node command.
Python/browser tests run cross-platform; actual interface binding and IPTV
authentication require Linux with an authorized IPTV network. The container smoke
test requires a local Linux Docker engine and uses synthetic fixtures without
contacting the operator. It checks direct environment and persisted scheduling.

Add a regression test before fixing a bug. Verify the installed wheel includes
static assets and third-party licenses; running from the source tree alone can
hide packaging omissions. Live provider tests are manual and must not introduce
credentials into CI. Keep local configuration outside version control.

## Release Checklist

1. Review the diff, dependencies, account-data boundaries and migration impact.
2. Pass unit tests, browser tests and Docker build; test an actual official
   refresh and a bounded authorized stream where available.
3. Update the changelog. Merge the reviewed pull request after CI passes.
4. Tag the exact merged commit and verify the image-publishing workflow.
5. Ensure the GHCR package is public and anonymously pullable. Never assume a
   public repository makes its first container package public automatically.
6. Publish release notes with limitations, tested architecture and upgrade steps.

Examples and test fixtures must use fictional identities and reserved example
addresses. Raw captures, authentication forms, tokens, cookies, subscriber MACs,
real private configuration and credentials are not acceptable contributions.
