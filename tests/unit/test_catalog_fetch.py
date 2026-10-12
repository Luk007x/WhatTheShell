# SPDX-License-Identifier: AGPL-3.0-or-later
"""clean_text and fetch_help (with throw-away shell scripts, no real tools)."""

import stat
from pathlib import Path

from whattheshell.catalog.fetch import HelpText, fetch_help
from whattheshell.helpparse import clean_text

HELP_SCRIPT = '#!/bin/sh\necho "Usage: x [-a]"\necho "  -a  all"\necho "  -b  bee"\n'


def make_script(directory: Path, name: str, body: str) -> str:
    path = directory / name
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


def test_clean_text_strips_ansi() -> None:
    assert clean_text("\x1b[1mBold\x1b[0m \x1b[31mred\x1b[0m") == "Bold red"


def test_clean_text_overstrike() -> None:
    assert clean_text("N\bNA\bAM\bME\bE _\bx") == "NAME x"


def test_clean_text_whitespace() -> None:
    assert clean_text("a\r\nb\rc\n\tx  \n") == "a\nbc\n        x\n"


def test_fetch_help_prefers_dash_dash_help(tmp_path: Path) -> None:
    result = fetch_help(make_script(tmp_path, "tool", HELP_SCRIPT))
    assert result == HelpText(
        text="Usage: x [-a]\n  -a  all\n  -b  bee\n", source="help", exit_code=0
    )


def test_fetch_help_falls_back_to_h_and_stderr(tmp_path: Path) -> None:
    body = (
        '#!/bin/sh\n[ "$1" = "-h" ] || { echo nope >&2; exit 2; }\n'
        'echo "usage: x" >&2\necho "  -a  all" >&2\necho "  -b  bee" >&2\nexit 3\n'
    )
    result = fetch_help(make_script(tmp_path, "tool", body))
    assert result is not None
    assert (result.source, result.exit_code) == ("h", 3)
    assert result.text.startswith("usage: x")


def test_fetch_help_passes_subcommand_and_sets_environment(tmp_path: Path) -> None:
    body = '#!/bin/sh\necho "Usage: $1 $2 $LC_ALL $COLUMNS"\necho "  -a  all"\necho "  -b  bee"\n'
    result = fetch_help(make_script(tmp_path, "tool", body), ["sub"])
    assert result is not None
    assert result.text.startswith("Usage: sub --help C 80")


def test_fetch_help_rejects_non_help_output(tmp_path: Path) -> None:
    body = "#!/bin/sh\necho one\necho two\necho three\n"
    assert fetch_help(make_script(tmp_path, "tool", body), ["sub"]) is None


def test_fetch_help_timeout(tmp_path: Path) -> None:
    script = make_script(tmp_path, "slow", "#!/bin/sh\nexec sleep 5\n")
    assert fetch_help(script, ["sub"], timeout=0.2) is None


def test_fetch_help_truncates_output(tmp_path: Path) -> None:
    body = '#!/bin/sh\necho "Usage: x"\nyes "  -a  all" | head -n 1000\n'
    result = fetch_help(make_script(tmp_path, "tool", body), max_bytes=100)
    assert result is not None
    assert len(result.text) <= 100


def test_fetch_help_denylist(tmp_path: Path) -> None:
    assert fetch_help(make_script(tmp_path, "reboot", HELP_SCRIPT)) is None


def test_fetch_help_not_executable(tmp_path: Path) -> None:
    path = tmp_path / "plain"
    path.write_text(HELP_SCRIPT)
    assert fetch_help(str(path)) is None
    assert fetch_help(str(tmp_path / "missing")) is None
