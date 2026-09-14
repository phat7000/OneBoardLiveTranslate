"""Distribution entry point and offline runtime verification.

The GUI executable invokes this with the bundled Python. Keeping an ordinary
Python runtime preserves upstream multiprocessing and dynamic model imports.
"""

import json
import multiprocessing
import sys
from pathlib import Path


def _smoke_worker(connection):
    import asr_worker

    connection.send({"executable": sys.executable, "worker": asr_worker.__name__})
    connection.close()


def smoke_test(report_path: Path) -> None:
    """Verify packaged native libraries, Qt, local VAD and spawn, without models."""
    import importlib
    import importlib.metadata
    import os

    # Never make smoke verification a model-download operation.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import main
    import torch
    import torchaudio
    from PyQt6.QtWidgets import QApplication
    from oneboard_paths import data_dir
    from vad_processor import VADProcessor

    for module in ("faster_whisper", "pyaudiowpatch", "yasbd", "funasr", "modelscope"):
        importlib.import_module(module)
    resampled = torchaudio.functional.resample(torch.zeros(1600), 16000, 8000)
    if resampled.numel() != 800:
        raise RuntimeError("Bundled torchaudio resampling returned an unexpected shape")
    app = QApplication.instance() or QApplication([])
    icon = main.create_app_icon()
    if icon.isNull():
        raise RuntimeError("Qt application icon could not be rendered")
    VADProcessor()  # Uses the small Silero asset shipped in its dependency wheel.
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=_smoke_worker, args=(child,))
    process.start()
    child.close()
    try:
        if not parent.poll(45):
            raise RuntimeError("Bundled Python worker did not start within 45 seconds")
        worker = parent.recv()
        process.join(10)
        if process.exitcode != 0:
            raise RuntimeError(f"Bundled worker exited with {process.exitcode}")
    finally:
        if process.is_alive():
            process.terminate()
            process.join(5)
        parent.close()
    report = {
        "ok": True,
        "executable": sys.executable,
        "prefix": sys.prefix,
        "data_dir": str(data_dir()),
        "worker": worker,
        "qt_platform": app.platformName(),
        "torch": torch.__version__,
        "torchaudio": torchaudio.__version__,
        "cuda_available": torch.cuda.is_available(),
        "checks": ["application imports", "native audio/ASR imports", "torchaudio resample",
                   "Qt rendering", "offline Silero VAD", "multiprocessing spawn"],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    if len(sys.argv) == 3 and sys.argv[1] == "--smoke-test":
        smoke_test(Path(sys.argv[2]).resolve())
    else:
        import main

        main.main()
