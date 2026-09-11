#!/usr/bin/env python3
"""
gere_llm_avaliacao.py

Generate LLM assessments of compositions from a directory of source documents.

The programme supports one command:

1. avalie
   Recursively parse all text/Markdown files in --input-dir. For each composition,
   send the prompt document specified by --prompt plus the composition contents to
   the selected LLM. The response is written as a Markdown document to --output-dir,
   preserving the input subdirectory structure.

Output filenames:
- The first five digits found at the beginning of the input filename are used as
  the composition ID.
- The output filename is:
      <ID>_avaliacao_<model>.md

Example:

    python gere_llm_avaliacao.py avalie \\
      --input-dir corpus/01_composicoes \\
      --output-dir corpus/04_composicoes_avaliadas \\
      --model gpt-5.6-sol \\
      --prompt prompts_de_avaliacao_de_composicoes/avaliacao_de_composicao_v1.md \\
      --test-mode

Model routing:
- Models whose name starts with "gemini-" use the Gemini API.
- Other models, including "gpt-5.6-sol", use the OpenAI API.

Important:
- The OpenAI model "gpt-5.6-sol" does not support the temperature argument, so
  this programme never sends temperature for that model.
- If another OpenAI model rejects temperature, the programme retries without it
  and remembers that model as temperature-unsupported for the current run.

Environment:
- OPENAI_API_KEY is required for OpenAI models.
- GEMINI_API_KEY is required for Gemini models.
- By default, environment variables are also loaded from env/.env when present.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import logging
import os
import re
import sys
import threading
import time
import traceback
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROGRAMME_NAME = "gere_llm_avaliacao.py"
PROGRAMME_VERSION = "v1"

COMMAND_AVALIE = "avalie"

SUPPORTED_INPUT_SUFFIXES = {".txt", ".md", ".markdown"}

DEFAULT_ENV_FILE = "env/.env"
DEFAULT_MODEL = "gpt-5.6-sol"
DEFAULT_TEMPERATURE = 0.0
DEFAULT_TEST_MODE = False
DEFAULT_TEST_LIMIT = 5
DEFAULT_WORKERS = 1
DEFAULT_MAX_RETRIES = 2
DEFAULT_RETRY_BACKOFF_SECONDS = 5.0
DEFAULT_REQUEST_DELAY_SECONDS = 0.0

OPENAI_MODEL_PREFIXES = ("gpt-", "o")
GEMINI_MODEL_PREFIXES = ("gemini-",)

# Explicitly known unsupported model.
TEMPERATURE_UNSUPPORTED_MODELS: set[str] = {"gpt-5.6-sol"}
TEMPERATURE_SUPPORT_LOCK = threading.Lock()


class ConfigurationError(Exception):
    """Raised when command-line options or runtime configuration are invalid."""


@dataclass(frozen=True)
class Config:
    script_dir: Path
    run_id: str

    command: str
    input_dir: Path
    output_dir: Path
    model: str
    prompt: Path
    env_file: Path

    temperature: float | None
    test_mode: bool
    test_limit: int
    start_filename: str | None
    reprocess: bool
    workers: int
    max_retries: int
    retry_backoff_seconds: float
    request_delay_seconds: float

    log_file: Path
    manifest_file: Path
    timestamped_manifest_file: Path


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Return an ISO-like UTC timestamp without microseconds."""
    return utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_run_id() -> str:
    """Return a compact run ID suitable for filenames."""
    return utc_now().strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]


def natural_sort_key(value: str) -> list[Any]:
    """Return a natural-sort key for filenames/paths containing numbers."""
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


def resolve_path(path_value: str | Path, base_dir: Path) -> Path:
    """Resolve a path relative to base_dir unless it is already absolute."""
    path = Path(path_value).expanduser()
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def relpath(path: Path, base_dir: Path) -> str:
    """Return path relative to base_dir when possible."""
    try:
        return str(path.resolve().relative_to(base_dir.resolve()))
    except ValueError:
        return str(path.resolve())


def read_text_file(path: Path) -> str:
    """Read a UTF-8 text file."""
    return path.read_text(encoding="utf-8")


def write_text_file(path: Path, text: str) -> None:
    """Write a UTF-8 text file, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_json_file(path: Path, data: dict[str, Any]) -> None:
    """Write a JSON file, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_text(text: str) -> str:
    """Return the SHA-256 hash of text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe_model_name_for_filename(model: str) -> str:
    """Return a filesystem-friendly model name."""
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", model.strip())
    return safe.strip("._-") or "modelo"


def composition_id_from_filename(input_file: Path) -> str:
    """
    Return the first five digits of the input filename.

    The expected corpus filenames begin with a five-digit composition ID, e.g.:
    - 36560.txt
    - 36560_composicao_gpt-5.6-sol.md
    """
    match = re.match(r"^(\d{5})", input_file.name)
    if not match:
        raise ValueError(
            f"Input filename does not start with five digits: {input_file.name}"
        )
    return match.group(1)


def model_family(model: str) -> str:
    """Return the provider family for a model name."""
    model_lower = model.lower().strip()
    if model_lower.startswith(GEMINI_MODEL_PREFIXES):
        return "gemini"
    if model_lower.startswith(OPENAI_MODEL_PREFIXES):
        return "openai"

    # Conservative default for this project.
    return "openai"


def load_dotenv_file(path: Path) -> bool:
    """
    Minimal .env loader.

    Supports simple KEY=VALUE lines. Existing process environment variables are
    not overwritten.
    """
    if not path.exists():
        return False

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        if line.startswith("export "):
            line = line[len("export ") :].strip()

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not key:
            continue

        if (
            (value.startswith('"') and value.endswith('"'))
            or (value.startswith("'") and value.endswith("'"))
        ):
            value = value[1:-1]

        os.environ.setdefault(key, value)

    return True


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Generate LLM assessments for composition files."
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    command_parser = subparsers.add_parser(
        COMMAND_AVALIE,
        help="Assess compositions",
    )

    command_parser.add_argument("--input-dir", required=True, type=Path)
    command_parser.add_argument("--output-dir", required=True, type=Path)
    command_parser.add_argument("--model", required=True, default=DEFAULT_MODEL)
    command_parser.add_argument("--prompt", required=True, type=Path)
    command_parser.add_argument("--env-file", default=DEFAULT_ENV_FILE, type=Path)

    command_parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)

    test_mode = command_parser.add_mutually_exclusive_group()
    test_mode.add_argument("--test-mode", action="store_true", dest="test_mode")
    test_mode.add_argument("--no-test-mode", action="store_false", dest="test_mode")
    command_parser.set_defaults(test_mode=DEFAULT_TEST_MODE)

    command_parser.add_argument("--test-limit", type=int, default=DEFAULT_TEST_LIMIT)
    command_parser.add_argument("--start-filename", default=None)
    command_parser.add_argument("--reprocess", action="store_true")
    command_parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    command_parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    command_parser.add_argument(
        "--retry-backoff-seconds",
        type=float,
        default=DEFAULT_RETRY_BACKOFF_SECONDS,
    )
    command_parser.add_argument(
        "--request-delay-seconds",
        type=float,
        default=DEFAULT_REQUEST_DELAY_SECONDS,
    )

    command_parser.add_argument("--log-file", default=None, type=Path)
    command_parser.add_argument("--manifest-file", default=None, type=Path)

    return parser


def make_config(args: argparse.Namespace) -> Config:
    """Create a validated path-oriented configuration object."""
    script_dir = Path(__file__).resolve().parent
    run_id = make_run_id()

    output_dir = resolve_path(args.output_dir, script_dir)

    log_file = (
        resolve_path(args.log_file, script_dir)
        if args.log_file
        else output_dir / "gere_llm_avaliacao.log"
    )
    manifest_file = (
        resolve_path(args.manifest_file, script_dir)
        if args.manifest_file
        else output_dir / "gere_llm_avaliacao_manifest.json"
    )
    timestamped_manifest_file = (
        manifest_file.parent / f"{manifest_file.stem}_{run_id}{manifest_file.suffix}"
    )

    return Config(
        script_dir=script_dir,
        run_id=run_id,
        command=args.command,
        input_dir=resolve_path(args.input_dir, script_dir),
        output_dir=output_dir,
        model=args.model.strip(),
        prompt=resolve_path(args.prompt, script_dir),
        env_file=resolve_path(args.env_file, script_dir),
        temperature=args.temperature,
        test_mode=args.test_mode,
        test_limit=args.test_limit,
        start_filename=args.start_filename,
        reprocess=args.reprocess,
        workers=args.workers,
        max_retries=args.max_retries,
        retry_backoff_seconds=args.retry_backoff_seconds,
        request_delay_seconds=args.request_delay_seconds,
        log_file=log_file,
        manifest_file=manifest_file,
        timestamped_manifest_file=timestamped_manifest_file,
    )


def setup_logging(config: Config) -> None:
    """Configure append-only UTF-8 file and console logging."""
    config.log_file.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)-5s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(config.log_file, mode="a", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )


def validate_config(config: Config) -> None:
    """Validate command-line arguments and filesystem paths."""
    if config.command != COMMAND_AVALIE:
        raise ConfigurationError(f"Unsupported command: {config.command}")

    if not config.model:
        raise ConfigurationError("--model must not be blank.")

    if config.temperature is not None and config.temperature < 0:
        raise ConfigurationError("--temperature must be greater than or equal to 0.")

    if config.test_limit <= 0:
        raise ConfigurationError("--test-limit must be a positive integer.")

    if config.workers <= 0:
        raise ConfigurationError("--workers must be a positive integer.")

    if config.max_retries < 0:
        raise ConfigurationError("--max-retries must be zero or positive.")

    if config.retry_backoff_seconds < 0:
        raise ConfigurationError("--retry-backoff-seconds must be zero or positive.")

    if config.request_delay_seconds < 0:
        raise ConfigurationError("--request-delay-seconds must be zero or positive.")

    if config.start_filename is not None and not config.start_filename.strip():
        raise ConfigurationError("--start-filename must not be empty.")

    if not config.input_dir.exists() or not config.input_dir.is_dir():
        raise ConfigurationError(
            f"Input directory does not exist: {relpath(config.input_dir, config.script_dir)}"
        )

    if not config.prompt.exists() or not config.prompt.is_file():
        raise ConfigurationError(
            f"Prompt file is missing or unreadable: {relpath(config.prompt, config.script_dir)}"
        )

    config.output_dir.mkdir(parents=True, exist_ok=True)


def validate_environment_for_model(config: Config) -> dict[str, Any]:
    """Load environment variables and validate required API key."""
    env_file_found = load_dotenv_file(config.env_file)
    family = model_family(config.model)

    openai_api_key_available = bool(os.environ.get("OPENAI_API_KEY"))
    gemini_api_key_available = bool(os.environ.get("GEMINI_API_KEY"))

    environment_metadata = {
        "env_file": relpath(config.env_file, config.script_dir),
        "env_file_found": env_file_found,
        "model_family": family,
        "openai_api_key_available": openai_api_key_available,
        "gemini_api_key_available": gemini_api_key_available,
        "api_keys_logged": False,
    }

    if family == "openai" and not openai_api_key_available:
        raise ConfigurationError(
            "OPENAI_API_KEY is not available in the process environment "
            f"or in {relpath(config.env_file, config.script_dir)}."
        )

    if family == "gemini" and not gemini_api_key_available:
        raise ConfigurationError(
            "GEMINI_API_KEY is not available in the process environment "
            f"or in {relpath(config.env_file, config.script_dir)}."
        )

    return environment_metadata


def load_prompt(path: Path) -> str:
    """Load the prompt document."""
    prompt_text = read_text_file(path).strip()
    if not prompt_text:
        raise ConfigurationError(f"Prompt file is empty: {path}")
    return prompt_text


def discover_input_files(config: Config) -> list[Path]:
    """Discover eligible input files recursively in natural path order."""
    files = [
        path
        for path in config.input_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_INPUT_SUFFIXES
    ]

    files.sort(
        key=lambda item: natural_sort_key(
            str(item.relative_to(config.input_dir))
        )
    )

    if not files:
        raise ConfigurationError(
            f"No supported input files found in: {relpath(config.input_dir, config.script_dir)}"
        )

    if config.start_filename:
        matching_indexes = [
            index
            for index, path in enumerate(files)
            if path.name == config.start_filename
            or str(path.relative_to(config.input_dir)) == config.start_filename
        ]

        if not matching_indexes:
            raise ConfigurationError(
                f"--start-filename not found in input directory tree: {config.start_filename}"
            )

        files = files[matching_indexes[0] :]

    if config.test_mode:
        files = files[: config.test_limit]

    return files


def output_path_for_input(config: Config, input_file: Path) -> Path:
    """Return the mirrored output Markdown path for a given input file."""
    model_name = safe_model_name_for_filename(config.model)
    composition_id = composition_id_from_filename(input_file)
    relative_parent = input_file.relative_to(config.input_dir).parent
    output_stem = f"{composition_id}_avaliacao_{model_name}"

    return config.output_dir / relative_parent / f"{output_stem}.md"


def build_llm_request(prompt_text: str, input_file: Path, input_text: str) -> str:
    """Combine prompt and composition document into one stateless LLM request."""
    composition_id = composition_id_from_filename(input_file)

    return (
        f"{prompt_text}\n\n"
        f"---\n\n"
        f"## Metadados da tarefa\n\n"
        f"- Tarefa: Avaliação de redação\n"
        f"- ID da Redação: {composition_id}\n"
        f"- Ficheiro de entrada: {input_file.name}\n\n"
        f"---\n\n"
        f"## Documento da Redação a Avaliar\n\n"
        f"{input_text.strip()}"
    )


def extract_openai_response_text(response: Any) -> str:
    """Extract text from an OpenAI Responses API result robustly."""
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    output = getattr(response, "output", None)
    parts: list[str] = []

    if output:
        for item in output:
            content = getattr(item, "content", None)
            if not content:
                continue
            for content_item in content:
                text = getattr(content_item, "text", None)
                if text:
                    parts.append(str(text))

    return "\n".join(parts).strip()


def openai_metadata_from_response(response: Any) -> dict[str, Any]:
    """Extract selected metadata from an OpenAI response."""
    metadata: dict[str, Any] = {}

    for attr in ("id", "model", "created_at", "status"):
        value = getattr(response, attr, None)
        if value is not None:
            metadata[attr] = value

    usage = getattr(response, "usage", None)
    if usage is not None:
        try:
            if hasattr(usage, "model_dump"):
                metadata["usage"] = usage.model_dump()
            elif hasattr(usage, "dict"):
                metadata["usage"] = usage.dict()
            else:
                metadata["usage"] = str(usage)
        except Exception:
            metadata["usage"] = str(usage)

    return metadata


def gemini_metadata_from_response(response: Any) -> dict[str, Any]:
    """Extract selected metadata from a Gemini response."""
    metadata: dict[str, Any] = {}

    usage_metadata = getattr(response, "usage_metadata", None)
    if usage_metadata is not None:
        try:
            if hasattr(usage_metadata, "model_dump"):
                metadata["usage_metadata"] = usage_metadata.model_dump()
            elif hasattr(usage_metadata, "to_json_dict"):
                metadata["usage_metadata"] = usage_metadata.to_json_dict()
            else:
                metadata["usage_metadata"] = str(usage_metadata)
        except Exception:
            metadata["usage_metadata"] = str(usage_metadata)

    candidates = getattr(response, "candidates", None)
    if candidates is not None:
        metadata["candidate_count"] = len(candidates)

    return metadata


def make_openai_client() -> Any:
    """Instantiate an OpenAI client."""
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ImportError(
            "The OpenAI Python SDK is unavailable. Install it with: pip install openai"
        ) from exc

    return OpenAI()


def make_gemini_client() -> Any:
    """Instantiate a Gemini client."""
    try:
        from google import genai
    except ImportError as exc:
        raise ImportError(
            "The Google GenAI Python SDK is unavailable. Install it with: pip install google-genai"
        ) from exc

    return genai.Client(vertexai=False)


def make_llm_client(config: Config) -> Any:
    """Instantiate the correct LLM client for the configured model."""
    family = model_family(config.model)

    if family == "gemini":
        return make_gemini_client()

    return make_openai_client()


def call_openai_with_retries(
    client: Any,
    *,
    model: str,
    prompt: str,
    temperature: float | None,
    max_retries: int,
    retry_backoff_seconds: float,
) -> tuple[str, dict[str, Any], bool]:
    """Call the OpenAI Responses API with retry and temperature fallback."""
    last_error: BaseException | None = None

    for attempt in range(max_retries + 1):
        try:
            kwargs: dict[str, Any] = {
                "model": model,
                "input": prompt,
            }

            temperature_sent = False

            with TEMPERATURE_SUPPORT_LOCK:
                model_supports_temperature = model not in TEMPERATURE_UNSUPPORTED_MODELS

            if temperature is not None and model_supports_temperature:
                kwargs["temperature"] = temperature
                temperature_sent = True

            try:
                response = client.responses.create(**kwargs)
            except TypeError:
                kwargs.pop("temperature", None)
                temperature_sent = False
                with TEMPERATURE_SUPPORT_LOCK:
                    TEMPERATURE_UNSUPPORTED_MODELS.add(model)
                response = client.responses.create(**kwargs)
            except Exception as exc:
                error_text = str(exc)
                if (
                    "Unsupported parameter" in error_text
                    and "temperature" in error_text
                    and "temperature" in kwargs
                ):
                    logging.warning(
                        "Model %s does not support temperature; retrying without temperature.",
                        model,
                    )
                    kwargs.pop("temperature", None)
                    temperature_sent = False
                    with TEMPERATURE_SUPPORT_LOCK:
                        TEMPERATURE_UNSUPPORTED_MODELS.add(model)
                    response = client.responses.create(**kwargs)
                else:
                    raise

            response_text = extract_openai_response_text(response)
            if not response_text.strip():
                raise ValueError("OpenAI response contains no usable text.")

            return response_text.strip(), openai_metadata_from_response(response), temperature_sent

        except Exception as exc:
            last_error = exc
            if attempt >= max_retries:
                break

            sleep_for = retry_backoff_seconds * (2 ** attempt)
            logging.warning(
                "OpenAI request failed on attempt %s/%s: %s",
                attempt + 1,
                max_retries + 1,
                exc,
            )
            if sleep_for > 0:
                time.sleep(sleep_for)

    raise RuntimeError(
        f"OpenAI request failed after {max_retries + 1} attempt(s): {last_error}"
    ) from last_error


def call_gemini_with_retries(
    client: Any,
    *,
    model: str,
    prompt: str,
    max_retries: int,
    retry_backoff_seconds: float,
) -> tuple[str, dict[str, Any], bool]:
    """Call the Gemini API with retries."""
    last_error: BaseException | None = None

    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=[prompt],
            )

            response_text = getattr(response, "text", None)
            if not isinstance(response_text, str) or not response_text.strip():
                raise ValueError("Gemini response contains no usable text.")

            return response_text.strip(), gemini_metadata_from_response(response), False

        except Exception as exc:
            last_error = exc
            if attempt >= max_retries:
                break

            sleep_for = retry_backoff_seconds * (2 ** attempt)
            logging.warning(
                "Gemini request failed on attempt %s/%s: %s",
                attempt + 1,
                max_retries + 1,
                exc,
            )
            if sleep_for > 0:
                time.sleep(sleep_for)

    raise RuntimeError(
        f"Gemini request failed after {max_retries + 1} attempt(s): {last_error}"
    ) from last_error


def call_llm_with_retries(
    client: Any,
    *,
    config: Config,
    prompt: str,
) -> tuple[str, dict[str, Any], bool]:
    """Call the configured LLM provider."""
    family = model_family(config.model)

    if family == "gemini":
        return call_gemini_with_retries(
            client,
            model=config.model,
            prompt=prompt,
            max_retries=config.max_retries,
            retry_backoff_seconds=config.retry_backoff_seconds,
        )

    return call_openai_with_retries(
        client,
        model=config.model,
        prompt=prompt,
        temperature=config.temperature,
        max_retries=config.max_retries,
        retry_backoff_seconds=config.retry_backoff_seconds,
    )


def process_one_file(
    input_file: Path,
    *,
    config: Config,
    client: Any,
    prompt_text: str,
    prompt_sha256: str,
    environment_metadata: dict[str, Any],
) -> dict[str, Any]:
    """Process one input file."""
    start_monotonic = time.monotonic()
    started_at = utc_now_iso()
    output_file = output_path_for_input(config, input_file)

    item: dict[str, Any] = {
        "input_filename": input_file.name,
        "input_file": relpath(input_file, config.script_dir),
        "input_relative_file": str(input_file.relative_to(config.input_dir)),
        "output_file": relpath(output_file, config.script_dir),
        "command": config.command,
        "model": config.model,
        "model_family": model_family(config.model),
        "prompt_file": relpath(config.prompt, config.script_dir),
        "prompt_sha256": prompt_sha256,
        "environment": environment_metadata,
        "status": "started",
        "submitted_to_llm": False,
        "temperature": config.temperature,
        "temperature_sent_to_api": False,
        "composition_id": None,
        "input_sha256": None,
        "output_sha256": None,
        "api_metadata": {},
        "started_at": started_at,
        "ended_at": None,
        "duration_seconds": None,
        "error": None,
    }

    try:
        composition_id = composition_id_from_filename(input_file)
        item["composition_id"] = composition_id

        if output_file.exists() and not config.reprocess:
            existing_text = read_text_file(output_file)
            item.update(
                {
                    "status": "skipped_existing",
                    "submitted_to_llm": False,
                    "output_sha256": sha256_text(existing_text),
                    "ended_at": utc_now_iso(),
                    "duration_seconds": round(time.monotonic() - start_monotonic, 3),
                }
            )
            logging.info(
                "SKIPPED_EXISTING %s -> %s",
                str(input_file.relative_to(config.input_dir)),
                str(output_file.relative_to(config.output_dir)),
            )
            return item

        input_text = read_text_file(input_file)
        if not input_text.strip():
            raise ValueError(f"Input file is empty: {input_file.name}")

        item["input_sha256"] = sha256_text(input_text)

        request_text = build_llm_request(
            prompt_text,
            input_file,
            input_text,
        )
        item["request_sha256"] = sha256_text(request_text)

        response_text, api_metadata, temperature_sent = call_llm_with_retries(
            client,
            config=config,
            prompt=request_text,
        )

        write_text_file(output_file, response_text)

        item.update(
            {
                "status": "success",
                "submitted_to_llm": True,
                "temperature_sent_to_api": temperature_sent,
                "output_sha256": sha256_text(response_text),
                "api_metadata": api_metadata,
                "ended_at": utc_now_iso(),
                "duration_seconds": round(time.monotonic() - start_monotonic, 3),
                "response_characters": len(response_text),
            }
        )

        logging.info(
            "SUCCESS %s -> %s",
            str(input_file.relative_to(config.input_dir)),
            str(output_file.relative_to(config.output_dir)),
        )
        return item

    except Exception as exc:
        item.update(
            {
                "status": "failed",
                "error": str(exc),
                "ended_at": utc_now_iso(),
                "duration_seconds": round(time.monotonic() - start_monotonic, 3),
            }
        )

        logging.error(
            "FAILED %s: %s",
            str(input_file.relative_to(config.input_dir)),
            exc,
        )
        logging.debug(
            "Traceback for %s:\n%s",
            str(input_file.relative_to(config.input_dir)),
            traceback.format_exc(),
        )
        return item


def build_manifest(
    config: Config,
    *,
    start_time: str,
    end_time: str,
    prompt_text: str,
    prompt_sha256: str,
    environment_metadata: dict[str, Any],
    discovered_count: int,
    planned_files: list[Path],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the run manifest."""
    succeeded = sum(1 for item in results if item.get("status") == "success")
    failed = sum(1 for item in results if item.get("status") == "failed")
    skipped = sum(1 for item in results if item.get("status") == "skipped_existing")
    submitted = sum(1 for item in results if item.get("submitted_to_llm"))

    return {
        "run_id": config.run_id,
        "programme": PROGRAMME_NAME,
        "programme_version": PROGRAMME_VERSION,
        "command": config.command,
        "start_time": start_time,
        "end_time": end_time,
        "paths": {
            "input_dir": relpath(config.input_dir, config.script_dir),
            "output_dir": relpath(config.output_dir, config.script_dir),
            "prompt": relpath(config.prompt, config.script_dir),
            "env_file": relpath(config.env_file, config.script_dir),
            "log_file": relpath(config.log_file, config.script_dir),
            "manifest_file": relpath(config.manifest_file, config.script_dir),
            "timestamped_manifest_file": relpath(
                config.timestamped_manifest_file,
                config.script_dir,
            ),
        },
        "environment": environment_metadata,
        "model_configuration": {
            "model": config.model,
            "model_family": model_family(config.model),
            "temperature": config.temperature,
            "temperature_unsupported_models_known_this_run": sorted(
                TEMPERATURE_UNSUPPORTED_MODELS
            ),
        },
        "prompt": {
            "file": relpath(config.prompt, config.script_dir),
            "sha256": prompt_sha256,
            "characters": len(prompt_text),
        },
        "processing": {
            "test_mode": config.test_mode,
            "test_limit": config.test_limit,
            "start_filename": config.start_filename,
            "reprocess": config.reprocess,
            "workers": config.workers,
            "max_retries": config.max_retries,
            "retry_backoff_seconds": config.retry_backoff_seconds,
            "request_delay_seconds": config.request_delay_seconds,
            "order": "natural_relative_path_order",
            "recursive": True,
            "mirrors_input_subdirectories": True,
            "supported_input_suffixes": sorted(SUPPORTED_INPUT_SUFFIXES),
        },
        "counts": {
            "files_discovered": discovered_count,
            "files_planned": len(planned_files),
            "submitted_to_llm": submitted,
            "succeeded": succeeded,
            "failed": failed,
            "skipped_existing": skipped,
        },
        "items": results,
    }


def main() -> int:
    """Run the batch workflow."""
    args = build_arg_parser().parse_args()
    config = make_config(args)

    setup_logging(config)
    run_start = utc_now_iso()

    logging.info("Starting %s run_id=%s", PROGRAMME_NAME, config.run_id)
    logging.info("Command: %s", config.command)
    logging.info("Input dir: %s", relpath(config.input_dir, config.script_dir))
    logging.info("Output dir: %s", relpath(config.output_dir, config.script_dir))
    logging.info("Model: %s", config.model)

    try:
        validate_config(config)
        environment_metadata = validate_environment_for_model(config)

        prompt_text = load_prompt(config.prompt)
        prompt_sha256 = sha256_text(prompt_text)

        all_discoverable_files = [
            path
            for path in config.input_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_INPUT_SUFFIXES
        ]
        discovered_count = len(all_discoverable_files)

        planned_files = discover_input_files(config)
        logging.info(
            "Discovered %s supported input files recursively; planned %s.",
            discovered_count,
            len(planned_files),
        )

        client = make_llm_client(config)
        results: list[dict[str, Any]] = []

        if config.workers == 1:
            for index, input_file in enumerate(planned_files):
                logging.info(
                    "Processing file: %s",
                    str(input_file.relative_to(config.input_dir)),
                )
                results.append(
                    process_one_file(
                        input_file,
                        config=config,
                        client=client,
                        prompt_text=prompt_text,
                        prompt_sha256=prompt_sha256,
                        environment_metadata=environment_metadata,
                    )
                )

                if index < len(planned_files) - 1 and config.request_delay_seconds > 0:
                    time.sleep(config.request_delay_seconds)
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=config.workers) as executor:
                future_to_file = {
                    executor.submit(
                        process_one_file,
                        input_file,
                        config=config,
                        client=client,
                        prompt_text=prompt_text,
                        prompt_sha256=prompt_sha256,
                        environment_metadata=environment_metadata,
                    ): input_file
                    for input_file in planned_files
                }

                for future in concurrent.futures.as_completed(future_to_file):
                    input_file = future_to_file[future]
                    try:
                        results.append(future.result())
                    except Exception as exc:
                        logging.error(
                            "Unexpected worker failure for %s: %s",
                            str(input_file.relative_to(config.input_dir)),
                            exc,
                        )
                        results.append(
                            {
                                "input_filename": input_file.name,
                                "input_file": relpath(input_file, config.script_dir),
                                "input_relative_file": str(
                                    input_file.relative_to(config.input_dir)
                                ),
                                "command": config.command,
                                "model": config.model,
                                "status": "failed",
                                "error": str(exc),
                            }
                        )

        run_end = utc_now_iso()
        manifest = build_manifest(
            config,
            start_time=run_start,
            end_time=run_end,
            prompt_text=prompt_text,
            prompt_sha256=prompt_sha256,
            environment_metadata=environment_metadata,
            discovered_count=discovered_count,
            planned_files=planned_files,
            results=results,
        )

        write_json_file(config.manifest_file, manifest)
        write_json_file(config.timestamped_manifest_file, manifest)

        logging.info(
            "Finished run_id=%s succeeded=%s failed=%s skipped_existing=%s",
            config.run_id,
            manifest["counts"]["succeeded"],
            manifest["counts"]["failed"],
            manifest["counts"]["skipped_existing"],
        )

        return 0 if manifest["counts"]["failed"] == 0 else 1

    except KeyboardInterrupt:
        logging.error("Interrupted by user.")
        return 130

    except Exception as exc:
        logging.error("Fatal error: %s", exc)
        logging.debug("Fatal traceback:\n%s", traceback.format_exc())

        fatal_manifest = {
            "run_id": config.run_id,
            "programme": PROGRAMME_NAME,
            "programme_version": PROGRAMME_VERSION,
            "command": config.command,
            "start_time": run_start,
            "end_time": utc_now_iso(),
            "status": "failed",
            "error": str(exc),
            "paths": {
                "input_dir": relpath(config.input_dir, config.script_dir),
                "output_dir": relpath(config.output_dir, config.script_dir),
                "prompt": relpath(config.prompt, config.script_dir),
                "log_file": relpath(config.log_file, config.script_dir),
                "manifest_file": relpath(config.manifest_file, config.script_dir),
            },
        }

        try:
            write_json_file(config.manifest_file, fatal_manifest)
            write_json_file(config.timestamped_manifest_file, fatal_manifest)
        except Exception:
            pass

        return 1


if __name__ == "__main__":
    raise SystemExit(main())