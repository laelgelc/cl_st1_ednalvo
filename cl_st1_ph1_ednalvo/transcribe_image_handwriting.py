#!/usr/bin/env python3
"""
transcribe_image_handwriting.py

Batch‑transcribe handwritten Brazilian Portuguese text from images using
an OpenAI GPT vision model.

The script:

- Loads the `OPENAI_API_KEY` from `env/.env` (relative to this script).
- Scans an input directory for supported image formats (`.jpg`, `.jpeg`, `.png` by default).
- Sends each image to a vision‑capable GPT model with a fixed prompt tailored
  to Brazilian Portuguese handwriting.
- Writes one UTF‑8 `.txt` file per image in the output directory, preserving
  paragraph structure.
- Skips images whose `.txt` files already exist (unless `--reprocess` is used).
- Can process images in parallel using multiple worker processes.
- Logs progress and errors to a log file and prints a concise summary.
- Produces a JSON manifest with per‑file status, timing, and error information.

Usage (examples)
----------------

Basic test run on a small sample (test mode enabled by default, limit 5):

    python transcribe_image_handwriting.py \
        --model gpt-4.1-mini \
        --input-dir corpus/01_poc_dataset \
        --output-dir corpus/01_poc_dataset_out

Process all supported images without test mode, using 4 workers:

    python transcribe_image_handwriting.py \
        --model gpt-4.1-mini \
        --input-dir corpus/01_poc_dataset \
        --output-dir corpus/01_poc_dataset_out \
        --no-test-mode \
        --workers 4

Force reprocessing of all images, overriding existing `.txt` files:

    python transcribe_image_handwriting.py \
        --model gpt-4.1-mini \
        --input-dir corpus/01_poc_dataset \
        --output-dir corpus/01_poc_dataset_out \
        --no-test-mode \
        --reprocess
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import requests


PROMPT_VERSION = "v1"

PROMPT_TEXT = (
    "This image contains handwritten text in Brazilian Portuguese. "
    "Transcribe only the handwritten text, ignoring any printed or pre‑printed "
    "text, into plain text. Preserve the original sentence and paragraph "
    "structure, grouping sentences into paragraphs as in the original and "
    "separating paragraphs with a single blank line. Do not add any "
    "explanations or extra text."
)

SUPPORTED_IMAGE_EXTENSIONS_DEFAULT: Tuple[str, ...] = (".jpg", ".jpeg", ".png")

MIME_TYPES: Dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}

OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"


@dataclass
class TranscriptionResult:
    status: str  # "success" or "failed"
    text: Optional[str]
    error: Optional[str]
    retries: int
    duration_seconds: float


@dataclass
class FileResult:
    input_path: str
    output_path: str
    status: str  # "success", "failed", "skipped_existing"
    error: Optional[str]
    retries: int
    duration_seconds: float
    model: Optional[str]
    timestamp: str  # ISO 8601


def load_env_file(env_path: Path) -> None:
    """
    Minimal .env loader: reads KEY=VALUE lines and populates os.environ.

    - Lines starting with '#' are ignored.
    - Blank lines are ignored.
    - Quotes around values are stripped.
    """
    if not env_path.is_file():
        return

    with env_path.open("r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value:
                os.environ.setdefault(key, value)


def parse_extensions(ext_arg: Optional[str]) -> Tuple[str, ...]:
    if not ext_arg:
        return SUPPORTED_IMAGE_EXTENSIONS_DEFAULT
    parts = [p.strip().lower() for p in ext_arg.split(",") if p.strip()]
    normalized: List[str] = []
    for p in parts:
        if not p.startswith("."):
            p = "." + p
        normalized.append(p)
    if not normalized:
        raise ValueError("No valid extensions provided in --extensions.")
    return tuple(normalized)


def discover_images(input_dir: Path, extensions: Sequence[str]) -> List[Path]:
    images: List[Path] = []
    for entry in sorted(input_dir.iterdir()):
        if not entry.is_file():
            continue
        suffix = entry.suffix.lower()
        if suffix in extensions:
            images.append(entry)
    return images


def transcribe_image(
        image_path: Path,
        model: str,
        mime_type: str,
        prompt: str,
        api_key: str,
        timeout: float,
        max_retries: int,
) -> TranscriptionResult:
    """
    Call the OpenAI Chat Completions API with an image and return the transcription.

    This function performs no logging and does not write any files.
    """
    start = time.time()
    retries_used = 0

    with image_path.open("rb") as f:
        image_bytes = f.read()

    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    image_url = f"data:{mime_type};base64,{b64_image}"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "temperature": 0.0,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ],
    }

    while True:
        try:
            response = requests.post(
                OPENAI_CHAT_COMPLETIONS_URL,
                headers=headers,
                json=payload,
                timeout=timeout,
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            # Transient network error
            if retries_used >= max_retries:
                duration = time.time() - start
                return TranscriptionResult(
                    status="failed",
                    text=None,
                    error=f"Network error after {retries_used} retries: {exc}",
                    retries=retries_used,
                    duration_seconds=duration,
                )
            retries_used += 1
            backoff = 2 ** retries_used
            time.sleep(backoff)
            continue

        # Non-network response handling
        if response.status_code == 200:
            try:
                data = response.json()
                message = data["choices"][0]["message"]["content"]
                duration = time.time() - start
                return TranscriptionResult(
                    status="success",
                    text=message,
                    error=None,
                    retries=retries_used,
                    duration_seconds=duration,
                )
            except Exception as exc:  # noqa: BLE001
                duration = time.time() - start
                return TranscriptionResult(
                    status="failed",
                    text=None,
                    error=f"Failed to parse response JSON: {exc}",
                    retries=retries_used,
                    duration_seconds=duration,
                )

        # Non-200 responses
        is_transient = response.status_code in {429} or 500 <= response.status_code < 600
        body_text: str
        try:
            body_text = response.text
        except Exception:  # noqa: BLE001
            body_text = "<unavailable>"

        if not is_transient or retries_used >= max_retries:
            duration = time.time() - start
            return TranscriptionResult(
                status="failed",
                text=None,
                error=(
                    f"HTTP {response.status_code} after {retries_used} retries: "
                    f"{body_text[:500]}"
                ),
                retries=retries_used,
                duration_seconds=duration,
            )

        retries_used += 1
        backoff = 2 ** retries_used
        time.sleep(backoff)


def setup_logging(log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt="[{asctime}] {levelname:5s}  {message}",
        datefmt="%Y-%m-%d %H:%M:%S",
        style="{",
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(console_handler)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Batch‑transcribe handwritten Brazilian Portuguese text from images "
            "using an OpenAI GPT vision model."
        )
    )

    parser.add_argument(
        "--model",
        required=True,
        help="OpenAI model name to use (e.g. gpt-4.1-mini).",
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing input images.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where .txt files, logs, and manifest will be written.",
    )

    test_group = parser.add_mutually_exclusive_group()
    test_group.add_argument(
        "--test-mode",
        dest="test_mode",
        action="store_true",
        default=True,
        help="Enable test mode (default: enabled).",
    )
    test_group.add_argument(
        "--no-test-mode",
        dest="test_mode",
        action="store_false",
        help="Disable test mode and process all images.",
    )

    parser.add_argument(
        "--test-limit",
        type=int,
        default=5,
        help="Maximum number of images to attempt in test mode (default: 5).",
    )
    parser.add_argument(
        "--reprocess",
        action="store_true",
        default=False,
        help="Reprocess images even if output .txt files already exist.",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Path to log file (default: <output-dir>/transcribe_image_handwriting.log).",
    )
    parser.add_argument(
        "--manifest-file",
        type=str,
        default=None,
        help="Path to JSON manifest (default: <output-dir>/manifest.json).",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum number of retries for transient API errors (default: 3).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Request timeout in seconds for each API call (default: 60).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes for parallel processing (default: 1).",
    )
    parser.add_argument(
        "--extensions",
        type=str,
        default=None,
        help="Comma‑separated list of image extensions to process "
             "(e.g. '.jpg,.jpeg,.png'). Default: .jpg,.jpeg,.png",
    )

    return parser


def create_output_paths(
        input_path: Path,
        output_dir: Path,
) -> Path:
    # Include original extension in the base name to avoid clashes.
    out_name = f"{input_path.name}.txt"
    return output_dir / out_name


def build_manifest_entry(
        fr: FileResult,
) -> Dict[str, object]:
    return asdict(fr)


def write_manifest(
        manifest_path: Path,
        run_metadata: Dict[str, object],
        file_results: List[FileResult],
) -> None:
    manifest = {
        "run_metadata": run_metadata,
        "files": [build_manifest_entry(fr) for fr in file_results],
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    # Load .env relative to this script: env/.env
    script_dir = Path(__file__).resolve().parent
    env_path = script_dir / "env" / ".env"
    load_env_file(env_path)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print(
            "ERROR: OPENAI_API_KEY is not set. Please define it in env/.env or the environment.",
            file=sys.stderr,
        )
        return 1

    try:
        extensions = parse_extensions(args.extensions)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    input_dir = Path(args.input_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()

    if not input_dir.is_dir():
        print(f"ERROR: Input directory does not exist or is not a directory: {input_dir}")
        return 1

    if args.test_limit <= 0:
        print("ERROR: --test-limit must be > 0.", file=sys.stderr)
        return 1
    if args.max_retries < 0:
        print("ERROR: --max-retries must be >= 0.", file=sys.stderr)
        return 1
    if args.timeout <= 0:
        print("ERROR: --timeout must be > 0.", file=sys.stderr)
        return 1
    if args.workers <= 0:
        print("ERROR: --workers must be > 0.", file=sys.stderr)
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    log_file = (
        Path(args.log_file).expanduser().resolve()
        if args.log_file
        else output_dir / "transcribe_image_handwriting.log"
    )
    manifest_file = (
        Path(args.manifest_file).expanduser().resolve()
        if args.manifest_file
        else output_dir / "manifest.json"
    )

    setup_logging(log_file)

    logging.info("Starting transcription run")
    logging.info("Model: %s", args.model)
    logging.info("Input dir: %s", input_dir)
    logging.info("Output dir: %s", output_dir)
    logging.info("Log file: %s", log_file)
    logging.info("Manifest file: %s", manifest_file)
    logging.info("Test mode: %s (limit=%d)", args.test_mode, args.test_limit)
    logging.info("Reprocess existing: %s", args.reprocess)
    logging.info("Workers: %d", args.workers)
    logging.info("Supported extensions: %s", ", ".join(extensions))
    logging.info("Prompt version: %s", PROMPT_VERSION)
    logging.info("Prompt: %s", PROMPT_TEXT)

    images = discover_images(input_dir, extensions)
    total_discovered = len(images)
    if total_discovered == 0:
        logging.error(
            "No images found in %s with extensions: %s",
            input_dir,
            ", ".join(extensions),
        )
        return 1

    logging.info("Discovered %d image(s).", total_discovered)

    # Plan work list and track skipped_existing
    work_items: List[Tuple[Path, Path, str]] = []
    file_results: List[FileResult] = []
    skipped_existing = 0

    for img in images:
        out_path = create_output_paths(img, output_dir)
        suffix = img.suffix.lower()
        mime_type = MIME_TYPES.get(suffix)
        if mime_type is None:
            logging.warning(
                "Skipping %s because MIME type for extension %s is not defined.",
                img,
                suffix,
            )
            file_results.append(
                FileResult(
                    input_path=str(img),
                    output_path=str(out_path),
                    status="failed",
                    error=f"No MIME type defined for extension {suffix}",
                    retries=0,
                    duration_seconds=0.0,
                    model=args.model,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
            )
            continue

        if not args.reprocess and out_path.is_file():
            logging.info(
                "SKIPPED_EXISTING %s (output file already exists)", img.name
            )
            skipped_existing += 1
            file_results.append(
                FileResult(
                    input_path=str(img),
                    output_path=str(out_path),
                    status="skipped_existing",
                    error=None,
                    retries=0,
                    duration_seconds=0.0,
                    model=None,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
            )
            continue

        work_items.append((img, out_path, mime_type))

    if args.test_mode:
        if len(work_items) > args.test_limit:
            logging.info(
                "Test mode enabled: limiting work items from %d to %d.",
                len(work_items),
                args.test_limit,
            )
            work_items = work_items[: args.test_limit]

    attempted = len(work_items)
    succeeded = 0
    failed = 0

    start_time = datetime.now(timezone.utc)

    logging.info("Beginning processing of %d image(s).", attempted)

    try:
        if attempted == 0:
            logging.info("No images to process after applying skip/test-mode filters.")
        elif args.workers == 1:
            for img_path, out_path, mime_type in work_items:
                logging.info("Processing %s", img_path.name)
                result = transcribe_image(
                    image_path=img_path,
                    model=args.model,
                    mime_type=mime_type,
                    prompt=PROMPT_TEXT,
                    api_key=api_key,
                    timeout=args.timeout,
                    max_retries=args.max_retries,
                )
                if result.status == "success" and result.text is not None:
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_text(result.text, encoding="utf-8")
                    succeeded += 1
                    logging.info(
                        "SUCCESS %s -> %s (%.2fs, retries=%d)",
                        img_path.name,
                        out_path.name,
                        result.duration_seconds,
                        result.retries,
                    )
                else:
                    failed += 1
                    logging.error(
                        "FAILED %s (retries=%d): %s",
                        img_path.name,
                        result.retries,
                        result.error,
                    )

                file_results.append(
                    FileResult(
                        input_path=str(img_path),
                        output_path=str(out_path),
                        status=result.status,
                        error=result.error,
                        retries=result.retries,
                        duration_seconds=result.duration_seconds,
                        model=args.model,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    )
                )
        else:
            # Parallel processing with ProcessPoolExecutor
            with ProcessPoolExecutor(max_workers=args.workers) as executor:
                future_to_item = {
                    executor.submit(
                        transcribe_image,
                        img_path,
                        args.model,
                        mime_type,
                        PROMPT_TEXT,
                        api_key,
                        args.timeout,
                        args.max_retries,
                    ): (img_path, out_path, mime_type)
                    for img_path, out_path, mime_type in work_items
                }

                for future in as_completed(future_to_item):
                    img_path, out_path, _mime_type = future_to_item[future]
                    try:
                        result: TranscriptionResult = future.result()
                    except KeyboardInterrupt:
                        logging.error("KeyboardInterrupt received in worker.")
                        raise
                    except Exception as exc:  # noqa: BLE001
                        failed += 1
                        err_msg = f"Worker exception: {exc}"
                        logging.error("FAILED %s due to worker exception: %s", img_path, exc)
                        file_results.append(
                            FileResult(
                                input_path=str(img_path),
                                output_path=str(out_path),
                                status="failed",
                                error=err_msg,
                                retries=0,
                                duration_seconds=0.0,
                                model=args.model,
                                timestamp=datetime.now(timezone.utc).isoformat(),
                            )
                        )
                        continue

                    if result.status == "success" and result.text is not None:
                        out_path.parent.mkdir(parents=True, exist_ok=True)
                        out_path.write_text(result.text, encoding="utf-8")
                        succeeded += 1
                        logging.info(
                            "SUCCESS %s -> %s (%.2fs, retries=%d)",
                            img_path.name,
                            out_path.name,
                            result.duration_seconds,
                            result.retries,
                        )
                    else:
                        failed += 1
                        logging.error(
                            "FAILED %s (retries=%d): %s",
                            img_path.name,
                            result.retries,
                            result.error,
                        )

                    file_results.append(
                        FileResult(
                            input_path=str(img_path),
                            output_path=str(out_path),
                            status=result.status,
                            error=result.error,
                            retries=result.retries,
                            duration_seconds=result.duration_seconds,
                            model=args.model,
                            timestamp=datetime.now(timezone.utc).isoformat(),
                        )
                    )

    except KeyboardInterrupt:
        logging.error("Run interrupted by user (KeyboardInterrupt).")
        # fall through to summary/manifest with partial results
    end_time = datetime.now(timezone.utc)

    # Summary
    logging.info("Run complete.")
    logging.info("Total discovered: %d", total_discovered)
    logging.info("Skipped (existing outputs): %d", skipped_existing)
    logging.info("Attempted: %d", attempted)
    logging.info("Succeeded: %d", succeeded)
    logging.info("Failed: %d", failed)

    run_metadata = {
        "model": args.model,
        "prompt_version": PROMPT_VERSION,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "test_mode": bool(args.test_mode),
        "test_limit": int(args.test_limit),
        "reprocess": bool(args.reprocess),
        "workers": int(args.workers),
        "supported_extensions": list(extensions),
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
    }

    try:
        write_manifest(manifest_file, run_metadata, file_results)
        logging.info("Manifest written to %s", manifest_file)
    except Exception as exc:  # noqa: BLE001
        logging.error("Failed to write manifest %s: %s", manifest_file, exc)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())