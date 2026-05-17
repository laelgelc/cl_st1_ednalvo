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
- Logs progress and errors to a log file in the output directory, plus a concise summary in the console.
- Produces a JSON manifest describing the status of each image (success, skipped, failed), including timing and error information.
- Optionally accepts a `--temperature` argument to override the model’s default temperature; if omitted, the script relies on the model’s own default, and it does not attempt to detect whether a particular model supports temperature override.

Later phases will build on these cleaned text files for annotation, exploration, and quantitative analysis of the learners’ productions.