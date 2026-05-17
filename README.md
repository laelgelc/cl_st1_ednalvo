# Corpus Linguistics - Study 1 - Ednalvo

## Phase 1: Raw Data Processing and Cleaning Proof-of-Concept

Phase 1 focuses on building a robust proof‑of‑concept pipeline to convert handwritten exam images into clean text files that can be used in later corpus‑linguistics analyses.

The main tool for this phase is `transcribe_image_handwriting.py`, which:

- Reads image files from an input directory, supporting multiple formats (`.jpg`, `.jpeg`, `.png` by default).
- Sends each image to an OpenAI vision model (e.g. `gpt-4.1-mini`, `gpt-4.1`, `o3-mini`, `gpt-5.5`) using a fixed, audited prompt tuned for Brazilian Portuguese handwritten text.
- Writes one UTF‑8 `.txt` file per image in an output directory, preserving paragraph structure.
- Skips already processed images by default, allowing safe re‑runs of the script.
- Supports a **test mode** (enabled by default) that limits processing to a small number of images (default: 5) for quick experiments.
- Can run with multiple worker processes to speed up batch transcription while keeping logs and outputs consistent.
- Logs progress and errors to a log file in the output directory (append‑only across runs), plus a concise summary in the console.
- Produces **JSON manifests** for each run:
  - A timestamped **per‑run manifest** that records run metadata and per‑file status (success, skipped, failed), including timing and error information.
  - A **“latest” manifest** (default: `manifest.json`) that always reflects the most recent run.
- Optionally accepts a `--temperature` argument to override the model’s default temperature; if omitted, the script relies on the model’s own default, and it does not attempt to detect whether a particular model supports temperature override.

Later phases will build on these cleaned text files for annotation, exploration, and quantitative analysis of the learners’ productions.

### Run History (from `transcribe_image_handwriting.log`)

Based on the accumulated log, the following runs of `transcribe_image_handwriting.py` have been executed on the proof‑of‑concept dataset:

#### Run 1

- **Start time:** 2026‑05‑17 10:22:54
- **End time:** 2026‑05‑17 10:36:54
- **Duration:** 14 minutes 0 seconds
- **Model:** `gpt-5.5`
- **Images discovered:** 50
- **Attempted:** 50
- **Succeeded:** 48
- **Failed:** 2

#### Run 2

- **Start time:** 2026‑05‑17 16:00:04
- **End time:** 2026‑05‑17 16:04:18
- **Duration:** 4 minutes 14 seconds
- **Model:** `gpt-5.5`
- **Images discovered:** 50
- **Attempted:** 2
- **Succeeded:** 1
- **Failed:** 1

#### Run 3

- **Start time:** 2026‑05‑17 17:54:35
- **End time:** 2026‑05‑17 17:57:35
- **Duration:** 3 minutes 0 seconds
- **Model:** `gpt-5.5`
- **Images discovered:** 50
- **Attempted:** 1
- **Succeeded:** 1
- **Failed:** 0

#### Aggregate Summary

- **Total number of runs:** 3
- **Total successful image transcriptions:** 48 + 1 + 1 = **50**
- **Total wall‑clock processing time across runs:**
  - Run 1: 14:00
  - Run 2: 4:14
  - Run 3: 3:00
  - **Total:** 21 minutes 14 seconds (1,274 seconds)