"""The drift guard for the full demo matrix.

Every demo exists in every mode group, with the same arguments — that symmetry is
the pedagogy (diff two mode files and only the lifecycle helper differs), and the
duplication it implies is exactly what drifts. A demo added to one mode and
forgotten in another fails here.
"""

import inspect

import typer

from piper.attended.cli import app as attended_app
from piper.blocking.cli import app as blocking_app
from piper.cli import app as root_app
from piper.detached.cli import app as detached_app

MODE_APPS = {"blocking": blocking_app, "attended": attended_app, "detached": detached_app}
DEMO_COMMANDS = {"extract-entities", "summarize-pdf", "generate-image"}
LIFECYCLE_COMMANDS = {"wait", "status", "result"}


def _command_names(mode_app: typer.Typer) -> set[str]:
    return {command.name for command in mode_app.registered_commands if command.name is not None}


def _demo_signatures(mode_app: typer.Typer) -> dict[str, list[str]]:
    signatures: dict[str, list[str]] = {}
    for command in mode_app.registered_commands:
        if command.name in DEMO_COMMANDS and command.callback is not None:
            signatures[command.name] = list(inspect.signature(command.callback).parameters)
    return signatures


class TestModeSymmetry:
    def test_every_mode_exposes_every_demo(self):
        assert _command_names(blocking_app) == DEMO_COMMANDS
        assert _command_names(attended_app) == DEMO_COMMANDS
        # Detached owns the run-lifecycle commands on top of the demos — nobody else has them.
        assert _command_names(detached_app) == DEMO_COMMANDS | LIFECYCLE_COMMANDS

    def test_the_demos_take_the_same_arguments_in_every_mode(self):
        blocking_signatures = _demo_signatures(blocking_app)
        assert set(blocking_signatures) == DEMO_COMMANDS
        assert _demo_signatures(attended_app) == blocking_signatures
        assert _demo_signatures(detached_app) == blocking_signatures

    def test_the_root_app_mounts_the_modes_in_reading_order(self):
        mounted = [group.name for group in root_app.registered_groups if group.name in MODE_APPS]
        assert mounted == ["blocking", "attended", "detached"]
