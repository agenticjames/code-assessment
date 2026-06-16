"""The agent's hands — read-only, source-attached evidence tools (LangChain ``@tool``).

Two kinds, mirroring the data: **raw** tools for unstructured text (``read_file`` / ``search`` over
logs) and **structured** tools for structured data (``get_topology`` / ``get_changes`` /
``get_metric``). Each is closed over the ``Vault`` so it serves *time-scoped* evidence, and every
result carries its ``<path>:<line>`` provenance so citations are real by construction. No "solve it" tool.
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

    @tool
    def get_topology(service: str) -> str:
        """Look up a service in the dependency graph: its upstream `depends_on`, the services that
        depend on it (derived), and store specifics (max_connections, shared_by). Use it to find
        SHARED infrastructure and reason about which upstream could cause a downstream symptom.
        e.g. get_topology('redis'), get_topology('checkout')."""
        return vault.get_topology(service)

    @tool
    def get_changes(service: str = "") -> str:
        """List deploys / config changes / migrations in the incident window (optionally for one
        service), each with its source line. Use it to find what changed right before onset and to
        check rollbacks. e.g. get_changes() or get_changes('rate-limiter')."""
        return vault.get_changes(service or None)

    @tool
    def get_metric(name: str) -> str:
        """Read a metric time-series in the incident window, with a summary (peak / min / max +
        peak time). Use it for timing correlation. e.g. get_metric('checkout_p99'),
        get_metric('orders_db_latency'), get_metric('redis_connections'). Unknown name lists the
        available metrics."""
        return vault.get_metric(name)

    return [list_evidence, read_file, search, get_topology, get_changes, get_metric]
