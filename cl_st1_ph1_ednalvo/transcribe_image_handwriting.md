## Specification: `transcribe_image_handwriting.py`

### 1. Purpose

`transcribe_image_handwriting.py` processes image files containing handwritten Brazilian Portuguese text, sends them to an OpenAI GPT vision model, and saves the transcriptions as `.txt` files.

The program is designed for:

- **Batch processing** of many images.
- **Support for multiple common image formats**.
- **Resumability** (skips already processed images by default).
- **Parallel processing** with a configurable number of worker processes.
- **Traceable logging** of progress and errors.
- **A JSON manifest** summarizing per‑file results.
- **Safe defaults** via a test mode that limits the number of processed images.
- Optional **temperature override**, while by default relying on the model’s own temperature setting.

---

### 2. Input / Output

#### 2.1. Input

- **Image files**:
  - All files in the input directory whose lowercase extension is in a supported list:
    - Default supported extensions: `.jpg`, `.jpeg`, `.png`.
  - Initial version: **non‑recursive** search (subdirectories may be added later).
- **Model name**:
  - Any OpenAI vision‑capable model (e.g. `gpt-4.1-mini`, `gpt-4.1`, `o3-mini`, `gpt-5.5`).
  - Provided via CLI argument.
- **Configuration**:
  - Environment variable `OPENAI_API_KEY`, loaded from `env/.env` (relative path).

#### 2.2. Output

For each processed image:

- A `.txt` file in the specified output directory:
  - Base name includes the full filename including extension:
    - Example: `image_001.jpg` → `image_001.jpg.txt`
      (this avoids clashes if multiple formats exist for the same logical page).
  - Encoding: UTF‑8.
  - Content: only the transcribed handwritten text in Brazilian Portuguese, structured as paragraphs separated by a single blank line, according to the prompt.

Additional outputs:

- A **log file** (default: `transcribe_image_handwriting.log`) in the output directory, unless overridden.
- A **JSON manifest** file in the output directory (see §8).
- A **summary** printed to stdout at the end of the run:
  - Total images discovered.
  - Number attempted.
  - Succeeded.
  - Skipped.
  - Failed.

---

### 3. Command-line Interface

Use `argparse` (or similar) to implement the following CLI.

#### 3.1. Required arguments

- `--model` (string, required):  
  OpenAI model name to use for transcription (e.g. `gpt-4.1-mini`, `gpt-4.1`, `o3-mini`, `gpt-5.5`).

- `--input-dir` (string, required):  
  Directory containing image files to process.

- `--output-dir` (string, required):  
  Directory where `.txt` output files, the log file, and manifest will be written.

#### 3.2. Optional arguments

- `--test-mode` / `--no-test-mode` (boolean flag):
  - Default: **test mode is enabled**.
  - When enabled, process only up to a limited number of images (`--test-limit`).
  - Implement via `--test-mode` (default `True`) and `--no-test-mode` (sets `False`).

- `--test-limit N` (integer):
  - Default: `5`.
  - Only meaningful when test mode is enabled.
  - Defines the maximum number of images to **attempt** (regardless of success/failure, but excluding skips due to already‑existing output files).

- `--reprocess` (boolean flag):
  - Default: `False`.
  - When `False` (default): if a target `.txt` file already exists for an image, that image is **skipped** and not sent to the API.
  - When `True`: force reprocessing and **overwrite** existing `.txt` files.

- `--log-file PATH` (string, optional):
  - Default: `<output-dir>/transcribe_image_handwriting.log`.
  - Custom path for the log file.

- `--manifest-file PATH` (string, optional):
  - Default: `<output-dir>/manifest.json`.
  - Custom path for the JSON manifest.

- `--max-retries N` (integer, optional):
  - Default: `3`.
  - Maximum number of retries per image when API/transient errors occur.

- `--timeout SECONDS` (integer or float, optional):
  - Default: `60`.
  - Request timeout per API call.

- `--workers N` (integer, optional):
  - Default: `1` (single‑process, sequential).
  - Number of worker processes for parallel image processing.
  - When `N > 1`, processing is parallelized across workers while keeping global limits and logging coherent.

- `--extensions EXT1,EXT2,...` (string, optional):
  - Default: `.jpg,.jpeg,.png`.
  - Comma‑separated list of file extensions (with or without leading dots) to consider as images.
  - All comparisons are done case‑insensitively.

- `--temperature FLOAT` (optional):
  - Default: `None` (no override).
  - When provided, the value is sent as `"temperature"` in the API request.
  - When omitted, the script **does not** send a temperature parameter and the model’s default is used.
  - The program **does not detect** whether a given model supports temperature override; if a model rejects the provided value (e.g. with an `unsupported_value` error), the request fails and the image is marked as `failed`.

Argument validation:

- Fail fast with clear errors if:
  - Input directory does not exist or is not readable.
  - No files with supported extensions are found in `--input-dir`.
  - `--test-limit`, `--max-retries`, `--timeout`, or `--workers` are invalid (≤0).
  - `--extensions` contains no valid items.
  - `--temperature` is provided but is negative (must be ≥ 0; additional model‑specific constraints are not validated by the script).

---

### 4. Environment and Configuration

- On startup:
  1. Load `.env` from `env/.env` (path is relative to the script or project root; explain in comments).
  2. After loading, read `OPENAI_API_KEY` from the environment.
- If `OPENAI_API_KEY` is absent or empty:
  - Exit with a clear, user‑friendly error message.
- API key is **not** accepted via CLI arguments or config files (to reduce accidental exposure).

---

### 5. Prompt

Use a fixed prompt string, stored as a named constant in the script (for auditability):

> This image contains handwritten text in Brazilian Portuguese. Transcribe only the handwritten text, ignoring any printed or pre‑printed text, into plain text. Preserve the original sentence and paragraph structure, grouping sentences into paragraphs as in the original and separating paragraphs with a single blank line. Do not add any explanations or extra text.

- When `--temperature` is omitted, the model’s own default temperature is used.
- When `--temperature` is provided, that value is sent as part of the request, but the script does **not** verify whether the model supports overriding temperature; errors from the API are treated as normal failures.
- The prompt should be logged once at the start of each run (INFO level) to aid auditability.

---

### 6. Supported Formats and MIME Types

- Supported extensions are configurable via:
  - `SUPPORTED_IMAGE_EXTENSIONS` constant (default: `[".jpg", ".jpeg", ".png"]`).
  - Value overridden at runtime by `--extensions` if provided.
- Every extension must have a corresponding MIME type in a mapping:

  - `.jpg`, `.jpeg` → `image/jpeg`
  - `.png` → `image/png`

- Extension matching is:
  - Case‑insensitive.
  - Based on the filename suffix (e.g. `Path.suffix.lower()` in Python).
- Discovery step:
  - Scan `--input-dir` for files whose extension is in the supported list.
- The internal logic is otherwise extension‑agnostic: the same pipeline is used for all supported formats, with only the MIME type differing.

---

### 7. Core Processing Logic

Overall flow:

1. **Startup**:
   - Load `.env` and validate `OPENAI_API_KEY`.
   - Parse CLI arguments.
   - Normalize and validate supported extensions.
   - Prepare logging.
   - Create `--output-dir` if it does not exist.
   - Log configuration summary (model, directories, test mode & limit, reprocess, workers, extensions, prompt version, and whether temperature override is set).

2. **Image discovery**:
   - Enumerate all files in `--input-dir` whose lowercase extension is in the supported list.
   - Sort files (e.g. lexicographically) to ensure deterministic ordering.
   - If none are found, exit with a clear message.

3. **Planning the work list**:
   - For each discovered image file:
     - Compute the target output path:
       - Example: `image_001.jpg` → `<output-dir>/image_001.jpg.txt`.
     - If `--reprocess` is `False` and the target `.txt` file exists:
       - Mark the item as **skipped_existing** without sending to workers.
     - Otherwise, include it in the **work list** to be processed.
   - If test mode is enabled:
     - Truncate the work list to at most `--test-limit` items.
     - Log that processing is limited because of test mode.

4. **Parallel processing (workers)**:

   - If `--workers == 1`:
     - Process items sequentially in the main process.
   - If `--workers > 1`:
     - Use `multiprocessing.Pool` or `concurrent.futures.ProcessPoolExecutor` (preferred) to process items in parallel.
     - Each worker:
       - Invokes the **API interaction function** (§9) for a single image.
       - Returns a structured result object containing:
         - Input path, output path.
         - Status: `success`, `failed`.
         - Optional error summary.
         - Timing information.
     - Main process:
       - Collects results.
       - Writes `.txt` files and updates manifest and counters based on results.
       - Handles logging in a centralized way where possible (e.g. workers return messages or statuses; main process logs them) to avoid garbled log output.

   Notes:

   - Skipped images due to existing `.txt` do **not** go to workers.
   - Parallelization must not violate resumability semantics; re‑run behavior remains the same.

5. **End-of-run summary**:
   - Maintain counters:
     - `total_discovered` (all images with supported extensions).
     - `skipped_existing` (skipped because `.txt` already existed and `--reprocess` is False).
     - `attempted` (sent to API, regardless of success/failure).
     - `succeeded`.
     - `failed`.
   - Print and log the summary.
   - Write or update the JSON manifest (§8).
   - Exit with:
     - Code `0` if `failed == 0`.
     - Non‑zero (e.g. `1`) otherwise or if any configuration error occurred.

6. **Interrupt handling**:
   - Catch `KeyboardInterrupt`:
     - Gracefully shutdown workers if any.
     - Log that the run was interrupted.
     - Write a partial manifest and summary based on the results so far.
     - Exit with non‑zero status.

---

### 8. JSON Manifest

The program maintains a JSON manifest summarizing each discovered image and its final status.

- Default path: `<output-dir>/manifest.json`, overridable via `--manifest-file`.
- Structure (example):

  ```json
  {
    "run_metadata": {
      "model": "gpt-4.1-mini",
      "prompt_version": "v1",
      "start_time": "2026-05-16T10:23:45Z",
      "end_time": "2026-05-16T10:25:10Z",
      "test_mode": true,
      "test_limit": 5,
      "reprocess": false,
      "workers": 4,
      "supported_extensions": [".jpg", ".jpeg", ".png"],
      "temperature": null
    },
    "files": [
      {
        "input_path": "path/to/input/image_001.jpg",
        "output_path": "path/to/output/image_001.jpg.txt",
        "status": "success",
        "error": null,
        "retries": 0,
        "duration_seconds": 3.8,
        "model": "gpt-4.1-mini",
        "timestamp": "2026-05-16T10:23:50Z"
      }
    ]
  }
  ```

- Manifest behavior:
  - Written at the end of the run.
  - If the file already exists, it may be overwritten for simplicity (the manifest describes a single run).
  - The schema above can be simplified but should at least contain:
    - Per‑file `input_path`, `output_path`, `status`, `error`/`null`.

---

### 9. API Interaction Function

The interaction with the OpenAI API must be implemented in a **separate function** (and optionally a small helper module) to keep the rest of the code clean and testable.

Function signature (conceptual):

```text
transcribe_image(
    image_path: Path,
    model: str,
    mime_type: str,
    prompt: str,
    api_key: str,
    timeout: float,
    max_retries: int,
    temperature: Optional[float],
) -> TranscriptionResult
```

Where `TranscriptionResult` is a structured object or dictionary containing:

- `status`: `"success"` or `"failed"`.
- `text`: transcription text on success.
- `error`: error message or `None`.
- `retries`: number of retries actually used.
- `duration_seconds`: elapsed time (inside the function).

Behavior:

1. Open and read the image bytes.
2. Build a base64 data URL with the appropriate MIME type.
3. Construct and send a Chat Completions request:
   - `model`: argument value.
   - One user message containing:
     - The fixed prompt text.
     - The image.
   - If `temperature` is **not** `None`, include `"temperature": <value>` in the payload.
   - If `temperature` is `None`, omit the parameter and rely on the model’s default.
4. Retry logic:
   - On **transient errors** (network, timeout, rate limit), retry up to `max_retries` using simple exponential backoff.
   - On **obvious permanent errors** (invalid API key, invalid model, 4xx request validation errors including unsupported temperature values):
     - Return immediately with `status="failed"` and an appropriate `error` message.
5. On success:
   - Extract the text response.
   - Return `TranscriptionResult` with `status="success"` and the text.
6. The function itself **must not** write files or log directly (except possibly very low‑level debug logs); it should return results for the caller to handle I/O and logging.
7. The program does **not** attempt to automatically detect whether a model supports temperature override; unsupported values result in failed requests logged as errors.

---

### 10. Logging Specification

- Use Python’s `logging` module.
- Log destination:
  - File: `--log-file` path.
  - Optional console handler for INFO+ messages.
- Recommended log format:

  ```text
  [YYYY-MM-DD HH:MM:SS] LEVEL  message
  ```

Minimum log events:

- Startup configuration and prompt version, including the effective temperature setting (either explicit value or “model default”).
- Discovery summary (`N` images found).
- Per image:
  - `SKIPPED_EXISTING`, `SUCCESS`, or `FAILED` with details.
- Retry attempts (as WARNING).
- Manifest writing (path).
- End‑of‑run summary.
- Interrupts and early exits.

Parallel mode logging:

- Prefer that workers return structured results to the main process, and the main process logs them, to avoid interleaved log lines from multiple processes.

---

### 11. Error Handling & Robustness

- Validate paths and input arguments before doing any network calls.
- Treat obviously malformed “images” (wrong content but correct extension) as failures:
  - Catch the error, log as `FAILED`, continue.
- Maintain resumability and idempotency:
  - Skipping on existing `.txt` files when `--reprocess` is `False` is central.
- Use meaningful exit codes:
  - `0` for a completely successful run.
  - Non‑zero when any file fails or a configuration error occurs.

---

### 12. Extensibility Notes

The design supports future changes:

- New image formats: add to supported extensions and MIME mapping.
- Different prompt versions: keep a `PROMPT_VERSION` constant and store it in the manifest.
- Alternative backends or models: change only the API interaction function.
- More advanced parallelism (e.g. async requests) can be introduced without changing the CLI.