from __future__ import annotations

import csv
import io
import os
import runpy
import shutil
import sys
import tempfile
from abc import ABC, abstractmethod
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Callable


APP_DIR = Path(__file__).resolve().parents[1]
LEGACY_PARSER_DIR = APP_DIR / "UI자료"
STANDARD_COLUMNS = ["pdfname", "PartNumber", "L", "W", "T"]
LogCallback = Callable[[str], None]


def _find_fitz_site_packages() -> Path | None:
    """fitz가 설치된 site-packages 경로를 동적으로 탐색."""
    import glob

    # 1. 현재 환경에서 바로 찾기
    try:
        import fitz as _fitz
        return Path(_fitz.__file__).resolve().parent.parent
    except ImportError:
        pass

    # 2. 공통 conda/homebrew 위치 탐색
    home = Path.home()
    search_roots = [
        "/opt/miniconda3", "/opt/anaconda3", "/opt/homebrew",
        str(home / "miniconda3"), str(home / "anaconda3"),
        str(home / "opt/miniconda3"),
    ]
    candidates: list[Path] = []
    for root in search_roots:
        for sp in glob.glob(f"{root}/lib/python3.*/site-packages"):
            candidates.append(Path(sp))
        for sp in glob.glob(f"{root}/envs/*/lib/python3.*/site-packages"):
            candidates.append(Path(sp))

    for sp in candidates:
        if (sp / "fitz").is_dir():
            return sp

    return None


class BaseParser(ABC):
    maker: str
    model: str

    def __init__(self, log: LogCallback | None = None):
        self.log = log

    @abstractmethod
    def parse(self, input_dir: Path) -> list[dict[str, str]]:
        pass

    def emit(self, message: str) -> None:
        if self.log:
            self.log(message)

    @property
    def output_csv_name(self) -> str:
        return f"{self.maker}_{self.model}_output.csv".replace("/", "_")

    def write_csv(self, rows: list[dict[str, str]], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=STANDARD_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)


class _LogStream(io.TextIOBase):
    def __init__(self, emit: LogCallback):
        self.emit = emit
        self._buffer = ""

    def writable(self) -> bool:
        return True

    def write(self, text: str) -> int:
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._safe_emit(line.rstrip())
        return len(text)

    def flush(self) -> None:
        if self._buffer:
            self._safe_emit(self._buffer.rstrip())
            self._buffer = ""

    def _safe_emit(self, message: str) -> None:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        try:
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__
            self.emit(message)
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr


@contextmanager
def pushd(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def copy_or_link(src: Path, dst: Path) -> None:
    if dst.exists() or dst.is_symlink():
        if dst.is_dir() and not dst.is_symlink():
            shutil.rmtree(dst)
        else:
            dst.unlink()
    try:
        dst.symlink_to(src.resolve(), target_is_directory=True)
    except OSError:
        shutil.copytree(src, dst)


class LegacyScriptParser(BaseParser):
    script_name: str
    input_folder: str
    legacy_output_csv: str

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        for attr in ("maker", "model", "script_name", "input_folder", "legacy_output_csv"):
            if not isinstance(getattr(cls, attr, None), str):
                raise TypeError(f"{cls.__name__} must define class attribute '{attr}': str")

    @property
    def output_csv_name(self) -> str:
        return self.legacy_output_csv

    def parse(self, input_dir: Path) -> list[dict[str, str]]:
        input_dir = Path(input_dir).expanduser().resolve()
        if not input_dir.is_dir():
            raise FileNotFoundError(f"Input folder not found: {input_dir}")

        script_path = LEGACY_PARSER_DIR / self.script_name
        if not script_path.exists():
            raise FileNotFoundError(f"Legacy parser not found: {script_path}")

        self.emit(f"> Running parser in-process: {self.script_name}")

        with tempfile.TemporaryDirectory(prefix="mechlab_parser_") as tmp:
            work_dir = Path(tmp)
            shutil.copy2(script_path, work_dir / self.script_name)
            copy_or_link(input_dir, work_dir / self.input_folder)
            if (LEGACY_PARSER_DIR / "mask").exists():
                copy_or_link(LEGACY_PARSER_DIR / "mask", work_dir / "mask")
            (work_dir / "output").mkdir(exist_ok=True)

            log_stream = _LogStream(self.emit)
            old_path = list(sys.path)
            old_modules = {
                name: module
                for name, module in sys.modules.items()
                if name == "fitz" or name.startswith("fitz.") or name == "frontend" or name.startswith("frontend.")
            }
            for name in old_modules:
                sys.modules.pop(name, None)

            fitz_sp = _find_fitz_site_packages()
            new_path = [str(work_dir)]
            if fitz_sp:
                fitz_sp_str = str(fitz_sp)
                if fitz_sp_str not in new_path:
                    new_path.append(fitz_sp_str)
            new_path.extend(path for path in old_path if ".venv" not in path and path not in new_path)
            sys.path[:] = new_path
            try:
                with pushd(work_dir), redirect_stdout(log_stream), redirect_stderr(log_stream):
                    runpy.run_path(str(work_dir / self.script_name), run_name=f"__mechlab_{self.maker}_{self.model}__")
            finally:
                log_stream.flush()
                sys.path[:] = old_path
                for name in list(sys.modules):
                    if name == "fitz" or name.startswith("fitz.") or name == "frontend" or name.startswith("frontend."):
                        sys.modules.pop(name, None)
                sys.modules.update(old_modules)

            output_path = work_dir / "output" / self.legacy_output_csv
            if not output_path.exists():
                candidates = sorted((work_dir / "output").glob("*.csv"))
                if not candidates:
                    raise FileNotFoundError("Parser finished but no CSV was created.")
                output_path = candidates[0]

            return self._read_standard_rows(output_path)

    def _read_standard_rows(self, csv_path: Path) -> list[dict[str, str]]:
        with csv_path.open("r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = [self._normalize_row(row) for row in reader]
        return rows

    def _normalize_row(self, row: dict[str, str]) -> dict[str, str]:
        normalized = {key.strip().lower(): value for key, value in row.items() if key is not None}

        def pick(*names: str) -> str:
            for name in names:
                value = normalized.get(name.lower())
                if value is not None:
                    return value
            return ""

        return {
            "pdfname": pick("pdfname", "Pdfname", "Filename"),
            "PartNumber": pick("PartNumber", "Part Number", "ESD Line"),
            "L": pick("L"),
            "W": pick("W"),
            "T": pick("T"),
        }
