# SPDX-License-Identifier: AGPL-3.0-or-later
import pytest

from whattheshell.engine import Context, StepOutput, TemplateError, render, render_value

CTX = Context(
    variables={"name": "x y"},
    results={"s1": StepOutput(stdout="a\nb\n", stderr="err", exit_code=3)},
    items={"item": "f.txt", "file": "f.txt"},
)


def test_references() -> None:
    assert render("{{ var.name }}|{{s1.stdout}}|{{s1.stderr}}|{{ s1.exit_code }}", CTX) == (
        "x y|a\nb\n|err|3"
    )
    assert render("{{s1.lines}}", CTX) == "a\nb"
    assert render("{{item}} {{file}}", CTX) == "f.txt f.txt"


def test_escape_and_no_code() -> None:
    assert render(r"docker --format '\{{.Names}}'", CTX) == "docker --format '{{.Names}}'"
    for bad in ["{{ var.name.upper() }}", "{{ 1+1 }}", "{{"]:
        with pytest.raises(TemplateError):
            render(bad, CTX)


@pytest.mark.parametrize("ref", ["var.nope", "zz.stdout", "s1.foo", "other"])
def test_unknown(ref: str) -> None:
    with pytest.raises(TemplateError, match=ref.split(".")[-1]):
        render("{{" + ref + "}}", CTX)


def test_item_outside_foreach() -> None:
    with pytest.raises(TemplateError, match="item"):
        render("{{item}}", Context({}, {}))


def test_render_value() -> None:
    assert render_value({"a": ["{{var.name}}", 1, None]}, CTX) == {"a": ["x y", 1, None]}


def test_keep_unknown() -> None:
    assert render("{{ var.name }}/{{ s9.stdout }}/\\{{ x }}/{{", CTX, keep_unknown=True) == (
        "x y/{{ s9.stdout }}/{{ x }}/{{"
    )
    with pytest.raises(TemplateError):
        render("{{ s9.stdout }}", CTX)
