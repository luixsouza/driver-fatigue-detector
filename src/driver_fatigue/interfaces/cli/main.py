from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from driver_fatigue.bootstrap import build_monitor_use_case
from driver_fatigue.interfaces.config.settings import (
    AppSettings,
    RecordingSettings,
    SourceSettings,
)


def _parse_source(arg: str) -> SourceSettings:
    if arg.startswith("rtsp://") or arg.startswith("rtsps://"):
        return SourceSettings(kind="rtsp", url=arg)
    kind, _, value = arg.partition(":")
    if kind == "webcam":
        try:
            return SourceSettings(kind="webcam", index=int(value or "0"))
        except ValueError as e:
            raise argparse.ArgumentTypeError(f"webcam index inválido: {e}")
    if kind == "file":
        if not value:
            raise argparse.ArgumentTypeError("file: requer um path (file:path/to.mp4)")
        return SourceSettings(kind="file", path=Path(value))
    raise argparse.ArgumentTypeError(
        f"source '{kind}' não suportado (use webcam:N, file:path, rtsp://...)"
    )


def _parse_sinks(arg: str) -> list[str]:
    valid = {"sound", "log", "http", "mqtt"}
    names = [n.strip() for n in arg.split(",") if n.strip()]
    for n in names:
        if n not in valid:
            raise argparse.ArgumentTypeError(
                f"sink '{n}' inválido; valores: {', '.join(sorted(valid))}"
            )
    return names


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="driver-fatigue",
        description="Detector de fadiga em motoristas (Clean Architecture).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="inicia detecção")
    run.add_argument(
        "--source", type=_parse_source,
        default=SourceSettings(kind="webcam", index=0),
        help="fonte de vídeo: webcam:N | file:path | rtsp://...",
    )
    run.add_argument(
        "--sinks", type=_parse_sinks, default=None,
        help="sinks ativos (comma-separated): sound,log,http,mqtt",
    )
    run.add_argument(
        "--record", type=Path, default=None,
        help="grava MP4 com overlay no caminho dado",
    )
    run.add_argument("--config", type=Path, default=None,
                     help="caminho para YAML de configuração")
    run.add_argument("--headless", action="store_true", help="sem janela OpenCV")
    run.add_argument(
        "--context-validator",
        choices=["noop", "eye_state"],
        default=None,
        help="validador contextual de alertas (default: usa config)",
    )
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

        updates: dict = {
            "source": args.source,
            "headless": args.headless or settings.headless,
        }
        if args.sinks is not None:
            updates["sinks"] = args.sinks
        if args.record is not None:
            updates["recording"] = RecordingSettings(
                path=args.record,
                fps=settings.recording.fps,
                codec=settings.recording.codec,
            )
        if args.context_validator is not None:
            updates["context_validator"] = settings.context_validator.model_copy(
                update={"kind": args.context_validator},
            )
        settings = settings.model_copy(update=updates)

        uc = build_monitor_use_case(settings=settings)
        uc.run()
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
