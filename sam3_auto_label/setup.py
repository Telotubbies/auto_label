"""Auto-detect hardware and install the right dependencies.

Detects:
  - Platform: Windows / Linux / macOS
  - GPU: NVIDIA CUDA / AMD ROCm / Apple MPS / CPU-only
  - RAM / VRAM

Then:
  1. Locates a compatible Python interpreter (3.10-3.12 preferred; 3.13+
     supported with upgraded numpy 2.x / torch 2.6+ deps)
  2. Creates a venv from that interpreter (if missing)
  3. Installs correct PyTorch variant
  4. Installs remaining requirements
  5. Downloads SAM 3.1 checkpoint (if missing)
  6. Prints summary

Usage:
    python setup.py              # full setup
    python setup.py --check      # just detect and print, no install
    python setup.py --force-cpu  # force CPU-only even if GPU exists
    python setup.py --no-prompt  # non-interactive: skip download confirmations
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import urllib.request

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(BASE_DIR, "sam3_venv")
MODEL_DIR = os.path.join(BASE_DIR, "checkpoints")
CKPT_PATH = os.path.join(MODEL_DIR, "sam3.1_multiplex.pt")
CKPT_URL = "https://huggingface.co/facebook/sam3.1/resolve/main/sam3.1_multiplex.pt"
# Expected SHA256 of the checkpoint (for integrity verification).
# Update this hash after the first verified download if needed.
CKPT_SHA256 = None  # Set to a 64-char hex string to enable integrity verification

# ---------------------------------------------------------------------------
# Python version policy
# ---------------------------------------------------------------------------
# Preferred range: 3.10-3.12 (matches pinned deps: numpy==1.26.4, torch==2.5.1).
# 3.13+ is supported with upgraded deps (numpy>=2.1, torch==2.6.0) but is less
# tested because SAM3's vendored pyproject.toml declares numpy<2.
# Sources:
#   numpy 1.26.4 supports 3.9-3.12 only: https://numpy.org/doc/2.3/release/1.26.4-notes.html
#   PyTorch 2.6+ supports 3.13: https://github.com/pytorch/pytorch/blob/2c13a07/RELEASE.md
PY_PREFERRED = (3, 10), (3, 12)   # inclusive range preferred for pinned deps
PY_MAX = (3, 13)                  # highest minor version we will attempt
# Interpreter chosen for venv creation; set by find_compatible_python().
SELECTED_PYTHON = None

# ---------------------------------------------------------------------------
# Hardware detection
# ---------------------------------------------------------------------------

class HardwareInfo:
    def __init__(self):
        self.os = platform.system()  # Windows / Linux / Darwin
        self.os_version = platform.version()
        self.machine = platform.machine()  # AMD64 / arm64
        self.python_version = platform.python_version()
        self.gpu_type = "cpu"       # cuda / rocm / mps / cpu
        self.gpu_name = "None"
        self.vram_gb = 0
        self.ram_gb = 0
        self.cuda_version = None
        self.rocm_version = None
        self.torch_index = None     # pip index URL for torch

    def detect(self):
        """Detect all hardware."""
        self._detect_ram()
        self._detect_gpu()
        self._set_torch_index()

    def _detect_ram(self):
        try:
            if self.os == "Windows":
                import ctypes
                kernel32 = ctypes.windll.kernel32
                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]
                m = MEMORYSTATUSEX()
                m.dwLength = ctypes.sizeof(m)
                kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
                self.ram_gb = round(m.ullTotalPhys / (1024**3), 1)
            elif self.os == "Darwin":
                out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
                self.ram_gb = round(int(out) / (1024**3), 1)
            else:  # Linux
                with open("/proc/meminfo") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            self.ram_gb = round(int(line.split()[1]) / (1024**2), 1)
                            break
        except Exception:
            self.ram_gb = 0

    def _detect_gpu(self):
        """Detect GPU type and set gpu_type, gpu_name, vram_gb.
        Priority: CUDA > ROCm > MPS > CPU (last resort).
        """
        # 1. NVIDIA CUDA (highest priority — fastest)
        if shutil.which("nvidia-smi"):
            try:
                out = subprocess.check_output(
                    ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                    text=True, stderr=subprocess.DEVNULL
                ).strip()
                if out:
                    parts = out.split(", ")
                    self.gpu_name = parts[0]
                    self.vram_gb = round(int(parts[1]) / 1024, 1) if len(parts) > 1 else 0
                    self.gpu_type = "cuda"
                    # Get CUDA version
                    out2 = subprocess.check_output(["nvidia-smi"], text=True, stderr=subprocess.DEVNULL)
                    for line in out2.split("\n"):
                        if "CUDA Version:" in line:
                            self.cuda_version = line.split("CUDA Version:")[1].strip().split()[0]
                            break
                    return
            except Exception:
                pass

        # 2. AMD ROCm (Linux only — priority 2)
        if self.os == "Linux" and shutil.which("rocm-smi"):
            try:
                out = subprocess.check_output(["rocm-smi", "--showproductname"], text=True, stderr=subprocess.DEVNULL)
                if out and "GPU" in out:
                    self.gpu_type = "rocm"
                    self.gpu_name = "AMD GPU"
                    # Try to get VRAM
                    out2 = subprocess.check_output(["rocm-smi", "--showmeminfo", "vram"], text=True, stderr=subprocess.DEVNULL)
                    for line in out2.split("\n"):
                        if "VRAM Total" in line:
                            val = line.split(":")[-1].strip().replace("B", "")
                            self.vram_gb = round(int(val) / (1024**3), 1)
                            break
                    # Get ROCm version
                    try:
                        out3 = subprocess.check_output(["rocm-smi", "--version"], text=True, stderr=subprocess.DEVNULL)
                        for line in out3.split("\n"):
                            if "version" in line.lower():
                                self.rocm_version = line.split()[-1]
                                break
                    except Exception:
                        pass
                    return
            except Exception:
                pass

        # 3. Apple Silicon MPS (macOS arm64 — priority 3)
        if self.os == "Darwin" and self.machine == "arm64":
            self.gpu_type = "mps"
            try:
                out = subprocess.check_output(["system_profiler", "SPDisplaysDataType"], text=True, stderr=subprocess.DEVNULL)
                for line in out.split("\n"):
                    if "Chip" in line:
                        self.gpu_name = line.split(":")[-1].strip()
                        break
            except Exception:
                self.gpu_name = "Apple Silicon"
            return

        # 4. CPU — last resort (no GPU detected)
        self.gpu_type = "cpu"

    def _set_torch_index(self):
        """Set the pip index URL for the correct PyTorch variant.
        Priority: CUDA > ROCm > MPS > CPU.
        """
        if self.gpu_type == "cuda":
            # CUDA 12.1 is the most common stable build
            self.torch_index = "https://download.pytorch.org/whl/cu121"
        elif self.gpu_type == "rocm":
            self.torch_index = "https://download.pytorch.org/whl/rocm6.1"
        elif self.gpu_type == "mps":
            # macOS: default PyPI build includes MPS support
            self.torch_index = None
        else:
            self.torch_index = "https://download.pytorch.org/whl/cpu"

    def print_summary(self):
        print("\n" + "=" * 60)
        print("HARDWARE DETECTION")
        print("=" * 60)
        print(f"  OS:          {self.os} {self.os_version[:40]}")
        print(f"  Machine:     {self.machine}")
        print(f"  Python:      {self.python_version}")
        print(f"  RAM:         {self.ram_gb} GB")
        print(f"  GPU type:    {self.gpu_type.upper()}")
        print(f"  GPU name:    {self.gpu_name}")
        if self.vram_gb:
            print(f"  VRAM:        {self.vram_gb} GB")
        if self.cuda_version:
            print(f"  CUDA:        {self.cuda_version}")
        if self.rocm_version:
            print(f"  ROCm:        {self.rocm_version}")
        print(f"  Torch index: {self.torch_index or 'default PyPI'}")
        print("=" * 60)

    def is_compatible(self):
        """Check the *selected* interpreter's version against the policy.

        Returns True when an interpreter in [3.10, 3.13] was located. The
        preferred range is 3.10-3.12 (pinned deps); 3.13 is allowed with a
        warning and upgraded dependencies.
        """
        global SELECTED_PYTHON
        v = sys.version_info
        print(f"\n[CHECK] Current interpreter: Python {v.major}.{v.minor}.{v.micro}")
        print(f"        {sys.executable}")

        candidate = find_compatible_python()
        if candidate is None:
            print("\nERROR: No compatible Python interpreter found.")
            print(f"  Preferred:  Python {PY_PREFERRED[0][0]}.{PY_PREFERRED[0][1]}-"
                  f"{PY_PREFERRED[1][0]}.{PY_PREFERRED[1][1]}")
            print(f"  Acceptable: up to Python {PY_MAX[0]}.{PY_MAX[1]}")
            print("  Install one of the above and ensure it is on PATH, then rerun.")
            if not _ARGS.no_prompt:
                offer_install_python()
            return False

        SELECTED_PYTHON = candidate
        # Report the chosen interpreter's version.
        cv = _python_version(candidate)
        print(f"[OK] Selected interpreter: Python {cv[0]}.{cv[1]} "
              f"-> {candidate}")
        if cv > (PY_PREFERRED[1][0], PY_PREFERRED[1][1]):
            print("  WARNING: Python 3.13+ selected — using upgraded deps "
                  "(numpy>=2.1, torch==2.6.0).")
            print("  This path is less tested; SAM3 vendored source declares "
                  "numpy<2.")
        return True


def _python_version(exe):
    """Return (major, minor) for an interpreter, or (0, 0) on failure."""
    try:
        out = subprocess.check_output(
            [exe, "-c", "import sys; print(sys.version_info[:2])"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
        # Output looks like "(3, 12)" or "sys.version_info(major=3, minor=12)"
        import ast
        return ast.literal_eval(out)
    except Exception:
        return (0, 0)


def find_compatible_python():
    """Locate a Python interpreter in the supported range.

    Preference order:
      1. Current interpreter (sys.executable) if in preferred range 3.10-3.12.
      2. Current interpreter if in acceptable range up to 3.13.
      3. `py` launcher (Windows) / `python3.X` (Linux/macOS) for 3.10-3.12.
      4. `py` launcher / `python3.13` as a last resort.
    Returns the executable path or None.
    """
    cur = _python_version(sys.executable)
    lo, hi = PY_PREFERRED
    if lo <= cur <= hi:
        return sys.executable
    if cur <= PY_MAX and cur >= (3, 10):
        return sys.executable

    # Build candidate list: preferred minors first, then 3.13 as fallback.
    candidates = []
    for minor in range(lo[1], hi[1] + 1):
        candidates.append(f"3.{minor}")
    candidates.append(f"{PY_MAX[0]}.{PY_MAX[1]}")

    for ver in candidates:
        exe = _lookup_python(ver)
        if exe:
            cv = _python_version(exe)
            if cv != (0, 0) and (3, 10) <= cv <= PY_MAX:
                return exe
    return None


def _lookup_python(ver):
    """Find an executable for a specific `major.minor` version string."""
    if os.name == "nt":
        # Windows: py launcher. `py -3.12` prints the path with -0p flag.
        for launcher in ("py", "py.exe"):
            if shutil.which(launcher):
                try:
                    out = subprocess.check_output(
                        [launcher, f"-{ver}", "-0p"],
                        text=True, stderr=subprocess.DEVNULL,
                    ).strip()
                    if out:
                        # First line is the interpreter path.
                        return out.splitlines()[0].strip()
                except Exception:
                    pass
        # Common install locations as a fallback.
        for base in (
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python"),
            r"C:\Python",
            r"C:\Program Files\Python311",
            r"C:\Program Files\Python312",
        ):
            cand = os.path.join(base, f"Python{ver.replace('.', '')}",
                                "python.exe")
            if os.path.exists(cand):
                return cand
    else:
        # Unix: try python3.X on PATH, then well-known prefixes.
        for name in (f"python{ver}", f"python{ver[0]}"):
            path = shutil.which(name)
            if path:
                return path
        for prefix in ("/usr/bin", "/usr/local/bin", "/opt/conda/bin"):
            cand = os.path.join(prefix, f"python{ver}")
            if os.path.exists(cand):
                return cand
    return None


def offer_install_python():
    """Interactively offer to install a compatible Python (WSL2/Ubuntu)."""
    print()
    if os.name == "nt":
        print("On Windows, install Python 3.12 from:")
        print("  https://www.python.org/downloads/release/python-3120/")
        print("Then rerun this setup.")
        return
    try:
        ans = input("Install Python 3.12 via apt now? [y/N] ").strip().lower()
    except EOFError:
        return
    if ans != "y":
        return
    print("[SETUP] Installing python3.12 and venv module via apt...")
    try:
        subprocess.check_call(
            ["sudo", "apt-get", "update", "-y"], stderr=subprocess.DEVNULL
        )
        subprocess.check_call(
            ["sudo", "apt-get", "install", "-y",
             "python3.12", "python3.12-venv", "python3-pip"],
            stderr=subprocess.DEVNULL,
        )
        print("[OK] Python 3.12 installed. Rerun setup to continue.")
    except Exception as e:
        print(f"[ERROR] apt install failed: {e}")
        print("  Install python3.12 manually and rerun.")


# ---------------------------------------------------------------------------
# Setup steps
# ---------------------------------------------------------------------------

def get_venv_python():
    if os.name == "nt":
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    return os.path.join(VENV_DIR, "bin", "python")


def get_venv_pip():
    if os.name == "nt":
        return os.path.join(VENV_DIR, "Scripts", "pip.exe")
    return os.path.join(VENV_DIR, "bin", "pip")


def create_venv():
    """Create virtual environment from the selected interpreter if missing."""
    if os.path.exists(get_venv_python()):
        print("[OK] Virtual environment exists")
        return

    base = SELECTED_PYTHON or sys.executable
    print(f"[SETUP] Creating Python virtual environment from: {base}")
    subprocess.check_call([base, "-m", "venv", VENV_DIR])
    print(f"[OK] Created venv: {VENV_DIR}")


def _venv_python_version():
    """Return (major, minor) of the interpreter inside the venv."""
    return _python_version(get_venv_python())


def install_torch(hw: HardwareInfo, force_cpu: bool = False):
    """Install PyTorch variant matching hardware and the venv's Python.

    torch==2.5.1 for Python 3.10-3.12 (pinned, stable for the project).
    torch==2.6.0 for Python 3.13+ (first release with full 3.13 support).
    Source: https://github.com/pytorch/pytorch/blob/2c13a07/RELEASE.md
    """
    pip = get_venv_pip()
    gpu_type = "cpu" if force_cpu else hw.gpu_type
    pv = _venv_python_version()
    torch_ver, tv_ver = ("2.5.1", "0.20.1") if pv <= (3, 12) else ("2.6.0", "0.21.0")

    print(f"\n[SETUP] Installing PyTorch {torch_ver} ({gpu_type.upper()}) "
          f"for Python {pv[0]}.{pv[1]}...")

    if gpu_type == "cuda":
        subprocess.check_call([
            pip, "install", f"torch=={torch_ver}", f"torchvision=={tv_ver}",
            "--index-url", "https://download.pytorch.org/whl/cu121"
        ])
    elif gpu_type == "rocm":
        subprocess.check_call([
            pip, "install", f"torch=={torch_ver}", f"torchvision=={tv_ver}",
            "--index-url", "https://download.pytorch.org/whl/rocm6.1"
        ])
    elif gpu_type == "mps":
        # macOS arm64: default PyPI build has MPS
        subprocess.check_call([
            pip, "install", f"torch=={torch_ver}", f"torchvision=={tv_ver}"
        ])
    else:  # cpu
        subprocess.check_call([
            pip, "install", f"torch=={torch_ver}", f"torchvision=={tv_ver}",
            "--index-url", "https://download.pytorch.org/whl/cpu"
        ])

    print(f"[OK] PyTorch installed ({gpu_type})")


def install_requirements():
    """Install remaining requirements (excluding torch, already installed).

    For Python 3.13+ the pinned numpy==1.26.4 (no cp313 wheel) is replaced
    with numpy>=2.1 which ships cp313 wheels. Source:
    https://numpy.org/doc/2.3/release/1.26.4-notes.html (3.9-3.12 only)
    """
    pip = get_venv_pip()
    req_path = os.path.join(BASE_DIR, "requirements.txt")
    pv = _venv_python_version()
    is_py313 = pv > (3, 12)

    # Read requirements and filter out torch/torchvision (already installed)
    with open(req_path, "r") as f:
        lines = f.readlines()
    filtered = [l.strip() for l in lines
                if l.strip() and not l.strip().startswith("#")
                and not l.strip().lower().startswith("torch")]

    if is_py313:
        # numpy 1.26.4 has no cp313 wheel; upgrade to 2.x.
        upgraded = []
        for line in filtered:
            if line.lower().startswith("numpy=="):
                upgraded.append("numpy>=2.1")
            else:
                upgraded.append(line)
        filtered = upgraded
        print("  [INFO] Python 3.13+ detected: using numpy>=2.1 "
              "(1.26.4 has no cp313 wheel).")

    # Write temp requirements
    temp_req = os.path.join(BASE_DIR, "requirements_temp.txt")
    with open(temp_req, "w") as f:
        f.write("\n".join(filtered))

    print("\n[SETUP] Installing remaining dependencies...")
    subprocess.check_call([pip, "install", "-r", temp_req])
    os.remove(temp_req)
    print("[OK] SAM dependencies installed")

    # Install YOLO dependencies (ultralytics, mlflow, albumentations, etc.)
    yolo_req = os.path.join(os.path.dirname(BASE_DIR), "yolo26_ppe", "requirements.txt")
    if os.path.exists(yolo_req):
        print("\n[SETUP] Installing YOLO dependencies...")
        subprocess.check_call([pip, "install", "-r", yolo_req])
        print("[OK] YOLO dependencies installed")
    else:
        print(f"[WARN] YOLO requirements not found at {yolo_req}")


def download_checkpoint():
    """Download SAM 3.1 checkpoint if missing, asking the user first."""
    if os.path.exists(CKPT_PATH):
        size_gb = round(os.path.getsize(CKPT_PATH) / (1024**3), 2)
        print(f"[OK] SAM 3.1 checkpoint exists ({size_gb} GB)")
        return

    print(f"\n[SETUP] SAM 3.1 checkpoint is missing.")
    print(f"  URL: {CKPT_URL}")
    print(f"  To:  {CKPT_PATH}")
    print(f"  Size: ~1-2 GB (this may take a while)")

    if not _ARGS.no_prompt:
        try:
            ans = input("\nDownload the checkpoint now? [Y/n] ").strip().lower()
        except EOFError:
            ans = "y"
        if ans in ("n", "no"):
            print("[SKIP] Checkpoint download skipped.")
            print(f"  Place it manually at {CKPT_PATH} before running inference.")
            return

    os.makedirs(MODEL_DIR, exist_ok=True)
    print("[SETUP] Downloading SAM 3.1 checkpoint...")

    try:
        urllib.request.urlretrieve(CKPT_URL, CKPT_PATH)
        size_gb = round(os.path.getsize(CKPT_PATH) / (1024**3), 2)
        print(f"[OK] Downloaded checkpoint ({size_gb} GB)")

        # Integrity verification (if hash is configured)
        if CKPT_SHA256:
            print("[SETUP] Verifying checkpoint integrity (SHA256)...")
            import hashlib
            sha = hashlib.sha256()
            with open(CKPT_PATH, "rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    sha.update(chunk)
            actual = sha.hexdigest()
            if actual.lower() != CKPT_SHA256.lower():
                print(f"[ERROR] Checksum mismatch!")
                print(f"  Expected: {CKPT_SHA256}")
                print(f"  Got:      {actual}")
                os.remove(CKPT_PATH)
                print("[ERROR] Corrupted checkpoint removed. Please re-run setup.")
                return
            print("[OK] Checkpoint integrity verified")
    except Exception as e:
        print(f"[ERROR] Download failed: {e}")
        print(f"  Please download manually from: {CKPT_URL}")
        print(f"  And place at: {CKPT_PATH}")


def verify_torch(hw: HardwareInfo):
    """Verify PyTorch can use the detected hardware."""
    py = get_venv_python()
    print("\n[SETUP] Verifying PyTorch...")

    code = f"""
import torch
print(f"  PyTorch: {{torch.__version__}}")
print(f"  CUDA available: {{torch.cuda.is_available()}}")
print(f"  MPS available: {{torch.backends.mps.is_available()}}")
gpu_type = "{hw.gpu_type}"
if gpu_type == "cuda" and torch.cuda.is_available():
    print(f"  GPU: {{torch.cuda.get_device_name(0)}}")
    print(f"  VRAM: {{round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 1)}} GB")
elif gpu_type == "mps" and torch.backends.mps.is_available():
    print("  MPS (Apple Silicon): ready")
elif gpu_type == "cpu":
    print("  CPU mode: ready")
else:
    print(f"  WARNING: expected {{gpu_type}} but not available")
"""
    result = subprocess.run([py, "-c", code], capture_output=True, text=True)
    print(result.stdout.strip())
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr.strip()}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# Parsed CLI args, accessible by helper functions (set in main()).
_ARGS = argparse.Namespace(no_prompt=False)


def main():
    global _ARGS
    parser = argparse.ArgumentParser(description="Auto-detect hardware and install dependencies")
    parser.add_argument("--check", action="store_true", help="Detect only, no install")
    parser.add_argument("--force-cpu", action="store_true", help="Force CPU-only PyTorch")
    parser.add_argument("--no-prompt", action="store_true",
                        help="Non-interactive: skip download confirmations")
    _ARGS = parser.parse_args()
    args = _ARGS

    print("PPE Segmentation Platform — Setup")
    print()

    # 1. Detect hardware
    hw = HardwareInfo()
    hw.detect()
    hw.print_summary()

    if not hw.is_compatible():
        sys.exit(1)

    if args.check:
        print("\n--check mode: skipping installation")
        print("Run without --check to install")
        return

    # 2. Create venv
    print("\n[STEP 1/5] Virtual environment")
    create_venv()

    # 3. Install PyTorch (hardware-specific)
    print("\n[STEP 2/5] PyTorch")
    install_torch(hw, force_cpu=args.force_cpu)

    # 4. Install other deps
    print("\n[STEP 3/5] Other dependencies")
    install_requirements()

    # 5. Download model
    print("\n[STEP 4/5] SAM 3.1 checkpoint")
    download_checkpoint()

    # 6. Verify
    print("\n[STEP 5/5] Verification")
    verify_torch(hw)

    # Done
    print("\n" + "=" * 60)
    print("SETUP COMPLETE")
    print("=" * 60)
    print(f"  Venv:       {VENV_DIR}")
    print(f"  Checkpoint: {CKPT_PATH}")
    print(f"  GPU mode:   {( 'cpu' if args.force_cpu else hw.gpu_type).upper()}")
    print()
    print("Next steps — batch CLI (no web service):")
    if os.name == "nt":
        print("  sam3_venv\\Scripts\\python.exe src\\batch_segment.py -c config\\ppe_4class.yaml --input ..\\data\\raw\\<batch> --output ..\\data\\sam_outputs_ground_truth\\<batch> --fresh")
    else:
        print("  source sam3_venv/bin/activate && python src/batch_segment.py -c config/ppe_4class.yaml --input ../data/raw/<batch> --output ../data/sam_outputs_ground_truth/<batch> --fresh")
    print("  -> Annotations in <output>/coco/, visualizations in <output>/viz/")
    print("=" * 60)


if __name__ == "__main__":
    main()
