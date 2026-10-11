from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from app.services.topic_transfer import (
    TopicTransferError,
    TransferRoots,
    export_topic,
    import_topic,
)
from app.services.topic_transfer_adapter import get_adapter

TRUST_WARNING = (
    "Import learn-up topics only from people and sources you trust. "
    "Validation reduces common archive risks, but it cannot make an untrusted archive safe."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export or securely import one learn-up topic"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    export_parser = subparsers.add_parser("export", help="Export one topic")
    export_parser.add_argument("topic_slug")
    export_parser.add_argument("--output", type=Path, required=True)
    export_parser.add_argument("--overwrite", action="store_true")
    import_parser = subparsers.add_parser(
        "import", help=f"Validate or import one topic. {TRUST_WARNING}"
    )
    import_parser.add_argument("archive", type=Path)
    action = import_parser.add_mutually_exclusive_group()
    action.add_argument("--dry-run", action="store_true")
    action.add_argument("--confirm", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    roots = TransferRoots.from_repo(Path(__file__).resolve().parents[1])
    adapter = get_adapter()
    try:
        if args.command == "export":
            report = export_topic(
                roots,
                adapter,
                args.topic_slug,
                args.output,
                overwrite=args.overwrite,
            )
        else:
            print(TRUST_WARNING, file=sys.stderr)
            report = import_topic(args.archive, roots, adapter, confirm=args.confirm)
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    except TopicTransferError as exc:
        print(f"topic transfer failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
