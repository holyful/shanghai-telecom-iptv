# HomeCast Frontend

Buildless Chinese frontend for Shanghai Telecom household IPTV. Serve
`index.html` at `/` and this directory at `/static/`, on the same origin as
the API. No authentication UI, build tooling, remote fonts, remote channel
logos, analytics, browser persistence, or runtime CDN dependency is used.

The first screen reads real API data. Unavailable services and empty data
have explicit states; production assets do not contain sample channels.
Dates and epoch timestamps are displayed in `Asia/Shanghai` (Beijing time),
including the date sent to the programme endpoint.

## Integration

- Read: `/api/status`, `/api/channels`, `/api/logs`, and
  `/api/channels/{encoded-id}/programmes?date=YYYY-MM-DD`.
- Write: `/api/refresh` with `{}`, `/api/settings` with
  `{refresh_time, auto_refresh}`. Both use `Content-Type: application/json`
  and `X-Requested-With: HomeCast`.
- Status polling: 5 seconds when idle, 2 seconds while refreshing; channel
  data reloads when `last_success` changes, at programme boundaries, or after
  a channel read failed. Slow guide/log requests do not delay status polling.
- Subscription dialog: absolute HTTP URLs with copy controls and optional downloads.
  Existing endpoints stay unchanged: `/m3u/xteve.m3u`, `/xmltv/xteve.xml`.
- Requests time out after 12 seconds. Guide selection cancels older requests.
  Existing channel data remains visible after a status connection failure.
- All server strings are inserted through `textContent`, not HTML parsing.

## Verification

From the repository root, with Playwright (or playwright-core) and Chrome
available:

```sh
node --check iptv_lan/static/app.js
node --test tests/frontend.test.cjs
```

The test uses Chromium request interception on the reserved `homecast.test`
hostname. It does not start an HTTP service or connect to an IPTV source.
Set `FRONTEND_BROWSER` to another installed Playwright Chromium channel as
needed. Optional `FRONTEND_SCREENSHOTS=1` writes synthetic-data screenshots
to `tests/frontend-*.png`; those are QA output, not production assets.

`tests/frontend-logo.ps1` reproduces the original raster logo on Windows.
Lucide provenance and license are in `vendor/`.
