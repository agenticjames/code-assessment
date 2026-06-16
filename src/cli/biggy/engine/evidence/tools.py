"""The agent's hands — read-only, source-attached evidence tools (LangChain ``@tool``).

Inc 0 ships three primitives. Each is closed over the ``Vault`` so it serves *time-scoped*
evidence, and every result carries its ``<path>:<line>`` provenance so citations are real by
construction. No "solve it" tool. Inc 1 adds ``get_topology`` / ``get_changes`` / ``get_metric``.
"""

from __future__ import annotations

from langchain_core.tools import BaseTool, tool

from biggy.engine.evidence.vault import Vault


def make_tools(vault: Vault) -> list[BaseTool]:
    """Build the tool list bound to one investigation's vault/window."""

    @tool
    def list_evidence() -> str:
        """List available evidence: live telemetry (logs, metrics, alerts, deploys, changes,
        captures — sliced to the incident window) and standing-world docs (topology, runbooks,
        ADRs). Call this FIRST to see what exists and the time ranges covered."""
        return vault.list_evidence()

    @tool
    def read_file(path: str) -> str:
        """Read one evidence file by path (e.g. 'telemetry/logs/redis.log' or
        'topology/services.yaml'). Telemetry is auto-sliced to the incident window. Returns
        line-numbered content; cite any fact you use as '<path>:<line>'."""
        return vault.read_evidence(path)

    @tool
    def search(keyword: str) -> str:
        """Search all in-window evidence for a keyword or phrase (case-insensitive). Returns
        matching lines as '<path>:<line>: <text>'. Use it to locate signals such as
        'max number of clients reached', a deploy id, or an error string."""
        return vault.search(keyword)

    return [list_evidence, read_file, search]
