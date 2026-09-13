"""Offline gates for the `make add-method` scaffolder (`scripts/add_method.py`).

Everything here runs with no API key and no network: the scaffolder's read-only half is pure
derivation from a validate report, and the report is built here rather than fetched. What is
deliberately NOT stubbed is the three mode files — `insert_into_mode_file` is exercised against
the real `piper/<mode>/cli.py`, so a template edit that loses an anchor, renames a lifecycle
helper's parameters or breaks the first-party import block fails this suite rather than the next
person's scaffold run.

The emitted command is checked by compiling it. A scaffolder whose output does not parse is the
one failure a starter cannot afford, and `compile()` catches it without a key, a network or an
installed method.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from mthds.protocol.input_form import (
    BooleanField,
    DocumentField,
    EnumField,
    ImageField,
    InputFormField,
    ListField,
    NumberField,
    ObjectField,
    PipeInputFormDescriptor,
    TextField,
    TextItem,
)
from mthds.protocol.pipe_io_contracts import IOMultiplicity, PipeIOContract, PipeOutputContract, PresenceMarker
from pipelex_sdk.validation_models import PipelexValidationReport

ROOT = Path(__file__).resolve().parents[2]
MODE_FILES = {mode: ROOT / "piper" / mode / "cli.py" for mode in ("blocking", "attended", "detached")}

PIPE_REF = "stats.analyze_text"
ADDRESS = "github.com/Pipelex/methods/text_stats@v0.1.1"


def load_add_method() -> Any:
    """Import the scaffolder the way `python -m scripts.add_method` does.

    The repository root goes on the path first: the scaffolder imports `scripts.codegen`, which
    is how the two scripts share the manifest format instead of each carrying a copy of it.
    """
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    return importlib.import_module("scripts.add_method")


add_method = load_add_method()


def build_report(
    *,
    fields: Sequence[InputFormField] | None = None,
    pipes: dict[str, str] | None = None,
    default_pipe_ref: str | None = PIPE_REF,
    multiplicity: IOMultiplicity = IOMultiplicity.SINGLE,
) -> PipelexValidationReport:
    """A valid report shaped like the one `POST /v1/validate` returns for a runnable method."""
    declared = pipes or {PIPE_REF: "stats.TextStats"}
    contracts = {
        pipe_ref: PipeIOContract(
            inputs={},
            output=PipeOutputContract(concept_ref=concept_ref, multiplicity=multiplicity, item_count=None, optional=False, json_schema={}),
        )
        for pipe_ref, concept_ref in declared.items()
    }
    form = {pipe_ref: PipeInputFormDescriptor(fields=list(fields) if fields is not None else []) for pipe_ref in declared}
    return PipelexValidationReport(is_valid=True, pipe_io_contracts=contracts, default_pipe_ref=default_pipe_ref, input_form=form)


def text_field(*, name: str = "text", required: bool = True) -> TextField:
    presence = PresenceMarker.PLAIN if required else PresenceMarker.OPTIONAL
    return TextField(name=name, required=required, presence=presence, gating=required, description="The text to analyze.")


def build_plan(
    *, mode: str = "attended", multiplicity: IOMultiplicity = IOMultiplicity.SINGLE, fields: Sequence[InputFormField] | None = None
) -> Any:
    report = build_report(fields=fields if fields is not None else [text_field()], multiplicity=multiplicity)
    selector = add_method.parse_selector(ADDRESS)
    return add_method.build_plan(report=report, selector=selector, slug="text-stats", mode=mode, requested_pipe=None)


class TestAddMethod:
    @pytest.mark.parametrize("mode", sorted(MODE_FILES))
    def test_every_mode_file_carries_both_anchors(self, mode: str):
        text = MODE_FILES[mode].read_text()
        assert add_method.IMPORT_ANCHOR in text
        assert add_method.COMMAND_ANCHOR in text

    @pytest.mark.parametrize("mode", sorted(MODE_FILES))
    def test_every_mode_file_declares_the_helper_the_scaffolder_calls(self, mode: str):
        """The emitted command calls the mode's lifecycle helper by name, with a selector.

        A helper renamed, or one that stopped taking `method_id` / `method_ref`, would make every
        scaffolded command a `NameError` or a `TypeError` at run time — caught here instead.
        """
        text = MODE_FILES[mode].read_text()
        assert f"async def {add_method.MODE_HELPERS[mode]}(" in text
        assert "method_id: str | None = None" in text
        assert "method_ref: str | None = None" in text

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("github.com/Pipelex/methods/text_stats@v0.1.1", "github.com/Pipelex/methods/text_stats@v0.1.1"),
            ("https://github.com/Pipelex/methods/text_stats@v0.1.1", "github.com/Pipelex/methods/text_stats@v0.1.1"),
            ("github.com/Pipelex/methods/text_stats", "github.com/Pipelex/methods/text_stats"),
            ("github.com/Pipelex/methods", "github.com/Pipelex/methods"),
        ],
    )
    def test_an_address_is_normalized_to_its_bare_form(self, raw: str, expected: str):
        selector = add_method.parse_selector(raw)
        assert selector.method_ref == expected
        assert selector.method_id is None

    def test_a_catalog_id_is_sent_as_method_id(self):
        selector = add_method.parse_selector("mt_abc123")
        assert selector.method_id == "mt_abc123"
        assert selector.method_ref is None

    @pytest.mark.parametrize("raw", ["piper/methods/text-stats", "./main.mthds", "gitlab.com/owner/repo", "mt_", ""])
    def test_anything_else_is_refused(self, raw: str):
        with pytest.raises(add_method.Refusal):
            add_method.parse_selector(raw)

    def test_an_address_names_the_slug_and_a_catalog_id_does_not(self):
        assert add_method.slug_from_selector(add_method.parse_selector(ADDRESS)) == "text-stats"
        with pytest.raises(add_method.Refusal, match="NAME"):
            add_method.slug_from_selector(add_method.parse_selector("mt_abc123"))

    @pytest.mark.parametrize(("raw", "slug"), [("text_stats", "text-stats"), ("CV screening", "cv-screening"), ("InvoiceTriage", "invoice-triage")])
    def test_a_name_is_kebab_cased(self, raw: str, slug: str):
        assert add_method.kebab_case(raw) == slug

    def test_every_name_derives_from_the_slug(self):
        names = add_method.derive_names("text-stats")
        assert names == ("text-stats", "text_stats", "text_stats", "TextStatsOutput")

    @pytest.mark.parametrize("slug", ["", "Text-Stats", "text--stats", "-text", "text stats"])
    def test_a_slug_that_cannot_be_a_directory_and_a_package_is_refused(self, slug: str):
        with pytest.raises(add_method.Refusal):
            add_method.derive_names(slug)

    def test_the_requested_pipe_wins_bare_or_qualified(self):
        report = build_report()
        assert add_method.choose_pipe(report=report, requested="analyze_text") == PIPE_REF
        assert add_method.choose_pipe(report=report, requested=PIPE_REF) == PIPE_REF

    def test_the_default_pipe_is_next(self):
        report = build_report(pipes={PIPE_REF: "stats.TextStats", "stats.other": "stats.Other"})
        assert add_method.choose_pipe(report=report, requested=None) == PIPE_REF

    def test_a_lone_pipe_is_taken_without_a_default(self):
        report = build_report(default_pipe_ref=None)
        assert add_method.choose_pipe(report=report, requested=None) == PIPE_REF

    def test_several_pipes_and_no_default_is_a_refusal_listing_them(self):
        report = build_report(pipes={PIPE_REF: "stats.TextStats", "stats.other": "stats.Other"}, default_pipe_ref=None)
        with pytest.raises(add_method.Refusal, match="stats.other"):
            add_method.choose_pipe(report=report, requested=None)

    def test_an_unknown_pipe_is_a_refusal_listing_what_the_method_declares(self):
        with pytest.raises(add_method.Refusal, match=PIPE_REF):
            add_method.choose_pipe(report=build_report(), requested="nope")

    def test_an_ambiguous_bare_code_is_a_refusal(self):
        report = build_report(pipes={"one.run": "one.Out", "two.run": "two.Out"}, default_pipe_ref=None)
        with pytest.raises(add_method.Refusal, match="ambiguous"):
            add_method.choose_pipe(report=report, requested="run")

    def test_required_inputs_come_before_optional_ones(self):
        """Forced by Python, not by taste: a parameter with no default cannot follow one with one."""
        fields = [text_field(name="note", required=False), text_field(name="text", required=True)]
        parameters = add_method.build_parameters(report=build_report(fields=fields), pipe_ref=PIPE_REF)
        assert [parameter.name for parameter in parameters] == ["text", "note"]

    def test_a_required_scalar_is_an_argument_and_an_optional_one_is_an_option(self):
        fields = [text_field(name="text", required=True), text_field(name="note", required=False)]
        parameters = add_method.build_parameters(report=build_report(fields=fields), pipe_ref=PIPE_REF)
        assert "typer.Argument(" in parameters[0].declaration
        assert 'typer.Option("--note"' in parameters[1].declaration
        assert parameters[1].declaration.endswith("= None,")

    def test_a_number_is_typed_by_what_the_method_says_it_is(self):
        integer = NumberField(name="top_n", required=True, presence=PresenceMarker.PLAIN, gating=True, integer=True)
        decimal = NumberField(name="ratio", required=True, presence=PresenceMarker.PLAIN, gating=True, integer=False)
        parameters = add_method.build_parameters(report=build_report(fields=[integer, decimal]), pipe_ref=PIPE_REF)
        assert [parameter.annotation for parameter in parameters] == ["int", "float"]

    def test_a_boolean_is_a_flag_pair_never_a_positional(self):
        field = BooleanField(name="strict", required=True, presence=PresenceMarker.PLAIN, gating=True)
        parameter = add_method.build_parameters(report=build_report(fields=[field]), pipe_ref=PIPE_REF)[0]
        assert '"--strict/--no-strict"' in parameter.declaration
        assert "typer.Argument(" not in parameter.declaration

    def test_an_enum_lists_its_choices_in_the_help(self):
        field = EnumField(name="tone", required=True, presence=PresenceMarker.PLAIN, gating=True, choices=["terse", "warm"])
        parameter = add_method.build_parameters(report=build_report(fields=[field]), pipe_ref=PIPE_REF)[0]
        assert "terse, warm" in parameter.declaration

    def test_a_document_is_uploaded_before_the_run(self):
        field = DocumentField(name="invoice", required=True, presence=PresenceMarker.PLAIN, gating=True)
        parameter = add_method.build_parameters(report=build_report(fields=[field]), pipe_ref=PIPE_REF)[0]
        assert "exists=True" in parameter.declaration
        assert parameter.assignment == ['    run_inputs["invoice"] = _run(upload_document_input(invoice))']

    @pytest.mark.parametrize(
        "field",
        [
            ObjectField(name="packet", required=True, presence=PresenceMarker.PLAIN, gating=True, fields=[]),
            ListField(name="items", required=True, presence=PresenceMarker.PLAIN, gating=True, item=TextItem(required=True)),
            ImageField(name="photo", required=True, presence=PresenceMarker.PLAIN, gating=True),
        ],
    )
    def test_an_input_with_no_honest_command_line_spelling_is_refused(self, field: InputFormField):
        """Refused, not guessed at. A JSON-encoded flag would be a hand-written input shape."""
        with pytest.raises(add_method.Refusal, match=field.name):
            add_method.build_parameters(report=build_report(fields=[field]), pipe_ref=PIPE_REF)

    def test_a_method_with_no_input_form_is_refused(self):
        report = build_report()
        report.input_form = None
        with pytest.raises(add_method.Refusal, match="input form"):
            add_method.build_parameters(report=report, pipe_ref=PIPE_REF)

    @pytest.mark.parametrize("mode", sorted(MODE_FILES))
    def test_the_emitted_command_parses(self, mode: str):
        compile(add_method.build_command_source(build_plan(mode=mode)), "<emitted>", "exec")

    def test_it_sends_the_selector_and_the_bare_pipe_code(self):
        source = add_method.build_command_source(build_plan())
        assert f'method_ref="{ADDRESS}"' in source
        assert 'pipe_code="analyze_text"' in source
        assert "mthds_contents" not in source

    def test_a_catalog_id_slice_sends_method_id(self):
        report = build_report(fields=[text_field()])
        plan = add_method.build_plan(
            report=report,
            selector=add_method.parse_selector("mt_abc123"),
            slug="text-stats",
            mode="attended",
            requested_pipe=None,
        )
        assert 'method_id="mt_abc123"' in add_method.build_command_source(plan)

    def test_a_single_output_narrows_into_the_generated_model(self):
        plan = build_plan()
        source = add_method.build_command_source(plan)
        assert "TextStatsOutput.model_validate(main_stuff)" in source
        assert add_method.import_lines(plan) == ["from piper.generated.text_stats.models import TextStats as TextStatsOutput"]

    def test_a_plural_output_goes_through_the_list_reader(self):
        """A plural output arrives as a bare array or an `items` envelope depending on the path."""
        plan = build_plan(multiplicity=IOMultiplicity.VARIABLE)
        source = add_method.build_command_source(plan)
        assert "list_items(main_stuff)" in source
        assert "from piper.outputs import list_items" in add_method.import_lines(plan)

    def test_detached_prints_the_run_id_and_narrows_nothing(self):
        """Consistent with detached's own demos: at start time there is no result to narrow."""
        plan = build_plan(mode="detached")
        source = add_method.build_command_source(plan)
        assert "_print_run_id(run_id)" in source
        assert "model_validate" not in source
        assert add_method.import_lines(plan) == []

    @pytest.mark.parametrize("mode", sorted(MODE_FILES))
    def test_the_slice_lands_in_the_real_mode_file_and_still_parses(self, mode: str):
        plan = build_plan(mode=mode)
        merged = add_method.insert_into_mode_file(
            text=MODE_FILES[mode].read_text(),
            imports=add_method.import_lines(plan),
            command_source=add_method.build_command_source(plan),
        )
        compile(merged, "<merged>", "exec")
        assert '@app.command(name="text-stats")' in merged

    def test_the_import_lands_in_sorted_position(self):
        """Sorted on insertion rather than fixed up afterwards, so `ruff check` stays green."""
        plan = build_plan(multiplicity=IOMultiplicity.VARIABLE)
        merged = add_method.insert_into_mode_file(
            text=MODE_FILES["attended"].read_text(),
            imports=add_method.import_lines(plan),
            command_source=add_method.build_command_source(plan),
        )
        first_party = [line for line in merged.splitlines() if line.startswith("from piper.")]
        assert first_party == sorted(first_party)
        assert "from piper.generated.text_stats.models import TextStats as TextStatsOutput" in first_party

    def test_a_mode_file_that_lost_an_anchor_is_refused(self):
        plan = build_plan()
        stripped = MODE_FILES["attended"].read_text().replace(add_method.COMMAND_ANCHOR, "# gone")
        with pytest.raises(add_method.Refusal, match="anchor"):
            add_method.insert_into_mode_file(text=stripped, imports=[], command_source=add_method.build_command_source(plan))

    @pytest.mark.parametrize(
        ("advertised", "selector_raw"),
        [(["runs", "method_id"], "mt_abc123"), (["runs", "method_ref"], ADDRESS), (["method_id", "method_ref"], ADDRESS)],
    )
    def test_an_advertised_selector_proceeds(self, advertised: list[str], selector_raw: str):
        selector = add_method.parse_selector(selector_raw)
        assert add_method.unsupported_selector_reason(base_url="https://api.example.com", advertised=advertised, selector=selector) is None

    def test_a_selector_the_deployment_does_not_advertise_is_refused_naming_both(self):
        """Measured against production on 2026-09-13: it advertises `runs` and `method_id` only."""
        selector = add_method.parse_selector(ADDRESS)
        reason = add_method.unsupported_selector_reason(base_url="https://api.example.com", advertised=["runs", "method_id"], selector=selector)
        assert reason is not None
        assert "method_ref" in reason
        assert "https://api.example.com" in reason

    def test_a_deployment_that_advertises_nothing_proceeds(self):
        """An empty handshake is "no verdict", never "supports nothing" — the real call answers."""
        selector = add_method.parse_selector(ADDRESS)
        assert add_method.unsupported_selector_reason(base_url="https://api.example.com", advertised=[], selector=selector) is None

    def test_a_name_already_on_disk_is_refused(self):
        """One-shot on purpose: `make codegen` is the refresh, and the command files are yours."""
        report = build_report(fields=[text_field()])
        with pytest.raises(add_method.Refusal, match="already exists"):
            add_method.build_plan(
                report=report,
                selector=add_method.parse_selector(ADDRESS),
                slug="extract-entities",
                mode="attended",
                requested_pipe=None,
            )
