"""Give every execution mode the same result type for the CLI.

The SDK hands back a `PipelexExecuteResult` from the blocking `execute` path and a
`RunResults` from the durable path — both already expose a resolved `.main_stuff`
(the main output's content, dug out of the working memory for you). `to_run_results`
just adapts the blocking result onto `RunResults` so every mode hands the CLI the same
type; from there, reading the output is simply `results.main_stuff`.
"""

from pipelex_sdk.execute_result import PipelexExecuteResult
from pipelex_sdk.runs import RunResults


def to_run_results(result: PipelexExecuteResult) -> RunResults:
    """Adapt a blocking `execute` result onto the lifecycle's `RunResults`, so both
    execution modes hand the CLI the same type.

    `.main_stuff` is already resolved by the SDK on either path (it raises
    `MissingMainStuffError` if a completed run named no main stuff), so there is no
    working-memory digging left to do here.
    """
    return RunResults(pipeline_run_id=result.pipeline_run_id, main_stuff=result.main_stuff)
