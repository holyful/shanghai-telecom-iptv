# Implementation Scope

Approved scope: a standalone Docker app on the router, replacing xTeVe while
preserving M3U/XMLTV subscription paths and port. Shanghai Telecom only. No login
for trusted-LAN use; reject untrusted clients and cross-origin mutations. Config
contains subscriber identity and must never be published. UDPxy remains the video
transport. The UI browses real channels and programmes, refresh status and history.

- [x] Tested official client: interface binding, HTML forms, fresh authentication,
      GB18030 responses, metadata and programme extraction, bounded failures.
- [x] Tested atomic snapshots, one refresh at a time, persisted daily schedule,
      last-good cache, sanitised public APIs and legacy compatibility.
- [x] UI: responsive channel list, guide, logs and manual refresh.
- [ ] Staging live refresh, desktop/mobile UI checks and stream test.
- [ ] Backup and cutover; legacy endpoint and Jellyfin verification, rollback.
- [ ] Public README, configuration and account-discovery guide; secret scan of
      all committed files/history before creating/pushing public GitHub repo.

Tests use synthetic identities and example addresses only. No household evidence
or configuration belongs in this repository. Backend and frontend are separate
implementation tasks with a fixed HTTP contract. No general workflow platform.

Review fixes: status-volume write failure no longer locks the refresh state;
incomplete future EPG cannot replace a healthy snapshot; a scheduled refresh
rejected by the cooldown remains due. Regression tests cover all three cases.
Python package data includes vendored icon assets and licenses. Explicit host
aliases preserve LAN DNS subscriptions while unknown Host values remain denied.
