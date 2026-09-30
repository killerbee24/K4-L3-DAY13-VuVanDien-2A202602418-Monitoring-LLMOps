from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from itertools import cycle, islice
from pathlib import Path

import httpx
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio
from app.main import app
from app.tracing import get_langfuse_client, tracing_enabled


def _load_payloads(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


async def generate_traces(*, labels: list[str], per_label: int) -> None:
    payloads = _load_payloads(REPO_ROOT / "data" / "sample_queries.jsonl")
    if not payloads:
        raise RuntimeError("No sample queries found")

    original_label = os.getenv("LANGFUSE_PROMPT_LABEL")
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://trace-evidence",
            timeout=30.0,
        ) as client:
            for label in labels:
                os.environ["LANGFUSE_PROMPT_LABEL"] = label
                for payload in islice(cycle(payloads), per_label):
                    request_id = f"req-{uuid.uuid4().hex[:8]}"
                    response = await client.post(
                        "/chat",
                        json=payload,
                        headers={"x-request-id": request_id},
                    )
                    response.raise_for_status()
                    print(
                        f"label={label} status={response.status_code} "
                        f"correlation_id={response.json()['correlation_id']}"
                    )
    finally:
        if original_label is None:
            os.environ.pop("LANGFUSE_PROMPT_LABEL", None)
        else:
            os.environ["LANGFUSE_PROMPT_LABEL"] = original_label

    get_langfuse_client().flush()


def main() -> int:
    configure_utf8_stdio()
    load_dotenv(REPO_ROOT / ".env", override=True)
    parser = argparse.ArgumentParser(
        description="Generate linked logs and Langfuse traces for CP2 evidence."
    )
    parser.add_argument("--per-label", type=int, default=5)
    parser.add_argument(
        "--labels",
        nargs="+",
        default=["baseline", "candidate"],
    )
    args = parser.parse_args()

    if args.per_label < 1:
        parser.error("--per-label must be at least 1")
    if not tracing_enabled():
        print("Langfuse tracing is disabled; configure both keys in .env first.")
        return 1

    asyncio.run(generate_traces(labels=args.labels, per_label=args.per_label))
    print(
        f"Generated {len(args.labels) * args.per_label} linked traces "
        f"for labels: {', '.join(args.labels)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
