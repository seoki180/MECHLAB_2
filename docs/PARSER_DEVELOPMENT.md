# 파서 개발 가이드 — 방식 B (`BaseParser`)

이 문서는 새 파서를 **단일 `.py` 파일로 처음부터 작성**할 때 따라야 할 컨벤션을 정리합니다. 레거시 스크립트(`UI자료/*.py`)를 재활용하는 방식 A는 README 의 [파서 추가 방법](../README.md#파서-추가-방법) 섹션을 참고하세요.

> **방식 B 를 권장하는 이유**: 단일 파일로 자기완결, 임시폴더/runpy 격리 비용 없음, 디버깅·로깅·테스트가 쉬움.

---

## 1. 파일·디렉토리 컨벤션

### 1.1 파일 위치

- **개발 중**: `samples/<filename>.py` — 작성·검증 단계에서는 여기 둠. `parsers/` 의 자동 import 영향 없음.
- **배포(GUI 업로드)**: 사용자가 `Parser 추가` 버튼으로 선택하면 `parsers/<filename>.py` 로 복사됨.
- **개발자가 직접 배치**: `parsers/<filename>.py` 에 두면 다음 앱 실행 시 자동 등록.

### 1.2 파일명 규칙

```
parsers/<maker>_<model>.py
```

- 모두 **소문자 + underscore**.
- `maker` 와 `model` 클래스 속성 값을 그대로 사용 (특수문자는 underscore로 치환).
- 한 파일에 한 파서 클래스만 담을 것 (REGISTRY 스캔이 모듈명 기준).

| `maker`    | `model`   | 파일명                                            |
| ---------- | --------- | ------------------------------------------------- |
| `infineon` | `default` | `parsers/infineon.py` (model이 default면 maker만) |
| `infineon` | `v2`      | `parsers/infineon_v2.py`                          |
| `acme`     | `ESD-Pro` | `parsers/acme_esd_pro.py`                         |
| `kyocera`  | `CM`      | `parsers/kyocera_cm.py`                           |

### 1.3 클래스명 규칙

```python
class <Maker><Model>Parser(BaseParser):
    ...
```

- PascalCase, 끝에 `Parser` 접미사.
- `__init_subclass__` 가 강제하지는 않지만 일관성을 위해 따를 것.

| 파일                      | 클래스명           |
| ------------------------- | ------------------ |
| `parsers/infineon.py`     | `InfineonParser`   |
| `parsers/infineon_v2.py`  | `InfineonV2Parser` |
| `parsers/acme_esd_pro.py` | `AcmeEsdProParser` |
| `parsers/kyocera_cm.py`   | `KyoceraCmParser`  |

---

## 2. 클래스 구조 컨벤션

### 2.1 필수 클래스 속성

| 속성           | 타입  | 역할                                                                                                                   |
| -------------- | ----- | ---------------------------------------------------------------------------------------------------------------------- |
| `maker`        | `str` | REGISTRY 키의 첫 번째 요소. 메이커명 (소문자 권장).                                                                    |
| `model`        | `str` | REGISTRY 키의 두 번째 요소. 시리즈/모델명.                                                                             |
| `input_folder` | `str` | 사용자 input 디렉토리 아래의 브랜드 하위폴더명. **반드시** 정의할 것 (BaseParser는 강제 안 하지만 라우팅 규칙상 필수). |

### 2.2 선택 클래스 속성 (관례)

상수는 클래스 속성으로 묶어서 정의. 인스턴스 변수로 두지 말 것.

```python
class AcmeXParser(BaseParser):
    maker = "acme"
    model = "X"
    input_folder = "acme_X"

    # 추출 영역 (PDF 좌표 bbox)
    DIM_BBOX = (42, 164, 550, 289)
    # 토큰 매칭 허용 오차 (pt)
    TOLERANCE = 10
    # 첫 페이지에서 메이커 식별 키워드
    MAKER_SIGNATURE = "Acme Semiconductor"
```

### 2.3 `parse()` 메서드 시그니처 — 고정

```python
def parse(self, input_dir: Path) -> list[dict[str, str]]:
```

- 인자 1개 (`input_dir`), 반환 타입 고정. 변경 금지.
- 반환 dict 의 키는 표준 5개:

```python
{"pdfname": str, "PartNumber": str, "L": str, "W": str, "T": str}
```

값이 없으면 빈 문자열 `""`. `None` 이나 키 누락 금지.

---

## 3. 표준 템플릿

새 파서는 항상 이 형태에서 출발할 것.

```python
# parsers/<maker>_<model>.py
from __future__ import annotations

from pathlib import Path

from .base import BaseParser, fitz_isolation


class AcmeXParser(BaseParser):
    maker = "acme"
    model = "X"
    input_folder = "acme_X"

    # ── 클래스 상수 ─────────────────────────────────────────────
    DIM_BBOX = (42, 164, 550, 289)
    TOLERANCE = 10

    # ── 진입점 ─────────────────────────────────────────────────
    def parse(self, input_dir: Path) -> list[dict[str, str]]:
        input_dir = Path(input_dir).expanduser().resolve()
        if not input_dir.is_dir():
            raise FileNotFoundError(f"Input folder not found: {input_dir}")

        brand_dir = input_dir / self.input_folder
        if not brand_dir.is_dir():
            raise FileNotFoundError(
                f"Expected brand subfolder not found: {brand_dir}\n"
                f"Place {self.maker}/{self.model} PDFs under '{self.input_folder}/' "
                f"inside the input directory."
            )

        pdf_files = sorted(p for p in brand_dir.iterdir() if p.suffix.lower() == ".pdf")
        if not pdf_files:
            self.emit(f">   (warning) {brand_dir} contains no PDFs")
            return []

        rows: list[dict[str, str]] = []
        with fitz_isolation():
            import fitz
            for pdf_path in pdf_files:
                self.emit(f">   processing {pdf_path.name}")
                try:
                    rows.append(self._extract_one(pdf_path, fitz))
                except Exception as exc:
                    self.emit(f">   ! failed {pdf_path.name}: {exc}")
                    rows.append(self._empty_row(pdf_path.name))
        return rows

    # ── 단일 PDF 추출 ──────────────────────────────────────────
    def _extract_one(self, pdf_path: Path, fitz) -> dict[str, str]:
        with fitz.open(pdf_path) as doc:
            part_number = self._find_part_number(doc)
            L, W, T = self._extract_dimensions(doc)
        return {
            "pdfname": pdf_path.name,
            "PartNumber": part_number,
            "L": L,
            "W": W,
            "T": T,
        }

    # ── 헬퍼 ───────────────────────────────────────────────────
    @staticmethod
    def _find_part_number(doc) -> str:
        for page in doc:
            for line in page.get_text().splitlines():
                # ... 추출 로직 ...
                pass
        return ""

    def _extract_dimensions(self, doc) -> tuple[str, str, str]:
        # ... L, W, T 추출 ...
        return ("", "", "")

    @staticmethod
    def _empty_row(filename: str) -> dict[str, str]:
        return {"pdfname": filename, "PartNumber": "", "L": "", "W": "", "T": ""}
```

---

## 4. 코드 컨벤션 세부

### 4.1 fitz import 패턴 — 반드시 lazy

```python
# ❌ 절대 금지 — 모듈 top-level 에서 import
import fitz

# ❌ 격리 없이 import
def parse(self, input_dir):
    import fitz
    ...

# ✅ 올바른 패턴
def parse(self, input_dir):
    ...
    with fitz_isolation():
        import fitz
        for pdf in ...:
            with fitz.open(pdf) as doc:
                ...
```

**이유**: venv 에 `pip install fitz` 로 들어간 잘못된 fitz 패키지가 있으면 top-level import 가 실패한다. `fitz_isolation()` 이 sys.path/sys.modules 를 격리해 conda PyMuPDF 를 우선 로드해줌. fitz 객체는 `with` 블록 안에서만 유효하므로, `_extract_one(pdf, fitz)` 처럼 인자로 전달.

### 4.2 입력 폴더 검증 — 표준 패턴

`parse()` 시작부에 항상 다음 3단계.

```python
input_dir = Path(input_dir).expanduser().resolve()
if not input_dir.is_dir():
    raise FileNotFoundError(f"Input folder not found: {input_dir}")

brand_dir = input_dir / self.input_folder
if not brand_dir.is_dir():
    raise FileNotFoundError(
        f"Expected brand subfolder not found: {brand_dir}\n"
        f"Place {self.maker}/{self.model} PDFs under '{self.input_folder}/' "
        f"inside the input directory."
    )

pdf_files = sorted(p for p in brand_dir.iterdir() if p.suffix.lower() == ".pdf")
if not pdf_files:
    self.emit(f">   (warning) {brand_dir} contains no PDFs")
    return []
```

- `expanduser()` + `resolve()` 로 절대경로화.
- `iterdir()` + `suffix.lower()` 로 `.pdf`/`.PDF` 모두 인식.
- `sorted()` 로 결정적 순서 보장 (테스트 안정성).

### 4.3 로깅 — `self.emit()` 만 사용

```python
# ❌ print 는 GUI 로그창에 안 흐름
print(f"processing {pdf}")

# ✅
self.emit(f">   processing {pdf}")
```

- prefix `>` 와 들여쓰기로 다른 로그와 시각적 구분 (`>   processing ...`).
- 로그 레벨 개념 없음 — 모든 줄이 동일하게 GUI 로그창에 표시됨.
- 진행 상황은 PDF 단위로만 한 줄. PDF 안의 세부 단계 로그는 디버깅 시에만 임시로.

### 4.4 에러 처리 — PDF 단위 격리

한 PDF 가 실패해도 나머지는 계속 처리.

```python
for pdf_path in pdf_files:
    try:
        rows.append(self._extract_one(pdf_path, fitz))
    except Exception as exc:
        self.emit(f">   ! failed {pdf_path.name}: {exc}")
        rows.append(self._empty_row(pdf_path.name))
```

- 빈 행을 추가해 PDF 와 출력 행의 1:1 대응 유지.
- 폴더 누락처럼 **루프 진입 자체가 불가능한 경우는 raise** — `app.py` 워커가 잡아 다른 파서로 진행.

### 4.5 PDF 내용 검증 — 권장

브랜드 폴더 라우팅이 1차 방어선이지만, PDF 가 진짜 자기 메이커 것인지 확인하는 2차 검증 추가 권장.

```python
def _is_my_pdf(self, doc) -> bool:
    first_page_text = doc[0].get_text().lower()
    return self.MAKER_SIGNATURE.lower() in first_page_text

def _extract_one(self, pdf_path: Path, fitz) -> dict[str, str]:
    with fitz.open(pdf_path) as doc:
        if not self._is_my_pdf(doc):
            self.emit(f">   ? skipping {pdf_path.name} (not a {self.maker} datasheet)")
            return self._empty_row(pdf_path.name)
        ...
```

### 4.6 헬퍼 함수 — 작은 단위로 분리

`parse()` 한 메서드 안에 모든 로직 넣지 말 것. 다음 단위로 분리:

| 메서드                               | 역할                                    |
| ------------------------------------ | --------------------------------------- |
| `parse(self, input_dir)`             | 폴더 검증 + 루프 + 격리 (위 템플릿대로) |
| `_extract_one(self, pdf_path, fitz)` | 1개 PDF → 1개 행                        |
| `_find_part_number(doc)`             | PartNumber 추출                         |
| `_extract_dimensions(doc)`           | L/W/T 추출                              |
| `_find_dimension_page(doc)`          | 치수가 있는 페이지 찾기                 |
| `_empty_row(filename)`               | 실패 시 빈 행 생성                      |

### 4.7 타입 힌트

- `from __future__ import annotations` 를 파일 첫 줄에 (PEP 563 forward refs).
- `parse()` 시그니처에 명시적 타입 (`Path`, `list[dict[str, str]]`).
- 헬퍼는 가능하면 타입 힌트, 외부 라이브러리 객체(fitz Document, Page)는 생략 OK.
- `tuple[float, ...]` 같은 모던 syntax 사용 (Python 3.13+).

### 4.8 모듈 top-level 코드 금지

```python
# ❌ 모듈 import 시 실행되면 안 됨
print("loading parser")
DATA = json.load(open("config.json"))

# ✅ 클래스 안에 두거나 클래스 상수로
class AcmeXParser(BaseParser):
    DEFAULT_CONFIG = {"tolerance": 10}
```

이유: `parsers/__init__.py` 가 패키지 import 시 모든 파서 모듈을 자동 로드한다. side-effect 가 있으면 GUI 시작이 느려지거나 깨짐.

---

## 5. 의존성 컨벤션

| 라이브러리                                            | 사용 가능 여부                                                           |
| ----------------------------------------------------- | ------------------------------------------------------------------------ |
| `fitz` (PyMuPDF)                                      | ✅ — `fitz_isolation()` 안에서 lazy import                               |
| 표준 라이브러리 (`pathlib`, `re`, `csv`, `json`, ...) | ✅                                                                       |
| `parsers.base` 의 `BaseParser`, `fitz_isolation`      | ✅                                                                       |
| `pandas`, `numpy`, `pdfplumber`, `pytesseract` 등     | ⚠️ venv 에 직접 설치 필요. 추가 시 `pyproject.toml` 도 업데이트.         |
| GUI 코드 (`wx.*`)                                     | ❌ 절대 금지 — 파서는 headless 동작해야 함                               |
| 다른 `parsers/*` 모듈                                 | ❌ 금지 — REGISTRY 등록 시 `obj.__module__ == module.__name__` 검사 깨짐 |

---

## 6. 출력 컨벤션

### 6.1 표준 5컬럼

```python
{"pdfname": "...", "PartNumber": "...", "L": "...", "W": "...", "T": "..."}
```

- 모두 `str`. 숫자도 문자열로 (예: `"0.43±0.03"`).
- 없는 값은 `""` (빈 문자열). `None`, `0`, `"N/A"` 사용 금지.
- 추가 키를 dict 에 넣어도 `write_csv` 가 무시하지만, 컴파일 단계에서 누락되므로 **표준 5개 외 키는 의미 없음**.

### 6.2 값 포맷 권장

| 컬럼            | 포맷 예시                                             |
| --------------- | ----------------------------------------------------- |
| `pdfname`       | `"infineon_test_1.pdf"` (원본 파일명 그대로)          |
| `PartNumber`    | `"ESD128-B1-W0201"` (메이커 표기 그대로)              |
| `L` / `W` / `T` | `"0.58±0.03"` 또는 `"0.58"` (단위 mm, 단위 표기 생략) |

### 6.3 행과 PDF 의 대응

- **PDF 1개 → 행 1개** (성공/실패 무관).
- 한 PDF 가 여러 부품 정보를 담고 있어도 행 1개로 합치거나, 가장 대표적인 값 1개만 추출.
- 한 PDF 에서 여러 행을 뽑아야 하는 케이스가 생기면 별도 모델로 분리(`maker="acme", model="X-multi"`)하거나 표준 컬럼 확장을 별도 의논.

---

## 7. 등록 체크리스트

업로드 또는 `parsers/` 배치 전에 다음을 확인.

- [ ] 파일 위치: `parsers/<maker>_<model>.py` (또는 `samples/` 에서 검증 후 이동)
- [ ] `from .base import BaseParser, fitz_isolation` 임포트
- [ ] 클래스가 `BaseParser` 직접 상속
- [ ] 클래스 속성 `maker`, `model`, `input_folder` 정의
- [ ] `(maker, model)` 페어가 기존 REGISTRY 와 충돌하지 않음
- [ ] `parse(self, input_dir: Path) -> list[dict[str, str]]` 시그니처 준수
- [ ] 표준 5컬럼 dict 반환 (빈 값은 `""`)
- [ ] fitz 는 `with fitz_isolation(): import fitz` 안에서만
- [ ] 입력 폴더 검증 3단계 적용 (input_dir → brand_dir → pdf_files)
- [ ] 로그는 `self.emit()` 사용
- [ ] PDF 단위 try/except 로 실패 격리
- [ ] 모듈 top-level 에 side-effect 없음
- [ ] 다른 `parsers/*` 모듈 import 안 함

---

## 8. 검증 방법

### 8.1 로컬 단위 테스트 (GUI 없이)

```python
from pathlib import Path
from parsers import REGISTRY, get_parser

# REGISTRY 등록 확인
assert ("acme", "X") in REGISTRY

# parse() 직접 호출
parser = get_parser("acme", "X", log=print)
rows = parser.parse(Path("test_input_pdf"))

# 반환 형태 검증
assert isinstance(rows, list)
assert all(set(r.keys()) >= {"pdfname", "PartNumber", "L", "W", "T"} for r in rows)
print(f"{len(rows)} rows OK")
```

### 8.2 GUI 통합 테스트

1. `python app.py` 실행
2. 체크리스트에 `acme / X` 노출 확인 (없으면 등록 실패)
3. Input 폴더 = 상위 디렉토리 (그 안에 `acme_X/` 하위폴더 + 샘플 PDF 배치)
4. EXTRACTION 실행
5. 로그에 PDF 처리 메시지 + CSV 생성 확인
6. 다른 파서와 함께 다중 선택 → 교차 오염 없는지 확인

### 8.3 회귀 테스트 (선택)

`tests/test_<parser_name>.py` 추가.

```python
import tempfile
from pathlib import Path
from parsers import get_parser

def test_acme_x_extraction():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "acme_X").mkdir()
        # ... 샘플 PDF 복사 ...

        parser = get_parser("acme", "X")
        rows = parser.parse(root)

        assert len(rows) > 0
        assert all("pdfname" in r for r in rows)
        assert all(r["pdfname"].endswith(".pdf") for r in rows)
```

---

## 9. 자주 하는 실수

| 실수                                             | 결과                                            | 해결                                      |
| ------------------------------------------------ | ----------------------------------------------- | ----------------------------------------- |
| `import fitz` 를 모듈 top-level                  | venv 의 깨진 fitz 로 import 실패                | `with fitz_isolation(): import fitz`      |
| `input_folder` 미정의                            | brand 라우팅 못 함                              | 클래스 속성으로 정의                      |
| `input_folder` 값과 실제 폴더명 대소문자 불일치  | Linux/case-sensitive FS 에서 FileNotFoundError  | 정확히 일치시키기                         |
| dict 키 누락 또는 `None` 값                      | CSV writer 에서 빈칸/에러                       | 표준 5키 항상 모두 포함, 빈 값은 `""`     |
| `(maker, model)` 페어 중복                       | `ValueError: Duplicate parser registration`     | model 이름 변경 (예: `default` → `v2`)    |
| 다른 `parsers/*` 모듈 import                     | 등록 실패 (`obj.__module__ != module.__name__`) | 공통 코드는 `base.py` 또는 모듈 내 헬퍼로 |
| 모듈 top-level 에서 큰 파일 로드 / 네트워크 호출 | GUI 시작 지연 또는 실패                         | 클래스 속성으로 늦은 초기화               |
| `print()` 로 진행 로그                           | GUI 로그창에 안 보임                            | `self.emit()`                             |
| PDF 1개 실패 시 raise → 전체 중단                | 다른 PDF 미처리                                 | PDF 단위 try/except + 빈 행 추가          |

---

## 10. 참고 — `samples/infineon_v2.py`

방식 B 의 **완성 예시**. 위 컨벤션을 모두 따르며, 실제 PDF 6개를 처리하는 동작 검증 완료.

직접 열어 패턴을 확인하거나, 새 파서의 출발점으로 복사해서 사용하세요.

```bash
cp samples/infineon_v2.py samples/acme_x.py
# maker, model, input_folder 변경
# 추출 로직 재작성
# 검증 후 GUI Parser 추가 또는 parsers/ 직접 배치
```

---

## 부록 — `BaseParser` API 요약

| 멤버                    | 시그니처                         | 설명                                                      |
| ----------------------- | -------------------------------- | --------------------------------------------------------- |
| `maker`                 | `str` (class attr)               | 필수                                                      |
| `model`                 | `str` (class attr)               | 필수                                                      |
| `input_folder`          | `str` (class attr)               | 컨벤션상 필수 (라우팅 키)                                 |
| `__init__(log=None)`    | `(LogCallback \| None)`          | 기본 구현 사용. 오버라이드 비권장                         |
| `parse(input_dir)`      | `(Path) -> list[dict[str, str]]` | **추상 메서드 — 반드시 구현**                             |
| `emit(message)`         | `(str) -> None`                  | 로그 출력 헬퍼. `self.log` 가 있을 때만 호출              |
| `output_csv_name`       | `str` (property)                 | 자동: `"{maker}_{model}_output.csv"`                      |
| `write_csv(rows, path)` | `(list, Path) -> None`           | 표준 5컬럼으로 CSV 저장. 직접 호출 X — `app.py` 가 호출함 |

| 헬퍼 (`parsers.base`) | 용도                                            |
| --------------------- | ----------------------------------------------- |
| `fitz_isolation()`    | fitz import 격리 컨텍스트 매니저                |
| `STANDARD_COLUMNS`    | `["pdfname", "PartNumber", "L", "W", "T"]` 상수 |
