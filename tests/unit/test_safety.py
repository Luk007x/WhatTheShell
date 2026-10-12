# SPDX-License-Identifier: AGPL-3.0-or-later
from whattheshell.models.catalog import CommandSpec
from whattheshell.models.common import InputSpec, OptionSpec, Safety
from whattheshell.safety import Verdict, classify_command, needs_confirmation, summarize


def _opt(id_: str, *flags: str, safety: Safety | None = None) -> OptionSpec:
    return OptionSpec(id=id_, flags=list(flags), safety=safety)


def _spec(name: str, *options: OptionSpec, safety: Safety = Safety.safe) -> CommandSpec:
    return CommandSpec(name=[name], options=list(options), safety=safety)


def test_rm_dangerous_with_both_reasons() -> None:
    spec = _spec("rm", _opt("recursive", "-r"), _opt("force", "-f"))
    verdict = classify_command(spec, {"recursive": True, "force": True})
    assert verdict.safety is Safety.dangerous
    assert "Option -r" in verdict.reasons
    assert "Option -f" in verdict.reasons
    assert classify_command(_spec("rm"), {}).safety is Safety.dangerous


def test_safe_and_caution_tools() -> None:
    assert classify_command(_spec("ls"), {}) == Verdict(Safety.safe, ())
    assert classify_command(_spec("cp"), {}).safety is Safety.caution
    assert classify_command(_spec("/usr/bin/mkfs.ext4"), {}).safety is Safety.dangerous


def test_sed_in_place() -> None:
    spec = _spec("sed", _opt("in_place", "-i", "--in-place"))
    assert classify_command(spec, {}).safety is Safety.safe
    assert classify_command(spec, {"in_place": False}).safety is Safety.safe
    assert classify_command(spec, {"in_place": True}).safety is Safety.dangerous


def test_grep_ignore_case_stays_safe() -> None:
    assert classify_command(_spec("grep", _opt("i", "-i")), {"i": True}).safety is Safety.safe


def test_find_delete() -> None:
    spec = _spec("find", _opt("delete", "-delete"))
    assert classify_command(spec, {"delete": True}).safety is Safety.dangerous
    assert classify_command(spec, {}).safety is Safety.safe


def test_chmod_recursive() -> None:
    spec = _spec("chmod", _opt("recursive", "-R", "--recursive"))
    assert classify_command(spec, {}).safety is Safety.caution
    assert classify_command(spec, {"recursive": True}).safety is Safety.dangerous


def test_systemctl() -> None:
    spec = CommandSpec(name=["systemctl"], inputs=[InputSpec(id="action")])
    assert classify_command(spec, {"action": "status"}).safety is Safety.safe
    assert classify_command(spec, {"action": "poweroff"}).safety is Safety.dangerous
    assert classify_command(spec, {}, ["reboot"]).safety is Safety.dangerous
    sub = CommandSpec(name=["systemctl", "poweroff"])
    assert classify_command(sub, {}).safety is Safety.dangerous
    assert classify_command(
        sub.model_copy(update={"name": ["systemctl", "status"]}), {}
    ).safety is (Safety.safe)


def test_module_option_safety_raises() -> None:
    spec = _spec("mytool", _opt("wipe", "--wipe", safety=Safety.dangerous))
    assert classify_command(spec, {"wipe": True}).safety is Safety.dangerous
    assert classify_command(spec, {}).safety is Safety.safe


def test_unknown_tool_keeps_base() -> None:
    assert classify_command(_spec("mytool", safety=Safety.caution), {}).safety is Safety.caution


def test_extra_args() -> None:
    assert classify_command(_spec("rsync"), {}, ["--delete"]).safety is Safety.dangerous
    assert classify_command(_spec("rsync"), {}, ["-v"]).safety is Safety.caution
    assert classify_command(_spec("ls"), {}, ["--delete"]).safety is Safety.dangerous


def test_summarize_and_confirmation() -> None:
    safe, danger = Verdict(Safety.safe, ()), Verdict(Safety.dangerous, ("x",))
    assert summarize([]) is Safety.safe
    assert summarize([("a", safe), ("b", danger)]) is Safety.dangerous
    assert [needs_confirmation(s) for s in Safety] == [False, True, True]


def test_flag_variants_and_new_tools() -> None:
    def run(name: str, *extra: str) -> Safety:
        return classify_command(_spec(name), {}, extra).safety

    assert run("find", ".", "-execdir", "x", ";") is Safety.dangerous
    assert run("find", ".", "-fprint", "out") is Safety.dangerous
    assert run("sed", "-i.bak", "s/a/b/", "f") is Safety.dangerous
    assert run("sed", "s/a/b/", "f") is Safety.safe
    assert run("rsync", "--delete=x") is Safety.dangerous
    assert run("timeout", "5", "rm") is Safety.caution
    assert run("awk") is Safety.caution
