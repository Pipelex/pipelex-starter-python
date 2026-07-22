"""Read and print what a run consumed — shared by every execution mode.

Cost reporting is orthogonal to *how* a run is executed, so — like input encoding
(`piper/inputs.py`) and error presentation (`piper/errors.py`) — it lives here rather
than in one of the mode packages.

Two responsibilities:

- **Reading usage off an SDK result.** The durable modes (`attended`, `detached`) get a
  typed `RunResults.tokens_usages`; the blocking mode's `client.execute` result carries
  the same records only raw in `pipe_output.model_extra`, so `usage_from_execute` lifts
  and validates them by hand. Both `usage_from_results` and `usage_from_execute` return a
  `RunUsage`, so a mode reads cost the same way regardless of which result it holds. (When
  `wip/sdk-qol/typed-tokens-usages-on-execute.md` lands upstream, `usage_from_execute`
  collapses to `result.tokens_usages`.)
- **Printing a cost report.** `print_cost_report` renders a compact per-call table plus a
  USD total — always to *stderr*, so stdout stays the clean, pipeable result.

The SDK's documented usage semantics are respected here: `cost is None` (no rate table —
mock / own-GPU / dry-run) is distinct from `cost == 0` (priced at zero); a `None` record
list (usage off, broken, or pre-artifact) is distinct from `[]` (ran, no inference);
`usage_assembly_error` is the only signal that separates "broke" from "off"; and token
categories are never summed (`input_cached` is a subset of `input`).
"""

from typing import NamedTuple

from pipelex_sdk.execute_result import PipelexExecuteResult
from pipelex_sdk.runs import RunResults, TokensUsageRecord
from rich.console import Console
from rich.table import Table


class RunUsage(NamedTuple):
    """A run's per-call usage records, normalized across execution modes.

    Mirrors the `RunResults` usage pair so a caller reads cost the same way whichever mode
    ran: `tokens_usages` is `None` when usage assembly produced no list (off / broke /
    pre-artifact) and `[]` when it ran with no inference; `usage_assembly_error` is the only
    field that tells the "broke" case apart from the other two.
    """

    tokens_usages: list[TokensUsageRecord] | None
    usage_assembly_error: str | None


def usage_from_results(results: RunResults) -> RunUsage:
    """Read the usage pair off a durable `RunResults` (attended / detached) — already typed."""
    return RunUsage(tokens_usages=results.tokens_usages, usage_assembly_error=results.usage_assembly_error)


def usage_from_execute(result: PipelexExecuteResult) -> RunUsage:
    """Lift the usage pair off a blocking `execute` result.

    Unlike `RunResults`, `PipelexExecuteResult` does not surface usage typed yet: the records
    ride the execute response's extension-open `pipe_output` as raw dicts, so we read them from
    `model_extra` and validate them into `TokensUsageRecord`s ourselves (mirroring the SDK's own
    `_map_run_result_to_run_results`). When the typed-usage-on-execute follow-up lands
    (`wip/sdk-qol/typed-tokens-usages-on-execute.md`), this collapses to `result.tokens_usages`.
    """
    extras = result.pipe_output.model_extra or {}
    raw = extras.get("tokens_usages")
    records = [TokensUsageRecord.model_validate(item) for item in raw] if raw is not None else None
    return RunUsage(tokens_usages=records, usage_assembly_error=extras.get("usage_assembly_error"))


def print_cost_report(console: Console, usage: RunUsage) -> None:
    """Print a run's cost report to `console` (always stderr, so stdout stays the pipeable result).

    Renders a per-call table (pipe, model, tokens in→out, USD cost) and a total. The three
    "no records" cases each get their own one-line note rather than an empty table: a failed
    assembly, no usage reported (off / pre-artifact), and no inference calls.
    """
    if usage.usage_assembly_error is not None:
        console.print(f"[dim]Cost report unavailable — usage assembly failed: {usage.usage_assembly_error}[/dim]")
        return
    records = usage.tokens_usages
    if records is None:
        console.print("[dim]No usage was reported for this run.[/dim]")
        return
    if not records:
        console.print("[dim]No inference calls — nothing to cost.[/dim]")
        return

    table = Table(title="Cost report", title_justify="left", title_style="bold", show_edge=False, pad_edge=False)
    table.add_column("pipe", style="cyan")
    table.add_column("model")
    table.add_column("tokens (in→out)", justify="right")
    table.add_column("cost (USD)", justify="right")

    priced_total = 0.0
    unpriced = 0
    for record in records:
        tokens = record.nb_tokens_by_category or {}
        # `input` is the joined total and `output` the generated tokens — never sum the categories.
        tokens_str = f"{tokens.get('input', 0)}→{tokens.get('output', 0)}"
        if record.cost is None:
            unpriced += 1
            cost_str = "—"
        else:
            priced_total += record.cost
            cost_str = f"${record.cost:.4f}"
        model = record.inference_model_name or record.model_type or "—"
        table.add_row(record.pipe_code or "—", model, tokens_str, cost_str)

    console.print(table)
    total = f"[bold]Total: ${priced_total:.4f}[/bold]"
    if unpriced:
        total += f" [dim](+{unpriced} unpriced: mock / own-GPU / dry-run)[/dim]"
    console.print(total)
