#!/usr/bin/env bash
#
# Lexaloud installer — Phase A bootstrap.
#
# Creates a dedicated venv at ~/.local/share/lexaloud/venv/, installs the
# pinned application dependency set, then the lexaloud package itself.
#
# After this script succeeds:
#
#   ~/.local/share/lexaloud/venv/bin/lexaloud setup
#
# will finish the configuration (render the systemd unit,
# print hotkey binding walkthrough).
#
# Usage:
#   ./scripts/install.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DEFAULT="$HOME/.local/share/lexaloud/venv"
VENV="${LEXALOUD_VENV:-$VENV_DEFAULT}"

# --- parse arguments ----------------------------------------------------

while (( "$#" )); do
  case "$1" in
    -h|--help)
      sed -n '4,24p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Usage: $0" >&2
      exit 2
      ;;
  esac
done

echo "=== Lexaloud installer ==="
echo "repo root: $REPO_ROOT"
echo "target venv: $VENV"
echo

# --- distro detection ---------------------------------------------------

DISTRO_ID="unknown"
DISTRO_LIKE=""
if [[ -f /etc/os-release ]]; then
  # shellcheck disable=SC1091
  DISTRO_ID="$(. /etc/os-release && echo "${ID:-unknown}")"
  DISTRO_LIKE="$(. /etc/os-release && echo "${ID_LIKE:-}")"
fi
echo "distro: $DISTRO_ID (like: ${DISTRO_LIKE:-none})"

# Classify into a package-manager family.
DISTRO_FAMILY="unknown"
case "$DISTRO_ID" in
  ubuntu|debian|linuxmint|pop|elementary|kali|zorin) DISTRO_FAMILY="debian" ;;
  fedora|rhel|centos|rocky|almalinux) DISTRO_FAMILY="fedora" ;;
  arch|manjaro|endeavouros|garuda|artix) DISTRO_FAMILY="arch" ;;
  opensuse*|sles) DISTRO_FAMILY="suse" ;;
esac
# Also check ID_LIKE for families that didn't hit the ID switch above.
if [[ "$DISTRO_FAMILY" == "unknown" && -n "$DISTRO_LIKE" ]]; then
  case "$DISTRO_LIKE" in
    *debian*|*ubuntu*) DISTRO_FAMILY="debian" ;;
    *fedora*|*rhel*)   DISTRO_FAMILY="fedora" ;;
    *arch*)            DISTRO_FAMILY="arch" ;;
    *suse*)            DISTRO_FAMILY="suse" ;;
  esac
fi
echo "distro family: $DISTRO_FAMILY"
echo

# --- Python version check (≥3.11) --------------------------------------

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is not installed." >&2
  exit 1
fi
PY_VERSION="$(python3 -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
PY_MAJOR="$(echo "$PY_VERSION" | cut -d. -f1)"
PY_MINOR="$(echo "$PY_VERSION" | cut -d. -f2)"
if (( PY_MAJOR < 3 || ( PY_MAJOR == 3 && PY_MINOR < 11 ) )); then
  cat >&2 <<EOF
ERROR: Python $PY_VERSION is too old. Lexaloud requires Python >= 3.11.
       Please install a newer Python via your distro's package manager.
EOF
  exit 1
fi
echo "python3: $PY_VERSION (ok)"
echo

# --- system dependency check (distro-aware) -----------------------------

missing=()

if ! python3 -c 'import venv' 2>/dev/null; then
  missing+=("python3-venv")
fi
if ! command -v wl-paste >/dev/null 2>&1; then
  missing+=("wl-clipboard")
fi
# Wayland uses wl-paste exclusively. Require xclip only for X11 sessions,
# where it provides the equivalent PRIMARY/CLIPBOARD access.
if [[ "${XDG_SESSION_TYPE:-}" != "wayland" ]] && ! command -v xclip >/dev/null 2>&1; then
    missing+=("xclip")
fi
# libportaudio2 — probe via ldconfig
LDCONFIG_OUT="$(ldconfig -p 2>/dev/null || true)"
if [[ "$LDCONFIG_OUT" != *libportaudio.so.2* ]]; then
  missing+=("libportaudio2")
fi
unset LDCONFIG_OUT
if ! command -v notify-send >/dev/null 2>&1; then
  missing+=("libnotify-bin")
fi

if (( ${#missing[@]} > 0 )); then
  mapfile -t missing < <(printf "%s\n" "${missing[@]}" | awk '!seen[$0]++')
  echo "Missing system packages (conceptual names):" >&2
  for p in "${missing[@]}"; do echo "  - $p" >&2; done
  echo >&2
  case "$DISTRO_FAMILY" in
    debian)
      echo "Install them with:" >&2
      echo "  sudo apt install ${missing[*]}" >&2
      ;;
    fedora)
      # Translate Debian package names to Fedora equivalents
      fedora_pkgs=()
      for p in "${missing[@]}"; do
        case "$p" in
          python3-venv)   fedora_pkgs+=("python3") ;;
          wl-clipboard)   fedora_pkgs+=("wl-clipboard") ;;
          xclip)          fedora_pkgs+=("xclip") ;;
          libportaudio2)  fedora_pkgs+=("portaudio") ;;
          libnotify-bin)  fedora_pkgs+=("libnotify") ;;
          *)              fedora_pkgs+=("$p") ;;
        esac
      done
      echo "Install them with:" >&2
      echo "  sudo dnf install ${fedora_pkgs[*]}" >&2
      ;;
    arch)
      arch_pkgs=()
      for p in "${missing[@]}"; do
        case "$p" in
          python3-venv)   arch_pkgs+=("python") ;;
          wl-clipboard)   arch_pkgs+=("wl-clipboard") ;;
          xclip)          arch_pkgs+=("xclip") ;;
          libportaudio2)  arch_pkgs+=("portaudio") ;;
          libnotify-bin)  arch_pkgs+=("libnotify") ;;
          *)              arch_pkgs+=("$p") ;;
        esac
      done
      echo "Install them with:" >&2
      echo "  sudo pacman -S ${arch_pkgs[*]}" >&2
      ;;
    suse)
      suse_pkgs=()
      for p in "${missing[@]}"; do
        case "$p" in
          python3-venv)   suse_pkgs+=("python3") ;;
          wl-clipboard)   suse_pkgs+=("wl-clipboard") ;;
          xclip)          suse_pkgs+=("xclip") ;;
          libportaudio2)  suse_pkgs+=("portaudio") ;;
          libnotify-bin)  suse_pkgs+=("libnotify-tools") ;;
          *)              suse_pkgs+=("$p") ;;
        esac
      done
      echo "Install them with:" >&2
      echo "  sudo zypper install ${suse_pkgs[*]}" >&2
      ;;
    *)
      echo "Your distro ($DISTRO_ID) isn't in our package-name table. The conceptual" >&2
      echo "names above are what you need. File a PR against scripts/install.sh to" >&2
      echo "add the package-name translation for your distro." >&2
      ;;
  esac
  exit 1
fi

LOCK="$REPO_ROOT/requirements-lock.cpu.txt"
if [[ ! -f "$LOCK" ]]; then
  echo "ERROR: lockfile not found: $LOCK" >&2
  exit 1
fi

# --- PYTHONPATH pollution warning ---------------------------------------

if [[ -n "${PYTHONPATH:-}" ]]; then
  cat >&2 <<WARN
Warning: \$PYTHONPATH is set in your shell:
  PYTHONPATH=$PYTHONPATH

This typically comes from sourcing ROS 2, a game engine, or similar. We
will scrub PYTHONPATH while installing so it does not pollute the venv
lockfile, and the rendered systemd unit will also scrub it so the daemon
runs in a clean environment.
WARN
fi

# --- venv creation ------------------------------------------------------

if [[ -d "$VENV" ]]; then
  echo "venv already exists at $VENV"
else
  echo "creating venv at $VENV"
  mkdir -p "$(dirname "$VENV")"
  python3 -m venv "$VENV"
fi

PIP="env -u PYTHONPATH $VENV/bin/pip"

# --- install the pinned runtime set -------------------------------------

echo "installing pinned runtime dependencies from $(basename "$LOCK")"
# The historical lockfiles include the in-process Kokoro stack.  Keep using
# their pinned, hashed application dependencies, but remove the now-unused
# model runtime (and its CUDA packages) before installing.
LOCK_NO_BUILTIN_TTS=""
trap '[[ -n "${LOCK_NO_BUILTIN_TTS:-}" ]] && rm -f "$LOCK_NO_BUILTIN_TTS"' EXIT
LOCK_NO_BUILTIN_TTS="$(mktemp)"
awk '/^(babel|csvw|dlinfo|espeakng-loader|flatbuffers|isodate|joblib|jsonschema|jsonschema-specifications|kokoro-onnx|language-tags|mpmath|nvidia-.*-cu12|onnxruntime(-gpu)?|packaging|phonemizer-fork|protobuf|pyparsing|pydantic_core|python-dateutil|rdflib|referencing|requests|rfc3986|rpds-py|segments|six|sympy|termcolor|uritemplate|urllib3)==/{skip=1; next} /^[^ \t]/{skip=0} !skip' "$LOCK" > "$LOCK_NO_BUILTIN_TTS"
# pydantic 2.12.5 requires this exact core release. The inherited lockfile
# incorrectly pinned 2.45.0; retain a platform-specific verified hash here.
cat >> "$LOCK_NO_BUILTIN_TTS" <<'EOF'
pydantic_core==2.41.5 \
    --hash=sha256:22f0fb8c1c583a3b6f24df2470833b40207e907b90c928cc8d3594b76f874375
EOF

$PIP install --require-hashes -r "$LOCK_NO_BUILTIN_TTS"

# --- install the lexaloud package --------------------------------------

echo "installing the lexaloud package (editable)"
$PIP install --no-deps -e "$REPO_ROOT"

echo
echo "=== install complete ==="
echo
echo "Next:"
echo "  $VENV/bin/lexaloud setup"
echo
echo "Add the venv to your PATH (optional):"
echo "  ln -s $VENV/bin/lexaloud ~/.local/bin/lexaloud"
