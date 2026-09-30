"""Translation-only Python package."""
import os

# Some httpx versions parse a bracketed NO_PROXY IPv6 literal as a port.
for _key in ("NO_PROXY", "no_proxy"):
    if _key in os.environ:
        os.environ[_key] = ",".join(part.strip() for part in os.environ[_key].split(",")
                                   if part.strip() and part.strip() != "[::1]")
