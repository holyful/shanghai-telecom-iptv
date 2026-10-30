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
screenshots or CI variables. Deploy from a private directory: a filled-in
`compose.yaml` contains credentials and must never be committed over the public
example. Environment variables are visible to Docker administrators via inspect
and are not encrypted secret storage.
Never publish `docker compose config` output from a real deployment. Keep secrets
out of image build arguments and layers. The image copies only application files;
maintainers must still inspect every release and its reachable Git history.

Do not submit exploit details or credentials in a public issue. Use GitHub's
private vulnerability reporting when enabled; otherwise first open a minimal
issue requesting a private reporting channel without technical details or data.

Only the latest released version receives fixes. No permanent compatibility with
the operator's undocumented protocol or access to every listed channel is
guaranteed.
