"""
DEAD AIR — the "there is a newer one" nudge.

PyPI does not push. A player who installed with pipx keeps whatever version
they installed until they run `pipx upgrade` themselves, and most never think
to. So once a day the game asks PyPI what the latest release is, writes the
answer to a file, and the next time the menu opens it reads that file and, if
the number on disk is behind, says so.

The ask happens on a background thread with a short timeout and every error
swallowed: a player with no network, or a slow one, or PyPI having a bad day,
must not notice any of it. The menu only ever reads the cached answer, so the
check never adds a frame of latency to startup.

Set DEADAIR_NO_UPDATE_CHECK to anything to turn the whole thing off.
"""

import json
import os
import threading
import time
import urllib.request
from importlib import metadata

from . import save

PYPI_JSON = "https://pypi.org/pypi/deadair/json"
CHECK_EVERY = 24 * 60 * 60        # seconds between asks
TIMEOUT = 3                       # seconds to wait on PyPI


def _cache_path():
    return save.state_root() / "deadair" / "update-check.json"


def installed_version():
    """What `deadair` currently is, or None when it is not installed at all.

    Running from a clone via ./play has no distribution metadata, and someone
    working from source does not need a package manager's opinion, so None is
    the right answer there too.
    """
    try:
        return metadata.version("deadair")
    except metadata.PackageNotFoundError:
        return None
    except Exception:
        return None


def _key(v):
    """A version string as a comparable tuple. Prereleases sort low."""
    try:
        from packaging.version import Version, InvalidVersion
        try:
            pv = Version(v)
        except InvalidVersion:
            return ()
        return (0 if pv.is_prerelease else 1, pv.release)
    except Exception:
        parts = []
        for chunk in v.replace("-", ".").split("."):
            if chunk.isdigit():
                parts.append(int(chunk))
            else:
                break
        return (1, tuple(parts))


def _is_newer(candidate, current):
    return bool(candidate) and _key(candidate) > _key(current)


def notice():
    """One line for the menu, or None. Reads only the cache — never the net."""
    current = installed_version()
    if current is None:
        return None
    try:
        data = json.loads(_cache_path().read_text())
        latest = data["latest"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not _is_newer(latest, current):
        return None
    return (f"A newer DEAD AIR is out — {current} → {latest}.  "
            f"Update with:  pipx upgrade deadair   "
            f"(or:  pip install -U deadair)")


def _fetch_latest():
    req = urllib.request.Request(
        PYPI_JSON, headers={"User-Agent": "deadair-update-check"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        payload = json.load(resp)
    releases = payload.get("releases", {})
    usable = [v for v, files in releases.items()
              if files and not all(f.get("yanked") for f in files)
              and _key(v) and _key(v)[0] == 1]
    if usable:
        return max(usable, key=_key)
    return payload["info"]["version"]


def refresh(force=False):
    """Ask PyPI and update the cache, unless the cache is still fresh.

    Every failure mode here — offline, DNS, timeout, PyPI 5xx, junk JSON,
    an unwritable state dir — ends the same way: quietly, with the player
    none the wiser.
    """
    path = _cache_path()
    if not force:
        try:
            seen = json.loads(path.read_text()).get("checked", 0)
            if time.time() - seen < CHECK_EVERY:
                return
        except (OSError, ValueError, AttributeError):
            pass
    try:
        latest = _fetch_latest()
    except Exception:
        latest = None
    record = {"checked": time.time(), "latest": latest}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".new")
        tmp.write_text(json.dumps(record))
        tmp.replace(path)
    except OSError:
        pass


def check_in_background():
    """Kick the once-a-day refresh onto a daemon thread and return at once."""
    if os.environ.get("DEADAIR_NO_UPDATE_CHECK"):
        return
    if installed_version() is None:
        return
    try:
        threading.Thread(target=refresh, name="deadair-update-check",
                         daemon=True).start()
    except Exception:
        pass
