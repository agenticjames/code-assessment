"""The Biggy worker — the only Python process in Phase 2 (docs/PHASE2.md §1/§5).

Claims jobs from the Redis stream, runs the SAME engine the CLI runs, and fans trace events out to
Redis (live stream) + Postgres (durable record). The engine knows nothing about either surface — the
worker just plugs a ``RedisPgSink`` into the existing ``Tracer`` seam.

Run with::

    python -m biggy.worker
"""
