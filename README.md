# MECHLab PDF Parser

반도체 부품 데이터시트(PDF)에서 **Part Number**와 **부품 크기(L/W/T)** 정보를 추출하여 CSV로 저장하는 GUI 도구입니다.

---

## 지원 제조사 및 모델

| 제조사   | 모델                          |
| -------- | ----------------------------- |
| cyntec   | (단일)                        |
| infineon | (단일)                        |
| kemet    | (단일)                        |
| kyocera  | CM, CT, CX                    |
| murata   | GJM, GRM(A), GRM(B), LQP, NCP |

---

## 프로젝트 구조

```
MECHLab/
├── app.py                  # wxPython GUI 진입점
├── maker.txt               # Maker 목록 (자동 생성)
├── model.txt               # Maker-Model 매핑 (자동 생성)
│
├── parsers/                # 파서 패키지
│   ├── __init__.py         # REGISTRY 자동 등록 + reload_registry()
│   ├── base.py             # BaseParser ABC / LegacyScriptParser / fitz_isolation()
│   ├── cyntec.py           # CyntecParser
│   ├── infineon.py         # InfineonParser
│   └── ...
│
├── UI자료/                 # 레거시 파싱 스크립트 (LegacyScriptParser 전용)
│   ├── cyntec.py
│   ├── murata_GJM.py
│   └── ...
│
├── samples/                # 사용자 업로드 테스트용 샘플 파서
│   └── infineon_v2.py      # BaseParser 단일파일 예시
│
├── test_input_pdf/         # 테스트 PDF (브랜드별 하위폴더로 정렬됨)
│   ├── CYNTEC/
│   ├── infineon/
│   ├── kemet/
│   ├── kyocera_CM/, kyocera_CT/, kyocera_CX/
│   └── murata_GJM/, murata_GRM(A)/, murata_GRM(B)/, murata_LQP/, murata_NCP/
│
└── tests/
```

---

## 입력 폴더 규칙 (중요)

각 파서는 **자기 브랜드 하위폴더에서만** PDF를 읽습니다. 입력 폴더는 다음 구조여야 합니다.

```
<input_dir>/
├── CYNTEC/         ← cyntec 파서가 처리
│   └── *.pdf
├── infineon/       ← infineon 파서가 처리
├── kemet/
├── kyocera_CM/, kyocera_CT/, kyocera_CX/
└── murata_GJM/, murata_GRM(A)/, murata_GRM(B)/, murata_LQP/, murata_NCP/
```

- 하위폴더명은 각 파서의 `input_folder` 클래스 속성과 **정확히 일치** (대소문자/괄호 포함).
- 하위폴더가 없으면 그 파서는 `FileNotFoundError` 로그를 남기고 건너뜀.
- 알 수 없는 하위폴더(파서 매칭 안 됨)나 input 최상위에 떠 있는 PDF는 실행 종료 후 경고로 표시됨.

이 규칙으로 인해 메이커별 파서가 다른 메이커 PDF를 잘못 파싱하는 문제가 사라집니다.

브랜드별 폴더명:

| 파서                                 | 하위폴더                                                                   |
| ------------------------------------ | -------------------------------------------------------------------------- |
| cyntec                               | `CYNTEC`                                                                   |
| infineon                             | `infineon`                                                                 |
| kemet                                | `kemet`                                                                    |
| kyocera/CM, CT, CX                   | `kyocera_CM`, `kyocera_CT`, `kyocera_CX`                                   |
| murata/GJM, GRM(A), GRM(B), LQP, NCP | `murata_GJM`, `murata_GRM(A)`, `murata_GRM(B)`, `murata_LQP`, `murata_NCP` |

---

## 실행 방법

### 의존성

- Python 3.13+
- `wxPython` — GUI 프레임워크
- `PyMuPDF (fitz)` — PDF 파싱 (miniconda3 환경에 설치되어도 자동 탐지)

```bash
pip install wxpython
conda install -c conda-forge pymupdf
```

### GUI 실행

```bash
python app.py
```

---

## 사용 방법

1. **파서 선택** — SELECTION 체크리스트에서 `(Maker / Model)` 쌍을 하나 이상 체크
   - 검색창으로 빠르게 필터링
   - `전체 선택` / `전체 해제` 일괄 조작
2. **Input 폴더** — 위 규칙에 따라 브랜드 하위폴더로 구성된 상위 디렉토리를 지정
3. **Output 폴더** — CSV 저장 위치 확인/변경
4. **EXTRACTION 실행** — 선택된 파서를 순차 실행
   - 각 파서는 자기 브랜드 하위폴더만 봄 → 메이커 간 교차 오염 없음
   - 다중 선택 시 `compiled_output.csv` 자동 생성
   - 일부 파서 실패해도 나머지는 계속 진행
   - 실행 종료 시 비매칭 항목 경고 로그 표시
     - `(info) skipped subfolders (parser not selected)` — 알려진 폴더지만 미선택
     - `WARNING: unknown subfolders` — 어느 파서에도 매칭 안 됨
     - `WARNING: N PDF(s) at top level were ignored` — 하위폴더 밖 PDF
5. **COMPILATION 실행** — **직전 EXTRACTION 결과만** 하나의 CSV로 통합 (Output 폴더 전체 스캔 아님)
6. **Parser 추가** — 외부 `.py` 파일을 선택하면 `parsers/`로 복사 + 즉시 등록

> 상태바 우측에 `선택: N개 파서` 가 실시간 표시됩니다.

---

## 변경 이력

### v2.1 — 브랜드 폴더 라우팅 / 결과 격리 / 안전성 개선

- **브랜드 하위폴더 라우팅** (`parsers/base.py`): `LegacyScriptParser.parse`가 `input_dir` 전체가 아닌 `input_dir/<self.input_folder>/` 만 작업폴더로 링크. 다중 파서 동시 실행 시 메이커 간 PDF 교차 파싱 차단.
- **비매칭 항목 경고** (`app.py`): 실행 후 unknown 하위폴더 / 미선택 파서 폴더 / top-level PDF 를 로그에 표시.
- **COMPILATION 동작 변경**: Output 폴더의 모든 CSV가 아니라 **직전 EXTRACTION 결과**만 합침 (`self.last_extraction_items`).
- **`fitz_isolation()` 컨텍스트 매니저** (`parsers/base.py`): BaseParser 직접 상속 파서들이 `with fitz_isolation(): import fitz` 패턴으로 venv의 깨진 fitz 패키지를 우회하고 conda PyMuPDF를 우선 로드.
- **macOS wxPython 4.2.5 회피**: 통합 CSV 저장 다이얼로그의 wildcard에 `All files (*.*)` 항목 추가 — wxArrayString index out of bounds 에러 방지.
- **`_refresh_default_input` 비활성화**: 새 라우팅 규칙과 안 맞는 자동 입력 로직 제거. 사용자가 input 폴더를 명시 지정.
- **샘플 업로드 파일** (`samples/infineon_v2.py`): `Parser 추가` 등록 흐름 테스트용 BaseParser 단일파일 예시.
- **테스트 데이터 재배치** (`test_input_pdf/`): 평면 구조 → 브랜드별 12개 하위폴더로 정렬.

### v2.0 — 다중 선택 / 자동 통합 / 파서 업로드

- SELECTION 영역 재설계: 드롭다운 → `(Maker / Model)` 체크리스트 (`wx.CheckListBox` + `SearchCtrl`)
- 다중 파서 동시 실행 + `compiled_output.csv` 자동 통합
- `Parser 추가` 버튼으로 런타임 파서 동적 등록 (`reload_registry()`)

---

## 파서 추가 방법

`Parser 추가` 버튼은 선택한 `.py` 파일을 `parsers/` 폴더로 복사한 뒤 `reload_registry()` 로 등록합니다. 두 가지 방식이 있습니다.

> 방식 B 의 자세한 컨벤션·템플릿·체크리스트는 [`docs/PARSER_DEVELOPMENT.md`](docs/PARSER_DEVELOPMENT.md) 참고.

### 방식 A — `LegacyScriptParser` (기존 파싱 스크립트 재활용)

`UI자료/<scriptname>.py` 가 이미 있을 때 사용. 5줄짜리 래퍼만 작성.

```python
# parsers/newmaker_modelx.py
from .base import LegacyScriptParser

class NewmakerModelxParser(LegacyScriptParser):
    maker = "newmaker"
    model = "ModelX"
    script_name = "newmaker_ModelX.py"          # UI자료/ 내 파일명
    input_folder = "newmaker_ModelX"            # input/ 하위폴더 이름
    legacy_output_csv = "newmaker_ModelX_output.csv"
```

레거시 스크립트가 따라야 할 규칙:

- 상대경로만 사용 (`./newmaker_ModelX/*.pdf` → `./output/*.csv`).
- 출력 CSV 컬럼은 `pdfname`/`Filename`, `PartNumber`/`Part Number`/`ESD Line`, `L`, `W`, `T` 중 별칭 매칭 가능한 이름.
- `print()` 로 진행 로그 출력 (stdout이 GUI 로그창으로 리다이렉트됨).

업로드 시 GUI는 `parsers/` 의 래퍼만 복사하므로, **`UI자료/<script_name>` 은 별도로 수동 배치**해야 합니다.

### 방식 B — `BaseParser` 직접 상속 (단일 파일, 권장)

레거시 스크립트 없이 한 파일로 완결.

```python
# parsers/newmaker_modely.py
from pathlib import Path
from .base import BaseParser, fitz_isolation

class NewmakerModelyParser(BaseParser):
    maker = "newmaker"
    model = "ModelY"
    input_folder = "newmaker_ModelY"   # input/ 하위폴더 이름

    def parse(self, input_dir: Path) -> list[dict[str, str]]:
        brand_dir = input_dir / self.input_folder
        if not brand_dir.is_dir():
            raise FileNotFoundError(f"Subfolder not found: {brand_dir}")

        rows = []
        with fitz_isolation():
            import fitz
            for pdf in sorted(brand_dir.glob("*.pdf")):
                self.emit(f">   processing {pdf.name}")
                with fitz.open(pdf) as doc:
                    # ... 추출 로직 ...
                    rows.append({
                        "pdfname": pdf.name,
                        "PartNumber": "...",
                        "L": "...", "W": "...", "T": "...",
                    })
        return rows
```

방식 B 규칙:

- 클래스 속성 `maker`, `model` 정의. `input_folder` 는 본인이 직접 사용할 라우팅 키.
- `parse(self, input_dir: Path) -> list[dict[str, str]]` 구현. 표준 5컬럼(`pdfname`, `PartNumber`, `L`, `W`, `T`) dict 리스트 반환.
- 로그는 `self.emit(...)` 사용 (`print` 는 GUI로 안 흐름).
- fitz 사용 시 반드시 `with fitz_isolation(): import fitz` 패턴.
- 예외는 그대로 raise — 워커가 잡아 다른 파서 진행을 막지 않음.

### 공통 등록 조건

- `(maker, model)` 페어가 기존 REGISTRY와 중복되면 안 됨 (`ValueError`).
- 클래스는 그 모듈에서 직접 정의되어야 함 (`obj.__module__ == module.__name__` 체크).
- `parsers/` 안의 단일 `.py` 파일 (서브패키지 X).

### 업로드 흐름 검증

`samples/infineon_v2.py` 를 `Parser 추가` 로 업로드하면:

1. `parsers/infineon_v2.py` 로 복사
2. `reload_registry()` 가 `('infineon', 'v2')` 발견 → 등록
3. 체크리스트에 `infineon / v2` 추가 + 자동 체크
4. `EXTRACTION 실행` → `infineon_v2_output.csv` 생성

기존 `infineon / default` 와 페어가 다르므로 충돌하지 않음.

---

## 테스트

```bash
python -m pytest tests/ -v
```

| 테스트 파일        | 내용                                       |
| ------------------ | ------------------------------------------ |
| `test_registry.py` | REGISTRY 자동 등록, maker/model 목록 검증  |
| `test_base.py`     | BaseParser 인터페이스, 필수 속성 강제 검증 |
| `test_cyntec.py`   | CyntecParser 입력 검증                     |

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

- **다중 모델**: `app.py._run_parser_worker` 가 워커 스레드에서 선택된 파서를 순차 호출. 다중 선택 시 결과를 `self.last_extraction_items` 에 저장하여 COMPILATION 이 그 결과만 통합.
- **다중 파일**:
  - `LegacyScriptParser`: 임시 작업폴더에 `input_dir/<input_folder>/` 만 심볼릭 링크 → 레거시 스크립트가 자체 루프로 PDF 순회 → CSV 출력 → 표준 5컬럼으로 정규화.
  - `BaseParser`: `parse(input_dir)` 안에서 직접 `brand_dir.glob("*.pdf")` 순회 → 메모리 dict 리스트 반환.
- **fitz 격리**: `_find_fitz_site_packages()` 가 conda 경로를 동적 탐지. `LegacyScriptParser` 는 `runpy.run_path` 직전에, `BaseParser` 는 `fitz_isolation()` 컨텍스트로 sys.path/sys.modules 격리.
- **REGISTRY 동적 등록**: `parsers/__init__.py` 의 `pkgutil.iter_modules` 로 패키지 스캔. `reload_registry()` 는 `sys.modules` 에 없는 새 모듈만 import 하여 등록.
- **stdout 리다이렉트**: `_LogStream` 이 레거시 스크립트의 `print()` 를 GUI 로그창으로 한 줄씩 흘려보냄.
