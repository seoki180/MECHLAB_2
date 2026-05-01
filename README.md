# MECHLab PDF Parser

반도체 부품 데이터시트(PDF)에서 **Part Number**와 **부품 크기(L/W/T)** 정보를 추출하여 CSV로 저장하는 GUI 도구입니다.

---

## 지원 제조사 및 모델

| 제조사 | 모델 |
|--------|------|
| cyntec | (단일) |
| infineon | (단일) |
| kemet | (단일) |
| kyocera | CM, CT, CX |
| murata | GJM, GRM(A), GRM(B), LQP, NCP |

---

## 프로젝트 구조

```
MECHLab/
├── app.py                  # wxPython GUI 진입점
├── maker.txt               # Maker 목록 (외부 파일, 자동 생성)
├── model.txt               # Maker-Model 매핑 (외부 파일, 자동 생성)
│
├── parsers/                # 파서 패키지
│   ├── __init__.py         # REGISTRY 자동 등록 및 공개 API
│   ├── base.py             # BaseParser ABC / LegacyScriptParser
│   ├── cyntec.py           # CyntecParser
│   ├── kyocera_cm.py       # KyoceraCmParser
│   └── ...                 # 나머지 파서 모듈
│
├── UI자료/                  # 레거시 파싱 스크립트 (수정 없이 유지)
│   ├── cyntec.py
│   ├── murata_GJM.py
│   └── ...
│
└── tests/                  # pytest 테스트
    ├── conftest.py
    ├── test_base.py
    └── test_registry.py
```

---

## 실행 방법

### 의존성

- Python 3.13+
- `wxPython` — GUI 프레임워크
- `PyMuPDF (fitz)` — PDF 파싱 (miniconda3 환경에 설치)

```bash
# wxPython 설치 (wxPython 환경)
pip install wxpython

# PyMuPDF는 별도 conda 환경에 설치되어 있어도 자동 탐지됨
conda install -c conda-forge pymupdf
```

### GUI 실행

```bash
python app.py
```

---

## 사용 방법

1. **파서 선택** — SELECTION 체크리스트에서 원하는 `(Maker / Model)` 쌍을 하나 이상 체크
   - 상단 검색창으로 빠르게 필터링 가능
   - `전체 선택` / `전체 해제` 버튼으로 일괄 조작
2. **Input 폴더** — PDF 파일이 있는 폴더 지정 (1개 파서 선택 시 기본 경로 자동 입력)
3. **Output 폴더** — CSV 저장 위치 확인/변경
4. **EXTRACTION 실행** — 선택된 파서를 순차 실행, 실행 로그 실시간 표시
   - 파서 2개 이상 선택 시 `compiled_output.csv`로 자동 통합
   - 일부 파서 실패해도 나머지는 계속 진행
5. **COMPILATION 실행** — Output 폴더의 모든 CSV를 하나로 수동 통합
6. **Parser 추가** — 외부에서 작성한 파서 `.py` 파일을 선택하면 `parsers/`에 등록

> 상태바 우측에 `선택: N개 파서` 가 실시간 표시됩니다.

---

## 변경 이력

### v2.0 — 다중 선택 / 자동 통합 / 파서 업로드

- **SELECTION 영역 재설계**: Maker+Model 드롭다운 → `(Maker / Model)` 쌍 체크리스트
  - `wx.CheckListBox` + `SearchCtrl` 필터 + `전체 선택` / `전체 해제` 버튼
- **다중 파서 동시 실행**: 체크한 파서를 한 번에 실행, 각 파서가 동일 Input 폴더 처리
- **자동 통합 CSV**: 2개 이상 선택 실행 시 `compiled_output.csv` 자동 생성
- **Parser 추가 버튼**: UI에서 `.py` 파일 선택 → `parsers/` 에 즉시 등록, 체크리스트에 반영
- `parsers/__init__.py` 에 `reload_registry()` 추가 — 런타임 파서 동적 등록

---

## 파서 추가 방법

### UI에서 추가 (런타임)

`SELECTION` 영역의 `Parser 추가` 버튼 → `.py` 파일 선택 → 자동 등록.

### 직접 추가 (파일)

`parsers/` 폴더에 새 파일을 추가하기만 하면 다음 실행 시 자동 등록됩니다.

### 1. 레거시 스크립트 방식 (기존 스크립트 재사용)

```python
# parsers/newmaker_modelx.py
from .base import LegacyScriptParser

class NewmakerModelxParser(LegacyScriptParser):
    maker = "newmaker"
    model = "ModelX"
    script_name = "newmaker_ModelX.py"   # UI자료/ 내 스크립트 파일명
    input_folder = "newmaker_ModelX"     # 입력 PDF 폴더명
    legacy_output_csv = "newmaker_ModelX_output.csv"
```

`UI자료/newmaker_ModelX.py` 파일을 넣으면 완료 — `app.py` 수정 불필요.

### 2. 네이티브 방식 (새로 구현)

```python
# parsers/newmaker_modely.py
from pathlib import Path
from .base import BaseParser

class NewmakerModelyParser(BaseParser):
    maker = "newmaker"
    model = "ModelY"

    def parse(self, input_dir: Path) -> list[dict[str, str]]:
        rows = []
        for pdf in input_dir.glob("*.pdf"):
            self.emit(f"> Processing {pdf.name}")
            # ... 파싱 로직 ...
            rows.append({"pdfname": pdf.name, "PartNumber": "...", "L": "", "W": "", "T": ""})
        return rows
```

---

## 테스트

```bash
python -m pytest tests/ -v
```

| 테스트 파일 | 내용 |
|------------|------|
| `test_registry.py` | REGISTRY 자동 등록, maker/model 목록 검증 |
| `test_base.py` | BaseParser 인터페이스, 필수 속성 강제 검증 |
| `test_cyntec.py` | CyntecParser 입력 검증 |

---

## maker.txt / model.txt

앱 최초 실행 시 자동 생성됩니다. 직접 편집하여 표시 순서나 항목을 제어할 수 있습니다.

```
# maker.txt
cyntec
infineon
kyocera
murata
```

```
# model.txt
kyocera,CM
kyocera,CT
murata,GJM
murata,GRM(A)
```

`#`으로 시작하는 줄은 주석으로 무시됩니다.

---

## 아키텍처 메모

- `LegacyScriptParser`는 기존 스크립트를 **subprocess 없이 in-process**로 실행 (`runpy.run_path`)
- `fitz` 위치는 현재 환경 → conda 공통 경로 순으로 자동 탐지
- `REGISTRY`는 `pkgutil.iter_modules`로 `parsers/` 폴더를 스캔하여 자동 구성
