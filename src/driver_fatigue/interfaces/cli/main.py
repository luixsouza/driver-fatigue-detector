from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from driver_fatigue.bootstrap import build_monitor_use_case
from driver_fatigue.config.settings import (
    AppSettings,
    DashboardStreamSettings,
    HttpWebhookSettings,
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
            raise argparse.ArgumentTypeError(f"webcam index inválido: {e}") from e
    if kind == "file":
        if not value:
            raise argparse.ArgumentTypeError("file: requer um path (file:path/to.mp4)")
        return SourceSettings(kind="file", path=Path(value))
    raise argparse.ArgumentTypeError(
        f"source '{kind}' não suportado (use webcam:N, file:path, rtsp://...)"
    )


def _parse_sinks(arg: str) -> list[str]:
    valid = {"sound", "log", "http", "mqtt", "jsonl"}
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

    web = sub.add_parser("web", help="dashboard HTTP/SSE em tempo real (sobe detector junto)")
    web.add_argument("--host", default="0.0.0.0")
    web.add_argument("--port", type=int, default=8000)
    web.add_argument("--source", default="webcam:0",
                     help="fonte do detector embutido (webcam:N | file:path | rtsp://...)")
    web.add_argument("--no-detector", action="store_true",
                     help="apenas o servidor; o detector deve ser rodado a parte")
    web.add_argument("--api-key", default=None,
                     help="exige X-API-Key em /api/events e /api/video/push")
    web.add_argument("--config", type=Path, default=None,
                     help="caminho para YAML (lê web.api_key, web.host, web.port)")

    run = sub.add_parser("run", help="inicia detecção")
    run.add_argument(
        "--source", type=_parse_source,
        default=SourceSettings(kind="webcam", index=0),
        help="fonte de vídeo: webcam:N | file:path | rtsp://...",
    )
    run.add_argument(
        "--sinks", type=_parse_sinks, default=None,
        help="sinks ativos (comma-separated): sound,log,http,mqtt,jsonl",
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
    run.add_argument(
        "--dashboard", default=None,
        metavar="URL",
        help="URL do dashboard p/ enviar webhook+video (ex http://localhost:8000)",
    )
    run.add_argument("--loop", action="store_true",
                     help="loopa a fonte de vídeo (válido para --source file:...)")
    run.add_argument("--verbose", "-v", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if getattr(args, "verbose", False) else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.command == "web":
        from driver_fatigue.interfaces.web.server import serve
        web_settings = None
        if args.config and args.config.exists():
            web_settings = AppSettings.from_yaml(args.config).web
        api_key = (
            args.api_key
            or (web_settings.api_key if web_settings else None)
            or os.environ.get("DRIVER_FATIGUE_WEB__API_KEY")
        )
        host = args.host if args.host != "0.0.0.0" else (web_settings.host if web_settings else args.host)
        port = args.port if args.port != 8000 else (web_settings.port if web_settings else args.port)
        serve(
            host=host, port=port,
            spawn_detector=not args.no_detector,
            detector_source=args.source,
            api_key=api_key,
        )
        return 0

    if args.command == "run":
        if args.config and args.config.exists():
            settings = AppSettings.from_yaml(args.config)
        else:
            settings = AppSettings()

        source = args.source
        if args.loop and source.kind == "file":
            source = source.model_copy(update={"loop": True})
        updates: dict = {
            "source": source,
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
        if args.dashboard is not None:
            base = args.dashboard.rstrip("/")
            updates["dashboard_stream"] = DashboardStreamSettings(
                enabled=True,
                push_url=f"{base}/api/video/push",
                jpeg_quality=settings.dashboard_stream.jpeg_quality,
                max_fps=settings.dashboard_stream.max_fps,
            )
            updates["http_webhook"] = HttpWebhookSettings(
                url=f"{base}/api/events",
                bearer_token=None,
                timeout_seconds=2.0,
            )
            sinks = list(settings.sinks if args.sinks is None else args.sinks)
            if "http" not in sinks:
                sinks.append("http")
            updates["sinks"] = sinks
        settings = settings.model_copy(update=updates)

        uc = build_monitor_use_case(settings=settings)
        uc.run()
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
