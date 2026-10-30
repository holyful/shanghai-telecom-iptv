# Security

HomeCast is an unauthenticated trusted-LAN service. Do not expose its HTTP port
to the Internet, a public reverse proxy, untrusted guests or a shared network.
All allowed clients may change refresh settings. Network/Host checks and
cross-origin protections do not replace user authentication.

The service executes the installed `curl` binary without a shell, binds official
requests to the configured IPTV interface, and sends credentials only as part of
the operator login. Operator authentication may use cleartext HTTP on its IPTV
network. Interface isolation does not provide end-to-end encryption. Host-network
containers can reach host interfaces, so avoid running untrusted modifications.

Treat subscriber IDs, protocol SN, MAC, cookies, authentication responses and
captures as secrets. Never include them in public issues, pull requests,
screenshots or CI variables. Local `config.json` and `data/` are excluded from Git
and the Docker build context, but maintainers must still inspect every release.

Do not submit exploit details or credentials in a public issue. Use GitHub's
private vulnerability reporting when enabled; otherwise first open a minimal
issue requesting a private reporting channel without technical details or data.

Only the latest released version receives fixes. No permanent compatibility with
the operator's undocumented protocol or access to every listed channel is
guaranteed.
