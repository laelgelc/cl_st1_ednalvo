# Specification Guidelines for Batch Processing Tools

These guidelines generalize the design and documentation pattern used in `transcribe_image_handwriting.py` so you can reuse it for other batch‑style tools, regardless of domain (NLP, image processing, data cleaning, etc.).

They focus on:

- Clear separation of concerns.
- Observability (logging, manifests).
- Resumability and safe re‑runs.
- Extensibility without breaking existing behavior.

You can treat this as a template when writing new specs.

---

## 1. Purpose and Scope

Every implementation should start with a short, focused **Purpose** section:

- Describe **what** the tool does in 1–3 sentences.
- Specify the **main data type** processed (e.g. text files, images, JSON records).
- Clarify the **primary goal**, e.g.:
  - “Normalize text for downstream NLP models.”
  - “Extract features from images for later classification.”
- Mention key design goals:
  - Batch processing.
  - Resumability (safe re‑runs).
  - Parallel execution.
  - Traceable logging and manifests.

This section should be high‑level and domain‑independent.

---

## 2. Input / Output

Define inputs and outputs precisely, independent of the tool’s specific function.

### 2.1. Input

- **Input data source**:
  - Typically a directory or a file list.
  - Specify whether discovery is:
    - Non‑recursive (files directly in a directory).
    - Recursive (walk subdirectories).
- **Supported formats**:
  - For files: list of supported extensions or MIME types.
  - For structured data: expected schema (e.g. JSON fields, CSV columns).
- **Configuration**:
  - Required environment variables (e.g. API keys, connection strings).
  - Configuration files (e.g. `.env`, YAML, JSON) and how they are loaded.
  - Priority order: environment variables vs. config files vs. CLI.

### 2.2. Output

- **Per‑item output**:
  - Output location (directory or other sink).
  - Naming scheme (e.g. `<input_name>.out.txt`, `<id>.json`).
  - Encoding (e.g. UTF‑8).
  - General content description (e.g. “normalized text”, “feature vector”, “classification result”).

- **Additional outputs**:
  - **Log file**:
    - Default path.
    - Format (line‑based, plain text).
  - **JSON manifest(s)**:
    - Per‑run manifest(s) summarizing item‑level results.
  - Optional:
    - Summary CSV/JSON.
    - Metrics report for monitoring.

---

## 3. Command‑line Interface

Use a consistent CLI pattern across tools.

### 3.1. Required arguments

- `--input-dir` or equivalent:
  - Directory or dataset location.
- `--output-dir`:
  - Destination for outputs, logs, manifests.
- **Core mode selector** (if applicable):
  - Model name, pipeline name, or processing profile.

### 3.2. Optional arguments (standard set)

- **Resumability / test mode**:
  - `--test-mode` / `--no-test-mode`:
    - Default: enabled.
    - Limits the number of items processed for quick checks.
  - `--test-limit N`:
    - Max number of items to **attempt** when in test mode.

- **Reprocessing semantics**:
  - `--reprocess`:
    - Default: `False`.
    - When `False`: skip items whose output already exists.
    - When `True`: recompute and overwrite outputs.

- **Logging / manifest paths**:
  - `--log-file PATH`
  - `--manifest-file PATH`
    - This is the **“latest”** manifest; per‑run manifests are timestamped and written next to it.

- **Execution parameters**:
  - `--workers N`:
    - Number of worker processes.
  - Timeouts, retry limits, batch sizes, etc.:
    - `--timeout SECONDS`
    - `--max-retries N`
    - `--batch-size N` (if applicable).

- **Domain‑specific controls**:
  - E.g. `--model`, `--temperature`, `--language`, `--strategy`, `--threshold`.

### 3.3. Argument validation

- Fail fast with clear messages if:
  - Required directories/files are missing or unreadable.
  - Integers / floats are out of allowed ranges (≤ 0 when > 0 is required).
  - Enums / “choice” arguments have invalid values.
- Prefer explicit, user‑friendly error messages over tracebacks.

---

## 4. Environment and Configuration

- Use a documented mechanism for loading environment/config:

  1. Load `.env` (or config file) from a **well‑defined location** relative to the script or project.
  2. Overlay with system environment variables.
  3. CLI flags override config/env where applicable.

- Sensitive values:
  - Do **not** accept secrets (e.g. API keys) via CLI arguments or output them in logs.
  - Document the exact env variables required and how to set them.

- On missing critical configuration:
  - Exit early with a helpful message.
  - Do not start long processing and fail mid‑way for missing keys.

---

## 5. Core Processing Architecture

Standardize the internal architecture for all batch tools.

### 5.1. High‑level flow

1. **Startup**:
   - Load configuration and environment.
   - Parse and validate CLI arguments.
   - Set up logging.
   - Ensure output directory exists.

2. **Discovery**:
   - Enumerate candidate items (files, records, etc.).
   - Apply filter based on supported extensions / schema.
   - Sort items for deterministic order.

3. **Planning**:
   - For each discovered item:
     - Determine output path(s).
     - Decide whether to **skip** or **process** (based on `--reprocess` and existing outputs).
   - Apply test‑mode limiting:
     - Truncate planned work list to `--test-limit` if test mode is on.

4. **Execution**:
   - If `workers == 1`:
     - Process sequentially in main process.
   - If `workers > 1`:
     - Use a `ProcessPoolExecutor` or equivalent.
     - Workers:
       - Perform CPU/network‑heavy work only.
       - Return structured results (status, error, timing, etc.).
     - Main process:
       - Orchestrates tasks.
       - Performs all file writes and logging where possible.

5. **End‑of‑run summary**:
   - Compute and log:
     - Total discovered.
     - Skipped (existing outputs).
     - Attempted.
     - Succeeded.
     - Failed.
   - Write manifests (per‑run + latest).
   - Exit with an appropriate status code.

6. **Interrupt handling**:
   - Catch `KeyboardInterrupt`:
     - Stop workers gracefully.
     - Write partial manifest and summary.
     - Exit non‑zero.

### 5.2. Separation of concerns

- **Core processing function** (worker):
  - Handles a single item:
    - Input loading.
    - Core transformation / inference.
    - Returns a result object (no logging or file I/O besides reading input).
- **Coordinator (main)**:
  - Planning items.
  - Dispatching work to workers.
  - Logging.
  - Writing outputs and manifests.

---

## 6. JSON Manifest Design

Use a consistent manifest structure across tools.

### 6.1. Files and naming

- **Per‑run manifest**:
  - One file per run.
  - Filename pattern:
    - `<base>_<run_id>.json` (e.g. `manifest_20260517T175435Z.json`).
  - `run_id`:
    - ISO‑like UTC time string safe for filenames (e.g. `YYYYMMDDTHHMMSSZ`).

- **Latest manifest**:
  - Always at `--manifest-file` (default: `manifest.json`).
  - Overwritten every run to reflect the most recent run.

### 6.2. Structure

Common structure, regardless of domain:

```json
{
  "run_metadata": {
    "run_id": "20260517T175435Z",
    "tool_name": "my_batch_tool",
    "version": "v1",
    "start_time": "2026-05-17T17:54:35Z",
    "end_time": "2026-05-17T17:57:35Z",
    "test_mode": true,
    "test_limit": 5,
    "reprocess": false,
    "workers": 4,
    "input_source": "/path/to/input",
    "output_dir": "/path/to/output",
    "config": {
      "...": "domain-specific settings (e.g. model, thresholds)"
    }
  },
  "files": [
    {
      "input_path": "/path/to/input/item.ext",
      "output_path": "/path/to/output/item.ext.out",
      "status": "success",
      "error": null,
      "retries": 0,
      "duration_seconds": 3.8,
      "timestamp": "2026-05-17T17:55:01Z",
      "metadata": {
        "...": "optional per-item metadata (e.g. model, label, score)"
      }
    }
  ]
}
```

- `status`:
  - At least: `success`, `failed`, `skipped_existing`.
- `error`:
  - `null` if no error.
  - Short string when failed.
- `metadata`:
  - Extensible space for domain‑specific info (e.g. “label”, “confidence”, “prompt_version”).

---

## 7. Logging Specification

Use a consistent logging pattern to make tools easy to monitor and debug.

- **Destination**:
  - File at `--log-file` (append mode).
  - Optional console output for INFO+.
- **Format**:
  - `[YYYY-MM-DD HH:MM:SS] LEVEL  message`
- **Minimum events**:
  - Startup configuration summary (model, dirs, workers, flags, important parameters).
  - Discovery summary (number of items found).
  - For each item:
    - `SKIPPED_EXISTING ...`
    - `SUCCESS ...`
    - `FAILED ...` (with error summary).
  - Retry attempts:
    - Logged at WARNING, including retry count and reason.
  - Manifest writing (paths for per‑run and latest).
  - End‑of‑run summary.
  - Interrupts, configuration errors, and early exits.

---

## 8. Error Handling & Resiliency

- **Configuration errors**:
  - Detected and reported before doing heavy work.
  - Example: missing env vars, invalid paths, invalid numeric arguments.
- **Per‑item errors**:
  - Should not abort the entire run.
  - Mark item as `failed`, log the error, continue to next item.
- **Transient vs permanent errors**:
  - Transient (e.g. network issues, rate limits):
    - Retries with backoff up to `max_retries`.
  - Permanent (e.g. invalid API key, unsupported parameter):
    - Immediate failure for that item; no further retries.
- **Exit codes**:
  - `0` if all attempted items succeeded.
  - Non‑zero if any item failed or a configuration error occurred.

---

## 9. Extensibility Guidelines

Design new tools so they can evolve without breaking existing users.

- **Versioning**:
  - Keep a `TOOL_VERSION` or `SPEC_VERSION` constant.
  - Record it in `run_metadata`.
- **Adding new options**:
  - Provide sensible defaults so existing commands continue to work.
- **Adding new outputs**:
  - Extend manifests via optional fields and nested `metadata` to avoid breaking schema consumers.
- **Alternate backends / engines**:
  - Isolate backend‑specific logic (API calls, models, engines) in dedicated functions or modules, called from the generic processing framework.

---

## 10. Documentation and Examples

For each new implementation:

- Provide a short **README section** describing:
  - What the tool does.
  - Typical usage pattern.
  - Example commands for:
    - A small test run.
    - A full production run with workers.
- Link to:
  - The specification document for that tool.
  - Any per‑run manifests or sample outputs.

---

By following these guidelines, you can build a family of batch tools that share a consistent architecture and user experience while differing only in their domain‑specific logic and configuration.