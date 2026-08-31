"""Auto-detect hardware and install the right dependencies.

Detects:
  - Platform: Windows / Linux / macOS
  - GPU: NVIDIA CUDA / AMD ROCm / Apple MPS / CPU-only
  - RAM / VRAM

Then:
  1. Creates Python 3.12 venv (if missing)
  2. Installs correct PyTorch variant
  3. Installs remaining requirements
  4. Downloads SAM 3.1 checkpoint (if missing)
  5. Prints summary

Usage:
    python setup.py              # full setup
    python setup.py --check      # just detect and print, no install
    python setup.py --force-cpu  # force CPU-only even if GPU exists
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
MODEL_DIR = os.path.join(BASE_DIR, "models", "sam3")
CKPT_PATH = os.path.join(MODEL_DIR, "sam3.1_multiplex.pt")
CKPT_URL = "https://huggingface.co/facebook/sam3.1/resolve/main/sam3.1_multiplex.pt"

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
        """Check if Python version is compatible (3.10-3.12)."""
        v = sys.version_info
        if v < (3, 10) or v >= (3, 13):
            print(f"\nERROR: Python {v.major}.{v.minor} is not supported.")
            print("SAM 3.1 requires Python 3.10, 3.11, or 3.12.")
            print("Please install Python 3.12 and try again.")
            return False
        return True


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
    """Create virtual environment if it doesn't exist."""
    if os.path.exists(get_venv_python()):
        print("[OK] Virtual environment exists")
        return

    print("[SETUP] Creating Python virtual environment...")
    subprocess.check_call([sys.executable, "-m", "venv", VENV_DIR])
    print(f"[OK] Created venv: {VENV_DIR}")


def install_torch(hw: HardwareInfo, force_cpu: bool = False):
    """Install PyTorch variant matching hardware."""
    pip = get_venv_pip()
    gpu_type = "cpu" if force_cpu else hw.gpu_type

    print(f"\n[SETUP] Installing PyTorch ({gpu_type.upper()})...")

    if gpu_type == "cuda":
        subprocess.check_call([
            pip, "install", "torch==2.5.1", "torchvision==0.20.1",
            "--index-url", "https://download.pytorch.org/whl/cu121"
        ])
    elif gpu_type == "rocm":
        subprocess.check_call([
            pip, "install", "torch==2.5.1", "torchvision==0.20.1",
            "--index-url", "https://download.pytorch.org/whl/rocm6.1"
        ])
    elif gpu_type == "mps":
        # macOS arm64: default PyPI build has MPS
        subprocess.check_call([
            pip, "install", "torch==2.5.1", "torchvision==0.20.1"
        ])
    else:  # cpu
        subprocess.check_call([
            pip, "install", "torch==2.5.1", "torchvision==0.20.1",
            "--index-url", "https://download.pytorch.org/whl/cpu"
        ])

    print(f"[OK] PyTorch installed ({gpu_type})")


def install_requirements():
    """Install remaining requirements (excluding torch, which is already installed)."""
    pip = get_venv_pip()
    req_path = os.path.join(BASE_DIR, "requirements.txt")

    # Read requirements and filter out torch/torchvision (already installed)
    with open(req_path, "r") as f:
        lines = f.readlines()
    filtered = [l.strip() for l in lines
                if l.strip() and not l.strip().startswith("#")
                and not l.strip().lower().startswith("torch")]

    # Write temp requirements
    temp_req = os.path.join(BASE_DIR, "requirements_temp.txt")
    with open(temp_req, "w") as f:
        f.write("\n".join(filtered))

    print("\n[SETUP] Installing remaining dependencies...")
    subprocess.check_call([pip, "install", "-r", temp_req])
    os.remove(temp_req)
    print("[OK] All dependencies installed")


def download_checkpoint():
    """Download SAM 3.1 checkpoint if missing."""
    if os.path.exists(CKPT_PATH):
        size_gb = round(os.path.getsize(CKPT_PATH) / (1024**3), 2)
        print(f"[OK] SAM 3.1 checkpoint exists ({size_gb} GB)")
        return

    os.makedirs(MODEL_DIR, exist_ok=True)
    print(f"\n[SETUP] Downloading SAM 3.1 checkpoint...")
    print(f"  URL: {CKPT_URL}")
    print(f"  To:  {CKPT_PATH}")
    print(f"  (This may take a while — file is ~1-2 GB)")
    print()

    try:
        urllib.request.urlretrieve(CKPT_URL, CKPT_PATH)
        size_gb = round(os.path.getsize(CKPT_PATH) / (1024**3), 2)
        print(f"[OK] Downloaded checkpoint ({size_gb} GB)")
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

def main():
    parser = argparse.ArgumentParser(description="Auto-detect hardware and install dependencies")
    parser.add_argument("--check", action="store_true", help="Detect only, no install")
    parser.add_argument("--force-cpu", action="store_true", help="Force CPU-only PyTorch")
    args = parser.parse_args()

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
    print("Next steps:")
    if os.name == "nt":
        print("  sam3_venv\\Scripts\\python.exe src\\service.py")
    else:
        print("  source sam3_venv/bin/activate && python src/service.py")
    print("  -> API at http://localhost:8000  (docs: http://localhost:8000/docs)")
    print("=" * 60)


if __name__ == "__main__":
    main()
