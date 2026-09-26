"""Command line entry point: `dgro serve`, `dgro doctor`, `dgro sync-inbox`."""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .config import get_settings


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from .runtime import build_runtime, configure_logging
    from .web.app import create_app

    settings = get_settings()
    if args.host:
        settings.host = args.host
    if args.port:
        settings.port = args.port
    configure_logging(settings.log_level)
    runtime = build_runtime(settings)
    app = create_app(runtime)
    print(f"dgro {__version__} - AI: {runtime.llm.name} ({settings.model}), email: {runtime.mail.name}, "
          f"data: {settings.data_dir.resolve()}")
    if settings.host not in ("127.0.0.1", "localhost"):
        print("WARNING: dgro has no login. Only expose it on a network you trust.")
    print(f"Open http://{'127.0.0.1' if settings.host == '0.0.0.0' else settings.host}:{settings.port}")
    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level.lower())
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    from .runtime import build_runtime

    settings = get_settings()
    ok = True
    print(f"dgro {__version__}")
    print(f"  data dir     : {settings.data_dir.resolve()}")
    runtime = build_runtime(settings)
    print(f"  database     : {settings.db_path.resolve()} (ok)")
    print(f"  AI backend   : {runtime.llm.name} / model {settings.model}")
    if runtime.llm.name == "fake":
        print("                 demo mode - set ANTHROPIC_API_KEY to use Claude")
    elif args.live:
        import anthropic

        try:
            model = runtime.llm.client.models.retrieve(settings.model)  # type: ignore[attr-defined]
            print(f"  Claude API   : ok - {model.display_name} available")
        except anthropic.APIError as exc:
            ok = False
            print(f"  Claude API   : FAILED - {exc}")
    print(f"  email mode   : {runtime.mail.name}")
    for passed, text in runtime.mail.check() if (args.live or runtime.mail.name == "sandbox") else []:
        ok = ok and passed
        print(f"  {'ok' if passed else 'FAIL':<12} : {text}")
    if runtime.mail.name != "sandbox" and not args.live:
        print("                 run `dgro doctor --live` to test SMTP/IMAP logins")
    if not (settings.requester_email or settings.email_from):
        print("  note         : set DGRO_REQUESTER_NAME / DGRO_REQUESTER_EMAIL to pre-fill your contact details")
    return 0 if ok else 1


def cmd_sync_inbox(args: argparse.Namespace) -> int:
    from .runtime import build_runtime, configure_logging

    settings = get_settings()
    configure_logging(settings.log_level)
    runtime = build_runtime(settings)
    if not runtime.mail.can_receive:
        print("Inbox sync needs DGRO_EMAIL_MODE=smtp and IMAP settings.")
        return 1
    with runtime.session() as db:
        runtime.queue.enqueue(db, "sync_inbox")
        db.commit()
    done = runtime.worker.run_pending()
    print(f"Processed {done} job(s).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dgro", description="Collect and compare vendor quotes, case by case.")
    parser.add_argument("--version", action="version", version=f"dgro {__version__}")
    sub = parser.add_subparsers(dest="command")

    serve = sub.add_parser("serve", help="run the web app (default)")
    serve.add_argument("--host", default="")
    serve.add_argument("--port", type=int, default=0)
    serve.set_defaults(func=cmd_serve)

    doctor = sub.add_parser("doctor", help="check configuration")
    doctor.add_argument("--live", action="store_true", help="also call the Claude API and log in to SMTP/IMAP")
    doctor.set_defaults(func=cmd_doctor)

    sync = sub.add_parser("sync-inbox", help="fetch vendor replies once and process them")
    sync.set_defaults(func=cmd_sync_inbox)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        args = parser.parse_args(["serve", *(argv or [])])
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
