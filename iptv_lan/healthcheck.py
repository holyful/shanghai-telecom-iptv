"""Container liveness check using the same configuration as the server."""

from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

from .config import ConfigError, load_config


def main():
    try:
        config = load_config()
        url = f'http://{config["bind_address"]}:{config["port"]}/health'
        with build_opener(ProxyHandler({})).open(url, timeout=3) as response:
            if response.status != 200:
                raise SystemExit(1)
    except (ConfigError, OSError, URLError):
        raise SystemExit('HomeCast health check failed') from None


if __name__ == '__main__':
    main()
