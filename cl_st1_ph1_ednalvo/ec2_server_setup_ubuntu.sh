#!/bin/bash

# EC2 Ubuntu 24.04 setup script with Miniconda/conda environment recreation.
#
# Features:
# - Runs from any directory (uses script location for relative paths)
# - Looks for environment YAMLs ONLY inside: ./env (relative to this script)
# - Default env file: condaenv.yaml
# - Optional: --env <FILENAME> (filename only; no paths)
# - Optional: --ssh-key (generate per-instance SSH key for git pushes)
# - If python version is specified in the env YAML (e.g., - python=3.13.9), it takes priority
# - No pip requirements file support
# - Accepts Anaconda channel Terms of Service (ToS) non-interactively if needed
#
# Usage examples:
#   bash setup/ec2_server_setup_ubuntu.sh
#   bash setup/ec2_server_setup_ubuntu.sh --env condaenv.yaml
#   bash setup/ec2_server_setup_ubuntu.sh --ssh-key
#   bash setup/ec2_server_setup_ubuntu.sh --env my_other_env.yaml --ssh-key

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_DIR="${SCRIPT_DIR}/env"

usage() {
  cat << 'EOF'
Usage:
  ./ec2_server_setup_ubuntu.sh [--env NAME] [--ssh-key]

Options:
  --env NAME    Environment YAML filename located in ./env (relative to this script).
               Examples: condaenv.yaml, my_other_env.yaml
               Default: condaenv.yaml
  --ssh-key     Generate an ephemeral per-instance SSH keypair at ~/.ssh/id_ed25519 (only if missing)
               and print the public key for registering as a GitHub deploy key (write access).
  -h, --help    Show this help message.
EOF
}

ENV_BASENAME="condaenv.yaml"
GENERATE_SSH_KEY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --env requires a filename argument (must exist in env/)"
        exit 1
      fi
      ENV_BASENAME="$2"
      shift 2
      ;;
    --ssh-key)
      GENERATE_SSH_KEY=1
      shift 1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

# Enforce: only files inside env/ are allowed (no absolute paths, no ../, no subdirs)
if [[ "$ENV_BASENAME" = /* ]] || [[ "$ENV_BASENAME" == *".."* ]] || [[ "$ENV_BASENAME" == */* ]]; then
  echo "ERROR: --env must be a filename only (no paths)."
  echo "It must refer to a file inside: ${ENV_DIR}"
  exit 1
fi

ENV_FILE="${ENV_DIR}/${ENV_BASENAME}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: Conda environment file not found in env/: ${ENV_FILE}"
  echo "Available files in ${ENV_DIR}:"
  ls -1 "${ENV_DIR}" 2>/dev/null || true
  exit 1
fi

echo "--- Using conda environment file: $ENV_FILE ---"

# Parse env name from YAML (fallback to my_env if missing)
ENV_NAME="$(awk -F': *' '/^name:[[:space:]]*/ {print $2; exit}' "$ENV_FILE" | tr -d '\r')"
ENV_NAME="${ENV_NAME:-my_env}"

# Prefer python version specified in YAML as: - python=3.13.9 (any indentation)
PY_VER_DEFAULT="3.13.9"
PY_VER_FROM_FILE="$(awk '
  /^[[:space:]]*dependencies:[[:space:]]*$/ {in_deps=1; next}
  in_deps && /^[[:space:]]*-[[:space:]]*python[[:space:]]*=/ {
    gsub(/^[[:space:]]*-[[:space:]]*python[[:space:]]*=/, "", $0)
    gsub(/[[:space:]]+$/, "", $0)
    print $0
    exit
  }
' "$ENV_FILE" | tr -d '\r')"

if [[ -n "$PY_VER_FROM_FILE" ]]; then
  PY_SPEC="python=${PY_VER_FROM_FILE}"
  echo "--- Python pinned in env file: ${PY_SPEC} (takes priority) ---"
else
  PY_SPEC="python=${PY_VER_DEFAULT}"
  echo "--- No Python pin found in env file; using default: ${PY_SPEC} ---"
fi

echo "--- Starting System Update and Basic Packages Installation ---"

sudo apt update
sudo apt upgrade -y

sudo apt install -y \
  git curl wget ca-certificates \
  openssh-client \
  xsel ripgrep html2text zip unzip bzip2 \
  pandoc \
  pipx build-essential \
  ffmpeg \
  tesseract-ocr tesseract-ocr-por tesseract-ocr-spa ocrmypdf \
  software-properties-common \
  xvfb

# Optional: AWS CLI via snap
if ! command -v aws >/dev/null 2>&1; then
  sudo snap install aws-cli --classic
fi

echo "--- Detecting Architecture ---"
ARCH="$(uname -m)"
case "$ARCH" in
  x86_64)
    TT_TARBALL="tree-tagger-linux-3.2.5.tar.gz"
    MINICONDA_SUFFIX="Linux-x86_64"
    ;;
  aarch64|arm64)
    TT_TARBALL="tree-tagger-ARM64-3.2.tar.gz"
    MINICONDA_SUFFIX="Linux-aarch64"
    ;;
  *)
    echo "Unsupported architecture: $ARCH"
    exit 1
    ;;
esac
echo "ARCH=$ARCH"

echo "--- Starting Conda (Miniconda) Setup ---"

CONDA_DIR="$HOME/miniconda3"
MINICONDA_INSTALLER="/tmp/miniconda.sh"
MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-${MINICONDA_SUFFIX}.sh"

if [[ ! -d "$CONDA_DIR" ]]; then
  echo "Downloading Miniconda from: $MINICONDA_URL"
  curl -fsSL "$MINICONDA_URL" -o "$MINICONDA_INSTALLER"
  bash "$MINICONDA_INSTALLER" -b -p "$CONDA_DIR"
else
  echo "Miniconda already installed at $CONDA_DIR"
fi

# Load conda for this script (non-interactive)
source "$CONDA_DIR/etc/profile.d/conda.sh"

# Initialize conda for future interactive shells (safe to re-run)
if ! grep -q "### conda initialize" "$HOME/.bashrc" 2>/dev/null; then
  "$CONDA_DIR/bin/conda" init bash
fi

conda config --set always_yes yes --set changeps1 no

echo "--- Accepting Conda Terms of Service if required ---"
# Newer conda versions require ToS acceptance for Anaconda-provided channels in non-interactive use.
# This makes the script fully unattended. If ToS is already accepted, these are no-ops.
# We deliberately keep failures non-fatal here to avoid breaking setups that don't have 'conda tos'.
if conda tos --help >/dev/null 2>&1; then
  yes | conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main >/dev/null 2>&1 || true
  yes | conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r >/dev/null 2>&1 || true
fi

echo "--- Updating base conda ---"
conda update -n base -c defaults conda

echo "--- Creating/Updating Conda Environment: ${ENV_NAME} ---"

# If env exists: update it. If Python isn't pinned in YAML, enforce script default.
if conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
  echo "Environment '${ENV_NAME}' exists; updating from YAML..."
  conda env update -n "$ENV_NAME" -f "$ENV_FILE" --prune

  if [[ -z "$PY_VER_FROM_FILE" ]]; then
    echo "Ensuring default Python version in existing env: ${PY_SPEC}"
    conda install -n "$ENV_NAME" "$PY_SPEC"
  fi
else
  echo "Environment '${ENV_NAME}' does not exist; creating..."
  if [[ -n "$PY_VER_FROM_FILE" ]]; then
    # YAML already pins Python; create directly from YAML
    conda env create -f "$ENV_FILE"
  else
    # YAML doesn't pin Python; create env with desired Python first, then apply YAML
    conda create -n "$ENV_NAME" "$PY_SPEC"
    conda env update -n "$ENV_NAME" -f "$ENV_FILE" --prune
  fi
fi

# Register Jupyter kernel (so JupyterLab sees the conda env)
conda run -n "$ENV_NAME" python -m pip install --upgrade ipykernel
conda run -n "$ENV_NAME" python -m ipykernel install --user --name="$ENV_NAME" --display-name="$ENV_NAME"

echo "--- Starting TreeTagger Setup ---"

mkdir -p "$HOME/treetagger/"
BASE_URL="https://cis.uni-muenchen.de/~schmid/tools/TreeTagger/data"

cd "$HOME/treetagger/"
curl -fO "${BASE_URL}/${TT_TARBALL}"
curl -fO "${BASE_URL}/tagger-scripts.tar.gz"
curl -fO "${BASE_URL}/install-tagger.sh"
curl -fO "${BASE_URL}/english.par.gz"
curl -fO "${BASE_URL}/portuguese2.par.gz"

chmod +x "$HOME/treetagger/install-tagger.sh"
"$HOME/treetagger/install-tagger.sh"

# Add TreeTagger PATH entries only once (idempotent)
if ! grep -q "$HOME/treetagger/cmd" "$HOME/.bashrc" 2>/dev/null; then
  {
    echo ""
    echo "# The following lines add TreeTagger to the PATH variable"
    echo "export PATH=\$PATH:$HOME/treetagger/cmd"
    echo "export PATH=\$PATH:$HOME/treetagger/bin"
  } >> "$HOME/.bashrc"
fi

echo "--- Starting Git Global Parameters Setup ---"

if ! command -v git >/dev/null 2>&1; then
  echo "Error: Git is not installed!"
  exit 1
fi

git config --global user.name "${USER}@$(hostname -s)"
git config --global user.email "${USER}@$(hostname -s).local"

# Write (don’t append) to keep this idempotent
cat << 'EOF' > "$HOME/.gitignore_global"
# General
nohup.out

# macOS system files
.DS_Store
.AppleDouble
.LSOverride

# Icon files
Icon?

# Thumbnails
._*

# macOS folder attributes
.Spotlight-V100
.Trashes

# AFP share metadata
.AppleDB
.AppleDesktop
Network Trash Folder
Temporary Items
.apdisk

# RStudio project files
.Rproj.user/
*.Rproj

# R session data
.Rhistory
.RData
.Ruserdata

# R package build artifacts
.Rbuildignore
.Rcheck/

# R Markdown caches
*_cache/
cache/

# renv
renv/library/
renv/staging/

EOF

git config --global core.excludesfile "$HOME/.gitignore_global"

echo "--- Starting Firefox Non-Snap Setup ---"

sudo snap remove firefox || true
sudo add-apt-repository -y ppa:mozillateam/ppa

sudo tee /etc/apt/preferences.d/mozilla-firefox > /dev/null << 'EOF'
Package: firefox
Pin: release o=LP-PPA-mozillateam
Pin-Priority: 1001

Package: firefox*
Pin: release o=Ubuntu*
Pin-Priority: -1
EOF

distro_codename="$(lsb_release -sc)"
echo "Unattended-Upgrade::Allowed-Origins:: \"LP-PPA-mozillateam:${distro_codename}\";" \
  | sudo tee /etc/apt/apt.conf.d/51unattended-upgrades-firefox > /dev/null

sudo apt update
sudo apt install -y firefox libasound2t64 libdbus-glib-1-2 libgtk-3-0t64 libx11-xcb1

echo "--- Firefox Setup Complete ---"
apt policy firefox || true

echo "--- GitHub SSH Setup (Optional) ---"

if [[ "$GENERATE_SSH_KEY" = "1" ]]; then
  SSH_DIR="$HOME/.ssh"
  KEY_PATH="$SSH_DIR/id_ed25519"
  PUB_PATH="${KEY_PATH}.pub"

  mkdir -p "$SSH_DIR"
  chmod 700 "$SSH_DIR"

  if [[ ! -f "$KEY_PATH" ]]; then
    SSH_KEY_COMMENT="${USER}@$(hostname -s)"
    ssh-keygen -t ed25519 -C "$SSH_KEY_COMMENT" -f "$KEY_PATH" -N ""
    chmod 600 "$KEY_PATH"
    chmod 644 "$PUB_PATH"
  else
    echo "SSH key already exists at $KEY_PATH; not generating a new one."
  fi

  # Avoid interactive host authenticity prompts for GitHub on first SSH use
  touch "$SSH_DIR/known_hosts"
  chmod 600 "$SSH_DIR/known_hosts"
  ssh-keyscan -H github.com 2>/dev/null >> "$SSH_DIR/known_hosts" || true

  echo ""
  echo "SSH public key (add as a GitHub Deploy Key with write access):"
  cat "$PUB_PATH"
else
  echo "Skipped SSH key generation. Re-run with: --ssh-key"
fi

echo "--- Setup Finished ---"
echo "Next steps:"
echo "  source ~/.bashrc"
echo "  conda activate ${ENV_NAME}"
echo ""
echo "Optional (recommended after large upgrades):"
echo "  sudo reboot"
read -p "Press [Enter] to reboot the system..."

# Rebooting the system for kernel's update
sudo reboot