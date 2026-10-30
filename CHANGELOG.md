# Changelog

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
