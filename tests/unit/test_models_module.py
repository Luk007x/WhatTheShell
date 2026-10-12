# SPDX-License-Identifier: AGPL-3.0-or-later
import pytest
from pydantic import ValidationError

from whattheshell.models.common import OptionSpec
from whattheshell.models.module import Module


def test_minimal_module() -> None:
    assert Module.model_validate({"schema_version": 1, "tool": "grep"}).override_mode == "merge"


def test_extra_field_rejected() -> None:
    with pytest.raises(ValidationError):
        Module.model_validate({"schema_version": 1, "tool": "grep", "tpyo": 1})


@pytest.mark.parametrize("path", ["../x", "/etc/x", "a/../../x", "", "."])
def test_fixture_path_rejected(path: str) -> None:
    doc = {"title": "t", "fixtures": [{"path": path}]}
    with pytest.raises(ValidationError):
        Module.model_validate({"schema_version": 1, "tool": "grep", "examples": [doc]})


def test_option_fields_set() -> None:
    spec = OptionSpec.model_validate({"id": "a", "label": "A"})
    assert spec.model_fields_set == {"id", "label"}


def _mod(**extra: object) -> dict[str, object]:
    return {"schema_version": 1, "tool": "grep", **extra}


@pytest.mark.parametrize("bad", ["", ".", "/etc/x", "../x"])
def test_template_workflow_path(bad: str) -> None:
    with pytest.raises(ValidationError):
        Module.model_validate(_mod(templates=[{"title": "t", "workflow": bad}]))


@pytest.mark.parametrize("tool", ["../x", "-x", "a/b"])
def test_tool_name(tool: str) -> None:
    with pytest.raises(ValidationError):
        Module.model_validate(_mod(tool=tool))


def test_bad_stdout_regex() -> None:
    ex = {"title": "t", "expect": {"stdout_regex": "("}}
    with pytest.raises(ValidationError, match="stdout_regex"):
        Module.model_validate(_mod(examples=[ex]))


def test_duplicate_ids_and_subcommands() -> None:
    dup = [{"id": "a"}, {"id": "a"}]
    with pytest.raises(ValidationError, match="mehrfach"):
        Module.model_validate(_mod(inputs=[{"id": "a"}], options=[{"id": "a"}]))
    with pytest.raises(ValidationError, match="mehrfach"):
        Module.model_validate(_mod(subcommands=[{"name": "c"}, {"name": "c"}]))
    with pytest.raises(ValidationError, match="mehrfach"):
        Module.model_validate(_mod(subcommands=[{"name": "c", "options": dup}]))
