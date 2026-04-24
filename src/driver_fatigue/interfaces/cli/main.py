from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from driver_fatigue.bootstrap import build_monitor_use_case
from driver_fatigue.interfaces.config.settings import AppSettings


def _parse_source(arg: str) -> tuple[str, int]:
    kind, _, value = arg.partition(":")
    if kind != "webcam":
        raise argparse.ArgumentTypeError(
            f"source '{kind}' não suportado na Fase 1 (use 'webcam:N')"
        )
    try:
        return kind, int(value or "0")
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="driver-fatigue",
        description="Detector de fadiga em motoristas (Clean Architecture).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="inicia detecção")
    run.add_argument("--source", type=_parse_source, default=("webcam", 0),
                     help="fonte de vídeo (ex.: webcam:0)")
    run.add_argument("--config", type=Path, default=None,
                     help="caminho para YAML de configuração")
    run.add_argument("--headless", action="store_true", help="sem janela OpenCV")
    run.add_argument("--verbose", "-v", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.command == "run":
        if args.config and args.config.exists():
            settings = AppSettings.from_yaml(args.config)
        else:
            settings = AppSettings()

        kind, index = args.source
        settings = settings.model_copy(update={
            "source": settings.source.model_copy(update={"kind": kind, "index": index}),
            "headless": args.headless or settings.headless,
        })
        uc = build_monitor_use_case(settings=settings)
        uc.run()
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
