#!/usr/bin/env python3
"""
Transcribe music video audio with Gemini API.

This script reads a curated music video audio index from an NDJSON file,
selects records whose extracted WAV audio is available, and generates a
continuous qualitative transcription of the music recording using the Gemini API.

Source audio files are resolved from the input record's "audio_file" field when
available, or from the input directory as "<corpus_id>.wav". Transcription outputs
are written to the output directory as "<corpus_id>.txt" and "<corpus_id>.json".

The plain-text transcription is intended for corpus linguistic analysis and human
inspection. The JSON transcription preserves model configuration, source metadata,
and run metadata for reproducibility.

By default, the script runs in test mode and attempts only the first planned
music video. Existing transcription files are skipped unless --reprocess is provided,
making the script safe to re-run.

Uploaded audio files are guaranteed to be deleted from Google's servers immediately
after generation via a finally block.

Use --start-corpus-id to resume planning from a specific music video onward.

Example:
    python transcribe_music_videos_gemini.py

Full run:
    python transcribe_music_videos_gemini.py --no-test-mode

Full run from a specific music video:
    python transcribe_music_videos_gemini.py --no-test-mode --start-corpus-id 4xqo7D2k8HM

The script writes an append-only log file, a JSON manifest, and a curated NDJSON
transcription index for downstream analysis.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import APIError

TOOL_NAME = "transcribe_music_videos_gemini.py"
TOOL_VERSION = "v1"

SCRIPT_DIR = Path(__file__).resolve().parent

DEFAULT_AUDIO_INDEX_PATH = (
    "corpus/01_music_videos_audio/music_videos_audio_index.ndjson"
)
DEFAULT_INPUT_DIR = "corpus/01_music_videos_audio/audio"
DEFAULT_OUTPUT_DIR = "corpus/02_music_videos_transcripts_gemini"
DEFAULT_PROMPT_FILE = "music_videos_transcription_prompts/music_videos_transcription_prompts_v1.md"
DEFAULT_ENV_FILE = "env/.env"
DEFAULT_LOG_FILE = (
    "corpus/02_music_videos_transcripts_gemini/"
    "transcribe_music_videos_gemini.log"
)
DEFAULT_MANIFEST_FILE = (
    "corpus/02_music_videos_transcripts_gemini/"
    "transcribe_music_videos_gemini_manifest.json"
)
DEFAULT_TRANSCRIPTION_INDEX_FILE = (
    "corpus/02_music_videos_transcripts_gemini/"
    "music_videos_transcript_index.ndjson"
)

DEFAULT_MODEL_NAME = "gemini-3.6-flash"
DEFAULT_REQUEST_DELAY_SECONDS = 4
DEFAULT_TEST_MODE = True
DEFAULT_TEST_LIMIT = 1
DEFAULT_WORKERS = 1
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY_SECONDS = 10

INPUT_AUDIO_EXTENSION = ".wav"
OUTPUT_TEXT_EXTENSION = ".txt"
OUTPUT_JSON_EXTENSION = ".json"

ELIGIBLE_AUDIO_STATUSES = ("success", "skipped_existing")

SUPPORTED_FORMATS = {
    ".wav": "audio/wav",
    ".mp3": "audio/mp3",
    ".aac": "audio/aac",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".m4a": "audio/m4a",
}

PRESERVED_METADATA_FIELDS = (
    "id",
    "corpus_id",
    "title",
    "description",
    "language",
    "uploader",
    "duration",
    "upload_date",
    "url",
    "audio_file",
    "audio_format",
    "audio_codec",
    "audio_channels",
    "audio_sample_rate",
    "audio_file_size_bytes",
    "download_status",
    "metadata_status",
    "download_run_id",
    "downloaded_at_utc",
    "download_duration_seconds",
    "yt_dlp_version",
)


class ConfigurationError(Exception):
    """Raised when command-line options or runtime configuration are invalid."""


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def utc_timestamp() -> str:
    """Return an ISO-like UTC timestamp string without microseconds."""
    return utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_run_id() -> str:
    """Return a compact UTC run ID suitable for filenames."""
    return utc_now().strftime("%Y%m%dT%H%M%SZ")


def resolve_script_relative_path(path: Path) -> Path:
    """
    Resolve relative paths against the programme directory.
    """
    if path.is_absolute():
        return path
    return SCRIPT_DIR / path


def path_for_index(path_value: Any) -> str | None:
    """
    Convert a path to a portable string for curated index files.
    """
    if path_value is None:
        return None

    path = Path(str(path_value))
    try:
        resolved = path.resolve(strict=False)
    except OSError:
        return str(path)

    try:
        return resolved.relative_to(SCRIPT_DIR).as_posix()
    except ValueError:
        return str(path)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the music videos transcription programme."""
    parser = argparse.ArgumentParser(
        description="Transcribe music video audio with Gemini API."
    )

    parser.add_argument("--audio-index", type=Path, default=Path(DEFAULT_AUDIO_INDEX_PATH))
    parser.add_argument("--input-dir", type=Path, default=Path(DEFAULT_INPUT_DIR))
    parser.add_argument("--output-dir", type=Path, default=Path(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--prompt-file", type=Path, default=Path(DEFAULT_PROMPT_FILE))
    parser.add_argument("--env-file", type=Path, default=Path(DEFAULT_ENV_FILE))

    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--request-delay", type=int, default=DEFAULT_REQUEST_DELAY_SECONDS)

    test_group = parser.add_mutually_exclusive_group()
    test_group.add_argument("--test-mode", dest="test_mode", action="store_true")
    test_group.add_argument("--no-test-mode", dest="test_mode", action="store_false")
    parser.set_defaults(test_mode=DEFAULT_TEST_MODE)

    parser.add_argument("--test-limit", type=int, default=DEFAULT_TEST_LIMIT)
    parser.add_argument("--reprocess", action="store_true")
    parser.add_argument("--start-corpus-id", default=None)

    parser.add_argument("--log-file", type=Path, default=Path(DEFAULT_LOG_FILE))
    parser.add_argument("--manifest-file", type=Path, default=Path(DEFAULT_MANIFEST_FILE))
    parser.add_argument("--transcript-index-file", type=Path, default=Path(DEFAULT_TRANSCRIPTION_INDEX_FILE))

    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    parser.add_argument("--retry-delay", type=int, default=DEFAULT_RETRY_DELAY_SECONDS)

    args = parser.parse_args()

    args.audio_index = resolve_script_relative_path(args.audio_index)
    args.input_dir = resolve_script_relative_path(args.input_dir)
    args.output_dir = resolve_script_relative_path(args.output_dir)
    args.prompt_file = resolve_script_relative_path(args.prompt_file)
    args.env_file = resolve_script_relative_path(args.env_file)
    args.log_file = resolve_script_relative_path(args.log_file)
    args.manifest_file = resolve_script_relative_path(args.manifest_file)
    args.transcript_index_file = resolve_script_relative_path(args.transcript_index_file)

    return args


def setup_logging(log_file: Path) -> logging.Logger:
    """Configure append-only UTF-8 file and console logging."""
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(TOOL_NAME)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)-5s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    return logger


def validate_args(args: argparse.Namespace) -> None:
    """Validate command-line arguments and filesystem paths."""
    if not args.model_name or not str(args.model_name).strip():
        raise ConfigurationError("--model-name must not be blank.")
    if args.request_delay < 0:
        raise ConfigurationError("--request-delay must be zero or positive.")
    if args.test_limit <= 0:
        raise ConfigurationError("--test-limit must be a positive integer.")
    if args.workers <= 0:
        raise ConfigurationError("--workers must be a positive integer.")
    if args.max_retries < 0:
        raise ConfigurationError("--max-retries must be zero or positive.")
    if args.retry_delay < 0:
        raise ConfigurationError("--retry-delay must be zero or positive.")
    if args.start_corpus_id is not None and not args.start_corpus_id.strip():
        raise ConfigurationError("--start-corpus-id must not be empty.")

    if not args.audio_index.exists() or not args.audio_index.is_file():
        raise ConfigurationError(f"Audio index file is missing or unreadable: {args.audio_index}")

    if not args.input_dir.exists() or not args.input_dir.is_dir():
        raise ConfigurationError(f"Input audio directory does not exist: {args.input_dir}")

    if not args.prompt_file.exists() or not args.prompt_file.is_file():
        raise ConfigurationError(f"Prompt file is missing or unreadable: {args.prompt_file}")

    if not args.env_file.exists() or not args.env_file.is_file():
        raise ConfigurationError(f"Environment file is missing: {args.env_file}")

    # Explicitly check for GEMINI_API_KEY
    load_dotenv(args.env_file)
    import os
    if not os.getenv("GEMINI_API_KEY"):
        raise ConfigurationError(f"GEMINI_API_KEY not found in environment or {args.env_file}")

    try:
        args.output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigurationError(f"Could not create output directory: {exc}")


def load_audio_index(
        audio_index_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, int, list[dict[str, Any]]]:
    """Load and validate eligible audio records from the NDJSON audio index."""
    eligible_records: list[dict[str, Any]] = []
    invalid_records: list[dict[str, Any]] = []
    ignored_records: list[dict[str, Any]] = []
    total_records = 0

    with audio_index_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue

            total_records += 1

            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ConfigurationError(f"Invalid JSON in audio index at line {line_number}: {exc}")

            if not isinstance(record, dict):
                raise ConfigurationError(f"Invalid NDJSON object at line {line_number}.")

            status = record.get("download_status")
            if status not in ELIGIBLE_AUDIO_STATUSES:
                ignored_records.append(
                    {**make_item_base(record), "status": "ignored_audio_unavailable"}
                )
                continue

            corpus_id = record.get("corpus_id") or record.get("id")
            if not corpus_id or not str(corpus_id).strip():
                invalid_records.append(
                    {**make_item_base(record), "status": "failed_metadata", "error": "Missing corpus_id"}
                )
                continue

            record["corpus_id"] = str(corpus_id)
            eligible_records.append(record)

    if not eligible_records and not invalid_records:
        raise ConfigurationError("No eligible audio records found in audio index.")

    return eligible_records, invalid_records, total_records, len(ignored_records), ignored_records


def resolve_source_audio_path(record: dict[str, Any], input_dir: Path) -> Path:
    """Resolve source audio path using audio_file or fallback input directory."""
    audio_file = record.get("audio_file")
    if isinstance(audio_file, str) and audio_file.strip():
        return resolve_script_relative_path(Path(audio_file.strip()))
    return input_dir / f"{record['corpus_id']}{INPUT_AUDIO_EXTENSION}"


def make_item_base(record: dict[str, Any]) -> dict[str, Any]:
    """Return preserved source metadata fields from a source record."""
    return {field: record.get(field) for field in PRESERVED_METADATA_FIELDS if field in record}


def plan_transcriptions(
        records: list[dict[str, Any]],
        input_dir: Path,
        output_dir: Path,
        test_mode: bool,
        test_limit: int,
        reprocess: bool,
        start_corpus_id: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Create planned, skipped-existing, and missing-input records."""
    if start_corpus_id:
        start_index = next((i for i, r in enumerate(records) if r.get("corpus_id") == start_corpus_id), None)
        if start_index is None:
            raise ConfigurationError(f"--start-corpus-id was not found: {start_corpus_id}")
        records = records[start_index:]

    planned = []
    skipped = []
    missing = []

    for record in records:
        corpus_id = record["corpus_id"]
        audio_path = resolve_source_audio_path(record, input_dir)
        text_out = output_dir / f"{corpus_id}{OUTPUT_TEXT_EXTENSION}"
        json_out = output_dir / f"{corpus_id}{OUTPUT_JSON_EXTENSION}"

        item = {
            "record": record,
            "corpus_id": corpus_id,
            "input_audio_path": audio_path,
            "text_output_path": text_out,
            "json_output_path": json_out,
        }

        if not audio_path.exists():
            missing.append(item)
            continue

        if text_out.exists() and json_out.exists() and not reprocess:
            skipped.append(item)
            continue

        planned.append(item)

    if test_mode:
        planned = planned[:test_limit]

    return planned, skipped, missing


def get_mime_type(path: Path) -> str:
    """Determine MIME type based on extension."""
    ext = path.suffix.lower()
    return SUPPORTED_FORMATS.get(ext, "audio/wav")


def transcribe_one_item(
        client: genai.Client,
        item: dict[str, Any],
        model_config: dict[str, Any],
        prompt_text: str,
        max_retries: int,
        retry_delay: int,
        logger: logging.Logger,
) -> dict[str, Any]:
    """Uploads audio, generates transcription using Gemini, and cleans up."""
    corpus_id = item["corpus_id"]
    audio_path = item["input_audio_path"]
    text_out = item["text_output_path"]
    json_out = item["json_output_path"]
    record = item["record"]

    mime_type = get_mime_type(audio_path)
    start_time = utc_timestamp()
    monotonic_start = time.monotonic()

    total_attempts = max_retries + 1
    retries_used = 0
    final_error = None

    for attempt in range(1, total_attempts + 1):
        try:
            logger.info("Transcription attempt %s/%s for %s", attempt, total_attempts, corpus_id)

            uploaded_file = client.files.upload(
                file=str(audio_path),
                config=types.UploadFileConfig(mime_type=mime_type),
            )

            try:
                response = client.models.generate_content(
                    model=model_config["model_name"],
                    contents=[uploaded_file, prompt_text],
                )
                transcript_text = response.text.strip()
            finally:
                client.files.delete(name=uploaded_file.name)

            end_time = utc_timestamp()
            duration = round(time.monotonic() - monotonic_start, 3)

            result_json = {
                "corpus_id": corpus_id,
                "input_audio_path": str(audio_path),
                "text_output_path": str(text_out),
                "json_output_path": str(json_out),
                "model": model_config,
                "transcription": {
                    "text": transcript_text,
                },
                "metadata": {
                    "youtube_id": record.get("youtube_id", record.get("id")),
                    "title_extracted": record.get("title"),
                    **make_item_base(record)
                },
                "run": {
                    "transcription_run_id": model_config["run_id"],
                    "transcribed_at_utc": end_time,
                },
                "status": "success",
                "error": None,
            }

            text_out.write_text(transcript_text + "\n", encoding="utf-8")
            json_out.write_text(json.dumps(result_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            logger.info("SUCCESS %s -> %s", corpus_id, text_out)

            return make_item_base(record) | {
                "corpus_id": corpus_id,
                "input_audio_path": str(audio_path),
                "text_output_path": str(text_out),
                "json_output_path": str(json_out),
                "status": "success",
                "error": None,
                "retries": retries_used,
                "duration_seconds": duration,
                "start_time": start_time,
                "end_time": end_time,
                "transcript_characters": len(transcript_text),
                "metadata": make_item_base(record),
            }

        except Exception as exc:
            final_error = str(exc)
            logger.error("FAILED attempt %s for %s: %s", attempt, corpus_id, final_error)

            if attempt < total_attempts:
                retries_used += 1
                logger.info("Retrying %s after %s seconds", corpus_id, retry_delay)
                if retry_delay:
                    time.sleep(retry_delay)

    end_time = utc_timestamp()
    duration = round(time.monotonic() - monotonic_start, 3)

    return make_item_base(record) | {
        "corpus_id": corpus_id,
        "input_audio_path": str(audio_path),
        "text_output_path": str(text_out),
        "json_output_path": str(json_out),
        "status": "failed",
        "error": final_error or "Transcription generation failed.",
        "retries": retries_used,
        "duration_seconds": duration,
        "start_time": start_time,
        "end_time": end_time,
        "transcript_characters": None,
        "metadata": make_item_base(record),
    }


def make_skipped_existing_result(item: dict[str, Any], model_config: dict[str, Any], logger: logging.Logger) -> dict[str, Any]:
    """Create a manifest item for a skipped complete transcription pair."""
    logger.info("SKIPPED_EXISTING %s -> %s", item["corpus_id"], item["text_output_path"])
    return make_item_base(item["record"]) | {
        "corpus_id": item["corpus_id"],
        "input_audio_path": str(item["input_audio_path"]),
        "text_output_path": str(item["text_output_path"]),
        "json_output_path": str(item["json_output_path"]),
        "status": "skipped_existing",
        "error": None,
        "retries": 0,
        "metadata": make_item_base(item["record"]),
        "model_name": model_config["model_name"],
    }


def make_missing_input_result(item: dict[str, Any], logger: logging.Logger) -> dict[str, Any]:
    """Create a manifest item for a missing source audio file."""
    error = f"Source audio file is missing: {item['input_audio_path']}"
    logger.error("MISSING_INPUT %s: %s", item["corpus_id"], item["input_audio_path"])
    return make_item_base(item["record"]) | {
        "corpus_id": item["corpus_id"],
        "input_audio_path": str(item["input_audio_path"]),
        "text_output_path": str(item["text_output_path"]),
        "json_output_path": str(item["json_output_path"]),
        "status": "missing_input",
        "error": error,
        "retries": 0,
        "metadata": make_item_base(item["record"]),
    }


def make_transcription_index_record(item: dict[str, Any], model_config: dict[str, Any]) -> dict[str, Any]:
    """Build one curated transcription index record."""
    record = {field: item.get(field) for field in PRESERVED_METADATA_FIELDS if field in item}
    record.update({
        "corpus_id": item.get("corpus_id"),
        "title_extracted": item.get("metadata", {}).get("title"),
        "youtube_id": item.get("metadata", {}).get("id"),
        "youtube_url": item.get("metadata", {}).get("url"),
        "audio_file": item.get("input_audio_path") or item.get("audio_file"),
        "transcript_text_file": item.get("text_output_path"),
        "transcript_json_file": item.get("json_output_path"),
        "transcription_status": item.get("status"),
        "transcription_run_id": model_config["run_id"],
        "transcribed_at_utc": item.get("end_time"),
        "model_name": model_config["model_name"],
        "prompt_file": model_config["prompt_file"],
        "download_status": item.get("metadata", {}).get("download_status"),
        "error": item.get("error"),
    })
    return record


def write_transcription_index(index_records: list[dict[str, Any]], index_file: Path) -> None:
    """Write curated NDJSON transcription index."""
    index_file.parent.mkdir(parents=True, exist_ok=True)
    with index_file.open("w", encoding="utf-8") as handle:
        for record in index_records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_manifests(manifest: dict[str, Any], manifest_file: Path, run_id: str) -> tuple[Path, Path]:
    """Write latest and timestamped manifest files."""
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    per_run_manifest_file = manifest_file.parent / f"{manifest_file.stem}_{run_id}{manifest_file.suffix}"

    manifest_json = json.dumps(manifest, ensure_ascii=False, indent=2)
    manifest_file.write_text(manifest_json + "\n", encoding="utf-8")
    per_run_manifest_file.write_text(manifest_json + "\n", encoding="utf-8")

    return manifest_file, per_run_manifest_file


def main() -> int:
    """Run the batch music video transcription workflow."""
    args = None
    logger = None
    run_id = make_run_id()
    start_time = utc_timestamp()

    manifest_items = []
    invalid_records = []
    ignored_records = []
    total_records = 0
    eligible_count = 0
    ignored_count = 0
    planned_count = 0
    attempted_count = 0

    try:
        args = parse_args()
        validate_args(args)
        logger = setup_logging(args.log_file)

        logger.info("Starting %s run_id=%s", TOOL_NAME, run_id)
        logger.info("Audio index: %s", args.audio_index)
        logger.info("Input dir: %s", args.input_dir)
        logger.info("Output dir: %s", args.output_dir)
        logger.info("Model: %s", args.model_name)

        prompt_text = args.prompt_file.read_text(encoding="utf-8").strip()

        eligible_records, invalid_records, total_records, ignored_count, ignored_records = load_audio_index(args.audio_index)
        eligible_count = len(eligible_records) + len(invalid_records)

        planned, skipped_existing, missing_input = plan_transcriptions(
            records=eligible_records,
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            test_mode=args.test_mode,
            test_limit=args.test_limit,
            reprocess=args.reprocess,
            start_corpus_id=args.start_corpus_id,
        )

        planned_count = len(planned)

        model_config = {
            "model_name": args.model_name,
            "prompt_file": str(args.prompt_file.name),
            "run_id": run_id,
        }

        for item in skipped_existing:
            manifest_items.append(make_skipped_existing_result(item, model_config, logger))

        for item in missing_input:
            manifest_items.append(make_missing_input_result(item, logger))

        client = None
        if planned:
            client = genai.Client(vertexai=False)
            logger.info("Instantiated Gemini client")

        for idx, item in enumerate(planned):
            attempted_count += 1
            manifest_items.append(
                transcribe_one_item(
                    client=client,
                    item=item,
                    model_config=model_config,
                    prompt_text=prompt_text,
                    max_retries=args.max_retries,
                    retry_delay=args.retry_delay,
                    logger=logger,
                )
            )
            if idx < len(planned) - 1:
                time.sleep(args.request_delay)

        succeeded = sum(1 for i in manifest_items if i.get("status") == "success")
        failed = sum(1 for i in manifest_items if i.get("status") == "failed")
        missing_count = sum(1 for i in manifest_items if i.get("status") == "missing_input")
        skipped_count = sum(1 for i in manifest_items if i.get("status") == "skipped_existing")

        index_records = [
            make_transcription_index_record(item, model_config)
            for item in [*manifest_items, *invalid_records]
            if item.get("status") in {"success", "failed", "skipped_existing", "missing_input", "failed_metadata"}
        ]
        write_transcription_index(index_records, args.transcript_index_file)

        summary = {
            "audio_index_records": total_records,
            "eligible_audio_records": eligible_count,
            "ignored_audio_records": ignored_count,
            "invalid_metadata": len(invalid_records),
            "planned": planned_count,
            "attempted": attempted_count,
            "succeeded": succeeded,
            "failed": failed,
            "missing_input": missing_count,
            "skipped_existing": skipped_count,
        }

        manifest = {
            "run_metadata": {
                "run_id": run_id,
                "tool_name": TOOL_NAME,
                "tool_version": TOOL_VERSION,
                "start_time": start_time,
                "end_time": utc_timestamp(),
                "test_mode": args.test_mode,
                "test_limit": args.test_limit,
                "reprocess": args.reprocess,
                "workers": args.workers,
                "audio_index_path": str(args.audio_index),
                "input_dir": str(args.input_dir),
                "output_dir": str(args.output_dir),
                "prompt_file": str(args.prompt_file),
                "env_file": str(args.env_file),
                "config": {
                    "model_name": args.model_name,
                    "request_delay_seconds": args.request_delay,
                    "max_retries": args.max_retries,
                    "retry_delay_seconds": args.retry_delay,
                    "start_corpus_id": args.start_corpus_id,
                },
                "summary": summary,
                "interrupted": False,
            },
            "items": manifest_items,
            "invalid_records": invalid_records,
            "ignored_records": ignored_records,
        }

        write_manifests(manifest, args.manifest_file, run_id)

        logger.info(
            "Finished run: succeeded=%s failed=%s skipped_existing=%s missing_input=%s invalid_metadata=%s",
            succeeded, failed, skipped_count, missing_count, len(invalid_records)
        )

        if failed or missing_count or invalid_records:
            return 1
        return 0

    except KeyboardInterrupt:
        if logger:
            logger.error("Interrupted by user.")
        return 130
    except ConfigurationError as exc:
        msg = f"Configuration error: {exc}"
        if logger:
            logger.error(msg)
        else:
            print(msg, file=sys.stderr)
        return 2
    except Exception as exc:
        msg = f"Unexpected error: {exc}"
        if logger:
            logger.exception(msg)
        else:
            print(msg, file=sys.stderr)
        return 2

if __name__ == "__main__":
    sys.exit(main())