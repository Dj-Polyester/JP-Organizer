from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from lxml import etree

logger = logging.getLogger(__name__)

JMDICT_GLOBS = ["*JMdict*", "*JMdict_e*", "*jmdict*"]
KANJIDIC_GLOBS = ["*kanjidic*", "*KANJIDIC*"]
SEARCH_DIRS = [
    Path.home(),
    Path.home() / "Downloads",
    Path.home() / "Documents",
    Path.home() / "Desktop",
    Path("/usr/share"),
    Path("/usr/local/share"),
    Path("/opt"),
]


def _run_rg(globs: list[str], dirs: list[Path]) -> list[str]:
    """Run ripgrep to find files matching globs in given directories."""
    results: set[str] = set()
    for directory in dirs:
        if not directory.exists():
            continue
        for glob in globs:
            try:
                proc = subprocess.run(
                    ["rg", "--files", "--glob", glob, str(directory)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if proc.returncode == 0:
                    for line in proc.stdout.strip().split("\n"):
                        line = line.strip()
                        if line and not line.endswith(".py"):
                            results.add(line)
            except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as exc:
                logger.debug("rg search failed for %s in %s: %s", glob, directory, exc)
                continue
    return sorted(results)


def _verify_jmdict(path: str) -> bool:
    """Check if file has JMdict root element."""
    try:
        with open(path, "rb") as f:
            context = etree.iterparse(f, events=("start",), tag="JMdict")
            for event, elem in context:
                return True
    except Exception:
        pass
    return False


def _verify_kanjidic(path: str) -> bool:
    """Check if file has kanjidic2 root element."""
    try:
        with open(path, "rb") as f:
            context = etree.iterparse(f, events=("start",), tag="kanjidic2")
            for event, elem in context:
                return True
    except Exception:
        pass
    return False


def discover_dictionaries() -> dict:
    """Discover JMdict and KANJIDIC XML files using ripgrep."""
    jmdict_candidates = _run_rg(JMDICT_GLOBS, SEARCH_DIRS)
    kanjidic_candidates = _run_rg(KANJIDIC_GLOBS, SEARCH_DIRS)

    jmdict_verified = [p for p in jmdict_candidates if _verify_jmdict(p)]
    kanjidic_verified = [p for p in kanjidic_candidates if _verify_kanjidic(p)]

    return {
        "jmdict": {
            "candidates": jmdict_candidates,
            "verified": jmdict_verified,
        },
        "kanjidic": {
            "candidates": kanjidic_candidates,
            "verified": kanjidic_verified,
        },
    }
