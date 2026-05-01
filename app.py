"""
MECHLab PDF Parser GUI

wxPython desktop UI for running the existing maker/model parser scripts in
UI자료 and collecting their CSV outputs.
"""

from __future__ import annotations

import csv
import os
import shutil
import threading
from pathlib import Path

import wx
import wx.grid

from parsers import REGISTRY, get_parser, reload_registry
from parsers import makers as registered_makers
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
        self._all_pairs: list[tuple[str, str]] = sorted(REGISTRY)
        self._displayed_pairs: list[tuple[str, str]] = list(self._all_pairs)
        self._checked_pairs: set[tuple[str, str]] = set()
        self.current_csv: Path | None = None
        self.worker: threading.Thread | None = None
        self._build_ui()
        self._bind_events()
        self._refresh_pair_list()
        self.Centre()

    def _build_ui(self) -> None:
        panel = wx.Panel(self)
        root = wx.BoxSizer(wx.VERTICAL)

        top = wx.Panel(panel)
        top_sizer = wx.BoxSizer(wx.VERTICAL)

        # SELECTION 영역
        sel_box = wx.StaticBoxSizer(wx.StaticBox(top, label="SELECTION"), wx.VERTICAL)

        self.txt_search = wx.SearchCtrl(top, style=wx.TE_PROCESS_ENTER)
        self.txt_search.ShowSearchButton(True)
        self.txt_search.ShowCancelButton(True)
        self.txt_search.SetDescriptiveText("파서 필터 (maker / model)...")
        sel_box.Add(self.txt_search, 0, wx.EXPAND | wx.ALL, 4)

        self.chk_parsers = wx.CheckListBox(top, style=wx.LB_NEEDED_SB)
        self.chk_parsers.SetMinSize((-1, 100))
        sel_box.Add(self.chk_parsers, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_select_all = wx.Button(top, label="전체 선택", size=(80, 28))
        self.btn_deselect_all = wx.Button(top, label="전체 해제", size=(80, 28))
        self.btn_add_parser = wx.Button(top, label="Parser 추가", size=(100, 28))
        self.btn_reload_lists = wx.Button(top, label="Reload", size=(70, 28))
        btn_row.Add(self.btn_select_all, 0, wx.RIGHT, 4)
        btn_row.Add(self.btn_deselect_all, 0, wx.RIGHT, 12)
        btn_row.AddStretchSpacer()
        btn_row.Add(self.btn_add_parser, 0, wx.RIGHT, 4)
        btn_row.Add(self.btn_reload_lists, 0)
        sel_box.Add(btn_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)
        top_sizer.Add(sel_box, 0, wx.EXPAND | wx.ALL, 8)

        # FILE 영역
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

        # 실행 버튼
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

        # 결과 그리드 + 로그
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

        self.statusbar = self.CreateStatusBar(2)
        self.statusbar.SetStatusWidths([-2, -1])
        self.statusbar.SetStatusText("준비", 0)
        self._update_selection_status()

        panel.SetSizer(root)
        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(frame_sizer)
        self.Layout()

    def _bind_events(self) -> None:
        self.txt_search.Bind(wx.EVT_TEXT, lambda _: self._on_search_changed())
        self.txt_search.Bind(wx.EVT_SEARCHCTRL_CANCEL_BTN, lambda _: self._on_search_cancel())
        self.chk_parsers.Bind(wx.EVT_CHECKLISTBOX, self._on_check_changed)
        self.btn_select_all.Bind(wx.EVT_BUTTON, lambda _: self._select_all())
        self.btn_deselect_all.Bind(wx.EVT_BUTTON, lambda _: self._deselect_all())
        self.btn_add_parser.Bind(wx.EVT_BUTTON, lambda _: self._add_parser_file())
        self.btn_reload_lists.Bind(wx.EVT_BUTTON, lambda _: self._refresh_pair_list())
        self.btn_input.Bind(wx.EVT_BUTTON, lambda _: self._choose_directory(self.txt_input, "PDF 입력 폴더 선택"))
        self.btn_output.Bind(wx.EVT_BUTTON, lambda _: self._choose_directory(self.txt_output, "CSV 출력 폴더 선택"))
        self.btn_extract.Bind(wx.EVT_BUTTON, lambda _: self._start_extraction())
        self.btn_compile.Bind(wx.EVT_BUTTON, lambda _: self._compile_outputs())
        self.btn_open_output.Bind(wx.EVT_BUTTON, lambda _: self._open_output_dir())

    # ── 파서 목록 관련 ────────────────────────────────────────────────────────

    def _selected_parser_classes(self) -> list[type[BaseParser]]:
        return [REGISTRY[pair] for pair in sorted(self._checked_pairs) if pair in REGISTRY]

    def _refresh_pair_list(self) -> None:
        filter_text = self.txt_search.GetValue().strip().lower() if hasattr(self, "txt_search") else ""
        self._all_pairs = sorted(REGISTRY)
        if filter_text:
            self._displayed_pairs = [
                (m, md) for m, md in self._all_pairs
                if filter_text in m.lower() or filter_text in md.lower()
            ]
        else:
            self._displayed_pairs = list(self._all_pairs)

        self.chk_parsers.Set([f"{m} / {md}" for m, md in self._displayed_pairs])
        for i, pair in enumerate(self._displayed_pairs):
            if pair in self._checked_pairs:
                self.chk_parsers.Check(i, True)

        self._update_selection_status()
        self._refresh_default_input()

    def _on_search_changed(self) -> None:
        self._refresh_pair_list()

    def _on_search_cancel(self) -> None:
        self.txt_search.SetValue("")
        self._refresh_pair_list()

    def _on_check_changed(self, evt: wx.CommandEvent) -> None:
        idx = evt.GetInt()
        if idx < len(self._displayed_pairs):
            pair = self._displayed_pairs[idx]
            if self.chk_parsers.IsChecked(idx):
                self._checked_pairs.add(pair)
            else:
                self._checked_pairs.discard(pair)
        self._update_selection_status()
        self._refresh_default_input()

    def _select_all(self) -> None:
        for i, pair in enumerate(self._displayed_pairs):
            self.chk_parsers.Check(i, True)
            self._checked_pairs.add(pair)
        self._update_selection_status()
        self._refresh_default_input()

    def _deselect_all(self) -> None:
        for i, pair in enumerate(self._displayed_pairs):
            self.chk_parsers.Check(i, False)
            self._checked_pairs.discard(pair)
        self._update_selection_status()
        self._refresh_default_input()

    def _refresh_default_input(self) -> None:
        selected = self._selected_parser_classes()
        if len(selected) == 1 and not self.txt_input.GetValue():
            input_folder = getattr(selected[0], "input_folder", "")
            if input_folder:
                self.txt_input.SetValue(str(PARSER_DIR / input_folder))

    # ── 상태 / 유틸 ─────────────────────────────────────────────────────────

    def _update_selection_status(self) -> None:
        count = len(self._checked_pairs)
        self.statusbar.SetStatusText(f"선택: {count}개 파서", 1)

    def _set_status(self, message: str) -> None:
        self.statusbar.SetStatusText(message, 0)

    def _log(self, message: str) -> None:
        self.txt_log.AppendText(message.rstrip() + os.linesep)

    def _set_running(self, running: bool) -> None:
        for btn in (
            self.btn_extract, self.btn_compile, self.btn_reload_lists,
            self.btn_add_parser, self.btn_select_all, self.btn_deselect_all,
        ):
            btn.Enable(not running)

    def _choose_directory(self, target: wx.TextCtrl, message: str) -> None:
        dlg = wx.DirDialog(self, message=message, defaultPath=target.GetValue() or str(APP_DIR))
        if dlg.ShowModal() == wx.ID_OK:
            target.SetValue(dlg.GetPath())
        dlg.Destroy()

    # ── EXTRACTION ──────────────────────────────────────────────────────────

    def _start_extraction(self) -> None:
        if self.worker and self.worker.is_alive():
            wx.MessageBox("이미 실행 중입니다.", "알림", wx.OK | wx.ICON_INFORMATION)
            return

        selected = self._selected_parser_classes()
        if not selected:
            wx.MessageBox("파서를 하나 이상 선택하세요.", "오류", wx.OK | wx.ICON_ERROR)
            return

        input_dir = Path(self.txt_input.GetValue()).expanduser()
        output_dir = Path(self.txt_output.GetValue()).expanduser()
        if not input_dir.is_dir():
            wx.MessageBox(f"입력 폴더가 없습니다:\n{input_dir}", "오류", wx.OK | wx.ICON_ERROR)
            return

        output_dir.mkdir(parents=True, exist_ok=True)
        self.txt_log.Clear()
        self._set_running(True)
        pairs = [(cls.maker, cls.model) for cls in selected]
        self._set_status(f"실행 중: {len(pairs)}개 파서")

        self.worker = threading.Thread(
            target=self._run_parser_worker,
            args=(pairs, input_dir, output_dir),
            daemon=True,
        )
        self.worker.start()

    def _run_parser_worker(
        self, pairs: list[tuple[str, str]], input_dir: Path, output_dir: Path
    ) -> None:
        total = len(pairs)
        wx.CallAfter(self._log, f"> Selected: {total} parser{'s' if total > 1 else ''}")
        wx.CallAfter(self._log, f"> Input: {input_dir}")
        wx.CallAfter(self._log, f"> Output: {output_dir}")

        success_items: list[tuple[str, str, Path]] = []
        failed_pairs: list[tuple[str, str]] = []

        for idx, (maker, model) in enumerate(pairs, 1):
            wx.CallAfter(self._log, f"> [{idx}/{total}] {maker} / {model} ...")
            try:
                parser = get_parser(maker, model, log=lambda msg: wx.CallAfter(self._log, msg))
                rows = parser.parse(input_dir)
                final_csv = output_dir / parser.output_csv_name
                parser.write_csv(rows, final_csv)
                wx.CallAfter(self._log, f">   → {len(rows)} rows → {final_csv.name}")
                success_items.append((maker, model, final_csv))
            except Exception as exc:
                wx.CallAfter(self._log, f">   → ERROR: {exc}")
                failed_pairs.append((maker, model))

        if total > 1 and success_items:
            compiled_path = output_dir / "compiled_output.csv"
            wx.CallAfter(self._log, f"> Compiling {len(success_items)} outputs → {compiled_path.name}")
            try:
                rows_written = self._compile_csvs(success_items, compiled_path)
                wx.CallAfter(self._log, f"> Done. {rows_written} rows compiled.")
                wx.CallAfter(self._on_extraction_done, success_items, failed_pairs, compiled_path)
            except Exception as exc:
                wx.CallAfter(self._log, f"> Compilation ERROR: {exc}")
                primary = success_items[0][2] if success_items else None
                wx.CallAfter(self._on_extraction_done, success_items, failed_pairs, primary)
        else:
            primary = success_items[0][2] if success_items else None
            wx.CallAfter(self._on_extraction_done, success_items, failed_pairs, primary)

    def _on_extraction_done(
        self,
        success_items: list[tuple[str, str, Path]],
        failed_pairs: list[tuple[str, str]],
        primary_csv: Path | None,
    ) -> None:
        if primary_csv:
            self.current_csv = primary_csv
            try:
                self.grid.load_csv(primary_csv)
            except Exception as exc:
                self._log(f"> CSV preview failed: {exc}")

        if failed_pairs:
            failed_names = ", ".join(f"{m}/{md}" for m, md in failed_pairs)
            self._set_status(f"완료 (실패: {failed_names})")
        elif primary_csv:
            self._set_status(f"완료: {primary_csv.name}")
        else:
            self._set_status("실패: 출력 없음")
        self._set_running(False)

    # ── COMPILATION ─────────────────────────────────────────────────────────

    def _compile_csvs(
        self, parser_items: list[tuple[str, str, Path]], compiled_path: Path
    ) -> int:
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
                    writer.writerow([
                        maker, model, path.name,
                        pick(row, "pdfname", "filename"),
                        pick(row, "PartNumber", "Part Number", "ESD Line"),
                        pick(row, "L"),
                        pick(row, "W"),
                        pick(row, "T"),
                    ])
                    rows_written += 1
        return rows_written

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
        for maker, model in sorted(REGISTRY):
            parser = get_parser(maker, model)
            path = output_dir / parser.output_csv_name
            if path.exists():
                parser_items.append((maker, model, path))

        if not parser_items:
            wx.MessageBox("통합할 CSV가 없습니다.", "알림", wx.OK | wx.ICON_INFORMATION)
            return

        rows_written = self._compile_csvs(parser_items, compiled_path)
        self.current_csv = compiled_path
        self.grid.load_csv(compiled_path)
        self._log(f"> Compilation done. {rows_written} rows saved: {compiled_path}")
        self._set_status(f"통합 완료: {compiled_path.name} ({rows_written} rows)")

    # ── Parser 추가 ──────────────────────────────────────────────────────────

    def _add_parser_file(self) -> None:
        dlg = wx.FileDialog(
            self,
            message="파서 스크립트 선택 (.py)",
            defaultDir=str(APP_DIR),
            wildcard="Python (*.py)|*.py",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        )
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        src_path = Path(dlg.GetPath())
        dlg.Destroy()

        dest_path = APP_DIR / "parsers" / src_path.name
        if dest_path.exists():
            confirm = wx.MessageBox(
                f"'{dest_path.name}' 이(가) 이미 있습니다. 덮어쓰시겠습니까?",
                "덮어쓰기 확인",
                wx.YES_NO | wx.ICON_QUESTION,
            )
            if confirm != wx.YES:
                return

        shutil.copy2(src_path, dest_path)

        try:
            new_keys = reload_registry()
        except Exception as exc:
            dest_path.unlink(missing_ok=True)
            wx.MessageBox(f"파서 등록 실패:\n{exc}", "오류", wx.OK | wx.ICON_ERROR)
            return

        if not new_keys:
            dest_path.unlink(missing_ok=True)
            wx.MessageBox(
                f"'{src_path.name}' 에서 BaseParser 서브클래스를 찾지 못했거나\n이미 등록된 파서입니다.",
                "등록 실패",
                wx.OK | wx.ICON_WARNING,
            )
            return

        self._rewrite_selection_files()
        for key in new_keys:
            self._checked_pairs.add(key)
        self._refresh_pair_list()

        names = ", ".join(f"{m}/{md}" for m, md in new_keys)
        self._log(f"> Parser 추가됨: {names}")
        self._set_status(f"파서 추가: {names}")
        wx.MessageBox(f"파서 등록 완료:\n{names}", "성공", wx.OK | wx.ICON_INFORMATION)

    def _rewrite_selection_files(self) -> None:
        (APP_DIR / "maker.txt").write_text(
            "\n".join(registered_makers()) + "\n", encoding="utf-8"
        )
        (APP_DIR / "model.txt").write_text(
            "\n".join(f"{m},{md}" for m, md in sorted(REGISTRY)) + "\n", encoding="utf-8"
        )

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
