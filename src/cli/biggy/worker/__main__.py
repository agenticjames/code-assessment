"""``python -m biggy.worker`` — claim jobs from Redis, run the engine, persist + stream (PHASE2 §1).

A single-process consume loop: block for a job, run it to a terminal state, ACK, repeat.
"""

from __future__ import annotations

import os
import socket
import sys

from dotenv import find_dotenv, load_dotenv

from biggy.engine.llm.client import ensure_google_key
from biggy.worker import redis_io
from biggy.worker.contracts import Job
from biggy.worker.db import Db
from biggy.worker.runner import run_job


def main() -> None:
    load_dotenv(find_dotenv(usecwd=True))

    database_url = os.environ.get("DATABASE_URL")
    redis_url = os.environ.get("REDIS_URL")
    if not database_url or not redis_url:
        sys.exit("DATABASE_URL and REDIS_URL are required (see .env.example).")
    if not ensure_google_key():
        sys.exit("GEMINI_API_KEY (or GOOGLE_API_KEY) is required (see .env.example).")

    r = redis_io.connect(redis_url)
    redis_io.ensure_group(r)
    db = Db.connect(database_url)
    consumer = f"{socket.gethostname()}-{os.getpid()}"
    print(
        f"[worker] consuming {redis_io.JOBS_STREAM} as {consumer}",
        file=sys.stderr,
    )

    try:
        while True:
            claimed = redis_io.claim_job(r, consumer)
            if claimed is None:
                continue
            msg_id, fields = claimed
            try:
                job = Job.model_validate_json(fields["data"])
                run_job(job, db, r)
            except Exception as exc:  # noqa: BLE001 - never let one bad job kill the loop
                print(f"[worker] job error: {exc}", file=sys.stderr)
            finally:
                redis_io.ack(r, msg_id)
    except KeyboardInterrupt:
        print("[worker] shutting down", file=sys.stderr)
    finally:
        db.close()


if __name__ == "__main__":
    main()
