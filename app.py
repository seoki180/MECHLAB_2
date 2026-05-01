"""
MECHLab PDF Parser GUI

wxPython desktop UI for running the existing maker/model parser scripts in
UI자료 and collecting their CSV outputs.
"""

from __future__ import annotations

import csv
import os
import threading
from pathlib import Path

import wx
import wx.grid

from parsers import REGISTRY, get_parser, makers as registered_makers
from parsers.base import BaseParser


APP_DIR = Path(__file__).resolve().parent
PARSER_DIR = APP_DIR / "UI자료"
DEFAULT_OUTPUT_DIR = PARSER_DIR / "test_output"


def ensure_selection_files() -> None:
    maker_path = APP_DIR / "maker.txt"
    model_path = APP_DIR / "model.txt"

    if not maker_path.exists():
        maker_path.write_text("\n".join(registered_makers()) + "\n", encoding="utf-8")

    if not model_path.exists():
        rows = [f"{maker},{model}" for maker, model in sorted(REGISTRY)]
        model_path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def load_makers() -> list[str]:
    ensure_selection_files()
    makers = []
    for line in (APP_DIR / "maker.txt").read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if value and not value.startswith("#"):
            makers.append(value)
    return makers or registered_makers()


def load_models_by_maker() -> dict[str, list[str]]:
    ensure_selection_files()
    models: dict[str, list[str]] = {}
    for line in (APP_DIR / "model.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "," in line:
            maker, model = [part.strip() for part in line.split(",", 1)]
        elif ":" in line:
            maker, model = [part.strip() for part in line.split(":", 1)]
        else:
            continue
        if maker and model:
            models.setdefault(maker, []).append(model)
    if not models:
        for maker, model in sorted(REGISTRY):
            models.setdefault(maker, []).append(model)
    return models


def find_parser_class(maker: str, model: str) -> type[BaseParser] | None:
    return REGISTRY.get((maker, model))


def read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    if not rows:
        return [], []
    return rows[0], rows[1:]

class ResultGrid(wx.grid.Grid):
    def __init__(self, parent):
        super().__init__(parent)
        self.CreateGrid(0, 0)
        self.EnableEditing(False)
        self.SetRowLabelSize(48)
        self.SetDefaultColSize(140)
        self.SetLabelBackgroundColour(wx.Colour(242, 244, 247))
        self.SetGridLineColour(wx.Colour(220, 224, 230))

    def load_csv(self, csv_path: Path) -> None:
        columns, rows = read_csv(csv_path)
        self.load(columns, rows)

    def load(self, columns: list[str], rows: list[list[str]]) -> None:
        if self.GetNumberRows():
            self.DeleteRows(0, self.GetNumberRows())
        if self.GetNumberCols():
            self.DeleteCols(0, self.GetNumberCols())

        if columns:
            self.AppendCols(len(columns))
            for col, label in enumerate(columns):
                self.SetColLabelValue(col, label)

        if rows:
            self.AppendRows(len(rows))
            for row_idx, row in enumerate(rows):
                for col_idx, value in enumerate(row[: len(columns)]):
                    self.SetCellValue(row_idx, col_idx, value)

        self.AutoSizeColumns()


class MainFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="MECHLab PDF Extraction", size=(1180, 760))
        self.SetMinSize((980, 640))
        self.makers = load_makers()
        self.models_by_maker = load_models_by_maker()
        self.current_csv: Path | None = None
        self.worker: threading.Thread | None = None
        self._build_ui()
        self._bind_events()
        self._refresh_models()
        self.Centre()

    def _build_ui(self) -> None:
        panel = wx.Panel(self)
        root = wx.BoxSizer(wx.VERTICAL)

        top = wx.Panel(panel)
        top_sizer = wx.BoxSizer(wx.VERTICAL)

        selection = wx.StaticBoxSizer(wx.StaticBox(top, label="SELECTION"), wx.HORIZONTAL)
        selection.Add(wx.StaticText(top, label="Maker"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.txt_maker = wx.TextCtrl(top, style=wx.TE_READONLY)
        self.txt_maker.SetMinSize((140, -1))
        if self.makers:
            self.txt_maker.SetValue(self.makers[0])
        self.btn_select_maker = wx.Button(top, label="Maker 선택")
        selection.Add(self.txt_maker, 0, wx.RIGHT, 6)
        selection.Add(self.btn_select_maker, 0, wx.RIGHT, 18)
        selection.Add(wx.StaticText(top, label="Model"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.choice_model = wx.Choice(top, choices=[])
        selection.Add(self.choice_model, 0, wx.RIGHT, 18)
        self.btn_reload_lists = wx.Button(top, label="Reload")
        selection.Add(self.btn_reload_lists, 0)
        top_sizer.Add(selection, 0, wx.EXPAND | wx.ALL, 8)

        files = wx.StaticBoxSizer(wx.StaticBox(top, label="FILE"), wx.VERTICAL)
        input_row = wx.BoxSizer(wx.HORIZONTAL)
        input_row.Add(wx.StaticText(top, label="Input 폴더"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.txt_input = wx.TextCtrl(top)
        self.btn_input = wx.Button(top, label="Browse")
        input_row.Add(self.txt_input, 1, wx.RIGHT, 6)
        input_row.Add(self.btn_input, 0)
        files.Add(input_row, 0, wx.EXPAND | wx.ALL, 6)

        output_row = wx.BoxSizer(wx.HORIZONTAL)
        output_row.Add(wx.StaticText(top, label="Output 폴더"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.txt_output = wx.TextCtrl(top, value=str(DEFAULT_OUTPUT_DIR))
        self.btn_output = wx.Button(top, label="Browse")
        output_row.Add(self.txt_output, 1, wx.RIGHT, 6)
        output_row.Add(self.btn_output, 0)
        files.Add(output_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        top_sizer.Add(files, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        actions = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_extract = wx.Button(top, label="EXTRACTION 실행", size=(170, 36))
        self.btn_compile = wx.Button(top, label="COMPILATION 실행", size=(170, 36))
        self.btn_open_output = wx.Button(top, label="Output 열기", size=(120, 36))
        actions.AddStretchSpacer()
        actions.Add(self.btn_extract, 0, wx.RIGHT, 10)
        actions.Add(self.btn_compile, 0, wx.RIGHT, 10)
        actions.Add(self.btn_open_output, 0)
        actions.AddStretchSpacer()
        top_sizer.Add(actions, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        top.SetSizer(top_sizer)
        root.Add(top, 0, wx.EXPAND)

        splitter = wx.SplitterWindow(panel, style=wx.SP_LIVE_UPDATE)
        self.grid = ResultGrid(splitter)
        log_panel = wx.Panel(splitter)
        log_sizer = wx.BoxSizer(wx.VERTICAL)
        log_sizer.Add(wx.StaticText(log_panel, label="실행 로그"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        self.txt_log = wx.TextCtrl(
            log_panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2 | wx.HSCROLL,
        )
        log_sizer.Add(self.txt_log, 1, wx.EXPAND | wx.ALL, 8)
        log_panel.SetSizer(log_sizer)
        splitter.SplitHorizontally(self.grid, log_panel, sashPosition=390)
        splitter.SetMinimumPaneSize(150)
        root.Add(splitter, 1, wx.EXPAND)

        self.statusbar = self.CreateStatusBar(3)
        self.statusbar.SetStatusWidths([-2, -1, -1])
        self.statusbar.SetStatusText("준비", 0)
        self._update_selection_status()

        panel.SetSizer(root)

        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(frame_sizer)
        self.Layout()

    def _bind_events(self) -> None:
        self.btn_select_maker.Bind(wx.EVT_BUTTON, lambda _: self._select_maker_popup())
        self.choice_model.Bind(wx.EVT_CHOICE, lambda _: self._on_model_changed())
        self.btn_reload_lists.Bind(wx.EVT_BUTTON, lambda _: self._reload_lists())
        self.btn_input.Bind(wx.EVT_BUTTON, lambda _: self._choose_directory(self.txt_input, "PDF 입력 폴더 선택"))
        self.btn_output.Bind(wx.EVT_BUTTON, lambda _: self._choose_directory(self.txt_output, "CSV 출력 폴더 선택"))
        self.btn_extract.Bind(wx.EVT_BUTTON, lambda _: self._start_extraction())
        self.btn_compile.Bind(wx.EVT_BUTTON, lambda _: self._compile_outputs())
        self.btn_open_output.Bind(wx.EVT_BUTTON, lambda _: self._open_output_dir())

    def _reload_lists(self) -> None:
        self.makers = load_makers()
        self.models_by_maker = load_models_by_maker()
        if self.makers:
            current = self.txt_maker.GetValue()
            self.txt_maker.SetValue(current if current in self.makers else self.makers[0])
        else:
            self.txt_maker.SetValue("")
        self._refresh_models()
        self._log("Reloaded maker.txt and model.txt")

    def _select_maker_popup(self) -> None:
        if not self.makers:
            wx.MessageBox("maker.txt에 Maker 목록이 없습니다.", "오류", wx.OK | wx.ICON_ERROR)
            return

        current = self.txt_maker.GetValue()
        dlg = wx.SingleChoiceDialog(
            self,
            "Maker를 선택하세요.",
            "Maker 선택",
            self.makers,
            style=wx.CHOICEDLG_STYLE,
        )
        if current in self.makers:
            dlg.SetSelection(self.makers.index(current))

        if dlg.ShowModal() == wx.ID_OK:
            self.txt_maker.SetValue(dlg.GetStringSelection())
            self._refresh_models()
        dlg.Destroy()

    def _refresh_models(self) -> None:
        maker = self.txt_maker.GetValue()
        models = self.models_by_maker.get(maker, [])
        self.choice_model.Set(models)
        if models:
            self.choice_model.SetSelection(0)
        self._update_selection_status()
        self._refresh_default_input()

    def _on_model_changed(self) -> None:
        self._update_selection_status()
        self._refresh_default_input()

    def _refresh_default_input(self) -> None:
        parser_cls = self._selected_parser_class()
        input_folder = getattr(parser_cls, "input_folder", "") if parser_cls else ""
        if input_folder:
            self.txt_input.SetValue(str(PARSER_DIR / input_folder))
        self._update_selection_status()

    def _selected_parser_class(self) -> type[BaseParser] | None:
        return find_parser_class(self.txt_maker.GetValue(), self.choice_model.GetStringSelection())

    def _choose_directory(self, target: wx.TextCtrl, message: str) -> None:
        dlg = wx.DirDialog(self, message=message, defaultPath=target.GetValue() or str(APP_DIR))
        if dlg.ShowModal() == wx.ID_OK:
            target.SetValue(dlg.GetPath())
        dlg.Destroy()

    def _set_status(self, message: str) -> None:
        self.statusbar.SetStatusText(message, 0)
        self._update_selection_status()

    def _update_selection_status(self) -> None:
        maker = self.txt_maker.GetValue() if hasattr(self, "txt_maker") else ""
        model = self.choice_model.GetStringSelection() if hasattr(self, "choice_model") else ""
        self.statusbar.SetStatusText(f"Maker: {maker or '-'}", 1)
        self.statusbar.SetStatusText(f"Model: {model or '-'}", 2)

    def _log(self, message: str) -> None:
        self.txt_log.AppendText(message.rstrip() + os.linesep)

    def _set_running(self, running: bool) -> None:
        self.btn_extract.Enable(not running)
        self.btn_compile.Enable(not running)
        self.btn_reload_lists.Enable(not running)
        self.btn_select_maker.Enable(not running)

    def _start_extraction(self) -> None:
        if self.worker and self.worker.is_alive():
            wx.MessageBox("이미 실행 중입니다.", "알림", wx.OK | wx.ICON_INFORMATION)
            return

        parser_cls = self._selected_parser_class()
        if not parser_cls:
            wx.MessageBox("Maker와 Model을 선택하세요.", "오류", wx.OK | wx.ICON_ERROR)
            return

        input_dir = Path(self.txt_input.GetValue()).expanduser()
        output_dir = Path(self.txt_output.GetValue()).expanduser()
        if not input_dir.is_dir():
            wx.MessageBox(f"입력 폴더가 없습니다:\n{input_dir}", "오류", wx.OK | wx.ICON_ERROR)
            return

        output_dir.mkdir(parents=True, exist_ok=True)
        self.txt_log.Clear()
        self._set_running(True)
        self._set_status(f"실행 중: {parser_cls.maker} / {parser_cls.model}")

        self.worker = threading.Thread(
            target=self._run_parser_worker,
            args=(parser_cls.maker, parser_cls.model, input_dir, output_dir),
            daemon=True,
        )
        self.worker.start()

    def _run_parser_worker(self, maker: str, model: str, input_dir: Path, output_dir: Path) -> None:
        try:
            wx.CallAfter(self._log, f"> Maker: {maker}")
            wx.CallAfter(self._log, f"> Model: {model}")
            wx.CallAfter(self._log, f"> Input: {input_dir}")
            wx.CallAfter(self._log, f"> Output: {output_dir}")
            parser = get_parser(maker, model, log=lambda message: wx.CallAfter(self._log, message))
            rows = parser.parse(input_dir)
            final_csv = output_dir / parser.output_csv_name
            parser.write_csv(rows, final_csv)
            wx.CallAfter(self._on_extraction_done, maker, model, final_csv)
        except Exception as exc:
            wx.CallAfter(self._on_extraction_failed, exc)

    def _on_extraction_done(self, maker: str, model: str, csv_path: Path) -> None:
        self.current_csv = csv_path
        try:
            self.grid.load_csv(csv_path)
            _, rows = read_csv(csv_path)
            self._log(f"> Done. {len(rows)} rows saved: {csv_path}")
            self._set_status(f"완료: {csv_path.name}")
        except Exception as exc:
            self._log(f"> CSV preview failed: {exc}")
            self._set_status(f"저장 완료: {csv_path.name} / 미리보기 실패")
        self._set_running(False)

    def _on_extraction_failed(self, exc: Exception) -> None:
        self._log(f"> ERROR: {exc}")
        self._set_status("오류 발생")
        self._set_running(False)
        wx.MessageBox(str(exc), "실행 오류", wx.OK | wx.ICON_ERROR)

    def _compile_outputs(self) -> None:
        output_dir = Path(self.txt_output.GetValue()).expanduser()
        if not output_dir.is_dir():
            wx.MessageBox(f"출력 폴더가 없습니다:\n{output_dir}", "오류", wx.OK | wx.ICON_ERROR)
            return

        dlg = wx.FileDialog(
            self,
            message="통합 CSV 저장",
            defaultDir=str(output_dir),
            defaultFile="compiled_output.csv",
            wildcard="CSV files (*.csv)|*.csv",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        )
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        compiled_path = Path(dlg.GetPath())
        dlg.Destroy()

        parser_items = []
        csv_paths = []
        for maker, model in sorted(REGISTRY):
            parser = get_parser(maker, model)
            path = output_dir / parser.output_csv_name
            if path.exists():
                parser_items.append((maker, model, path))
                csv_paths.append(path)
        if not csv_paths:
            wx.MessageBox("통합할 CSV가 없습니다.", "알림", wx.OK | wx.ICON_INFORMATION)
            return

        rows_written = 0
        with compiled_path.open("w", newline="", encoding="utf-8-sig") as out:
            writer = csv.writer(out)
            writer.writerow(["Maker", "Model", "SourceCSV", "pdfname", "PartNumber", "L", "W", "T"])
            for maker, model, path in parser_items:
                columns, rows = read_csv(path)
                index = {name.strip().lower(): i for i, name in enumerate(columns)}

                def pick(row: list[str], *names: str, _idx: dict = index) -> str:
                    for name in names:
                        pos = _idx.get(name.lower())
                        if pos is not None and pos < len(row):
                            return row[pos]
                    return ""

                for row in rows:
                    writer.writerow(
                        [
                            maker,
                            model,
                            path.name,
                            pick(row, "pdfname", "pdfname", "filename"),
                            pick(row, "PartNumber", "Part Number", "ESD Line"),
                            pick(row, "L"),
                            pick(row, "W"),
                            pick(row, "T"),
                        ]
                    )
                    rows_written += 1

        self.current_csv = compiled_path
        self.grid.load_csv(compiled_path)
        self._log(f"> Compilation done. {rows_written} rows saved: {compiled_path}")
        self._set_status(f"통합 완료: {compiled_path.name} ({rows_written} rows)")

    def _open_output_dir(self) -> None:
        output_dir = Path(self.txt_output.GetValue()).expanduser()
        if not output_dir.exists():
            wx.MessageBox(f"출력 폴더가 없습니다:\n{output_dir}", "오류", wx.OK | wx.ICON_ERROR)
            return
        wx.LaunchDefaultApplication(str(output_dir))


def main() -> None:
    ensure_selection_files()
    app = wx.App(False)
    frame = MainFrame()
    frame.Show()
    app.MainLoop()


if __name__ == "__main__":
    main()
