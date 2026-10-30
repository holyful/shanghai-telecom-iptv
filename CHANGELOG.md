# Changelog

## 0.2.0 - 2026-10-31

- Environment-only configuration with strict validation and safe startup errors,
  without additional JSON or secret-file configuration layers.
- Default Compose pulls the published image and keeps state in one data volume;
  source builds use a separate optional Compose override.
- Explicit environment schedule settings override persisted settings and are
  locked in the existing schedule UI.
- Subscription dialog shows and copies HTTP M3U/XMLTV URLs; file downloads are
  secondary actions. Existing client URLs and stream identities are unchanged.
- Shared-config container health check and real-container regression tests for
  direct environment configuration and persisted schedule settings.
- Deployment prerequisites, external udpxy setup, configuration precedence and
  migration documentation. No bundled udpxy or Docker administration panel.

## 0.1.0 - 2026-10-31

- Official Shanghai Telecom authentication and channel/EPG retrieval.
- Trusted-LAN channel browser, programme guide, refresh logs and scheduling.
- Atomic last-good cache, sparse-guide rejection and refresh concurrency guards.
- M3U/XMLTV exports, configurable legacy channel identity and udpxy redirects.
- Optional Jellyfin-specific group-prefixed names and ordered channel numbers,
  without changing existing clients' subscriptions or channel identities.
- Linux amd64 Docker deployment and GitHub Container Registry publication.
- Network prerequisites and account-discovery guide using fictional examples.

Limitations: no other operators, SSDP discovery, DRM bypass, transcoding,
recording, catch-up or user authentication. ARM deployment is not verified.
