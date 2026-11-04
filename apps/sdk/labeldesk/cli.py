"""LabelDesk command line. Run as `labeldesk ...` or `python -m labeldesk.cli ...`.

Auth comes from `--api-key` / LABELDESK_API_KEY; the API root from `--base-url` / LABELDESK_URL.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .client import LabelDesk, LabelDeskError


def _emit(obj, args) -> None:
    if args.json:
        print(json.dumps(obj, separators=(",", ":"), default=str))
    else:
        print(json.dumps(obj, indent=2, default=str))


def _cmd_whoami(args, client: LabelDesk) -> int:
    _emit(client.whoami(), args)
    return 0


def _cmd_models(args, client: LabelDesk) -> int:
    _emit(client.models(), args)
    return 0


def _cmd_upload(args, client: LabelDesk) -> int:
    _emit(client.upload(args.project, args.files, batch_name=args.batch, split=args.split, tags=args.tags), args)
    return 0


def _cmd_export(args, client: LabelDesk) -> int:
    job = client.export(args.project, args.version, args.fmt)
    if not args.wait:
        _emit(job, args)
        return 0
    job = client.job(job["id"], wait=True)
    if not job.get("url"):
        raise LabelDeskError(0, "export finished without a download URL")
    dest = Path(args.output) if args.output else Path(f"{args.version}-{args.fmt}.zip")
    job["saved"] = str(client.download(job["url"], dest))
    _emit(job, args)
    return 0


def _cmd_train(args, client: LabelDesk) -> int:
    model = client.train(args.project, args.version, variant=args.variant, epochs=args.epochs,
                         imgsz=args.imgsz, batch=args.batch)
    if args.wait and model.get("jobId"):
        client.job(model["jobId"], wait=True)
        model = client.model(model["id"])
    _emit(model, args)
    return 0


def _cmd_predict(args, client: LabelDesk) -> int:
    _emit(client.predict(args.model, args.image, confidence=args.confidence), args)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="labeldesk", description="LabelDesk developer API client")
    p.add_argument("--base-url", dest="base_url", help="API root (env LABELDESK_URL, default http://localhost:8010)")
    p.add_argument("--api-key", dest="api_key", help="workspace API key (env LABELDESK_API_KEY)")
    p.add_argument("--json", action="store_true", help="one-line JSON output")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("whoami", help="show the workspace behind the key")
    s.set_defaults(run=_cmd_whoami)

    s = sub.add_parser("models", help="list trained models")
    s.set_defaults(run=_cmd_models)

    s = sub.add_parser("upload", help="upload images to a project")
    s.add_argument("project", help="project slug")
    s.add_argument("files", nargs="+", help="image files (or a zip)")
    s.add_argument("--batch", default="CLI Upload", help="batch name")
    s.add_argument("--split", default="auto", help="auto | train | valid | test | keep")
    s.add_argument("--tags", default="", help="comma-separated tags")
    s.set_defaults(run=_cmd_upload)

    s = sub.add_parser("export", help="export a dataset version")
    s.add_argument("project", help="project slug")
    s.add_argument("version", help="version id")
    s.add_argument("--format", dest="fmt", default="coco", help="coco | yolo | voc | ...")
    s.add_argument("-o", "--output", help="download path (default VERSION-FORMAT.zip)")
    s.add_argument("--wait", action="store_true", help="wait for the export, then download it")
    s.set_defaults(run=_cmd_export)

    s = sub.add_parser("train", help="start a training job")
    s.add_argument("project", help="project slug")
    s.add_argument("version", help="dataset version id")
    s.add_argument("--variant", default="yolo26n")
    s.add_argument("--epochs", type=int, default=30)
    s.add_argument("--imgsz", type=int, default=640)
    s.add_argument("--batch", type=int, default=8)
    s.add_argument("--wait", action="store_true", help="wait for the job and print the trained model")
    s.set_defaults(run=_cmd_train)

    s = sub.add_parser("predict", help="run hosted inference on one image")
    s.add_argument("model", help="trained model id")
    s.add_argument("image", help="local image path")
    s.add_argument("--confidence", type=float, help="override the model's best-F1 threshold")
    s.set_defaults(run=_cmd_predict)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    client = None
    try:
        client = LabelDesk(api_key=args.api_key, base_url=args.base_url)
        return args.run(args, client)
    except (LabelDeskError, OSError) as exc:
        print(f"error: {getattr(exc, 'detail', None) or exc}", file=sys.stderr)
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
