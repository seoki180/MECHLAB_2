# MECHLab - 반도체 데이터시트 파서 UI 개발 계획

## 프로젝트 개요

반도체 제조사의 PDF 데이터시트에서 **Part Number**와 **부품 치수(L/W/T)**를 자동 추출하는 파이썬 스크립트들을 하나의 **GUI 애플리케이션**으로 통합한다.

---

## 현황 정리

### 처리 대상 데이터

| 제조사 | 모델 | 스크립트 | CSV 출력 행 수 | 파싱 방식 |
|--------|------|----------|----------------|-----------|
| Cyntec | - | `cyntec.py` | 45행 | fitz 텍스트 좌표 매칭 |
| Infineon | - | `infineon.py` | 6행 | fitz bounding box 하드코딩 |
| Kemet | - | `kemet.py` | 22행 | fitz 텍스트 병합 |
| Kyocera | CM | `kyocera_CM.py` | 12행 | fitz |
| Kyocera | CT | `kyocera_CT.py` | 3행 | fitz |
| Kyocera | CX | `kyocera_CX.py` | 5행 | fitz |
| Murata | GJM | `murata_GJM.py` | 16행 | fitz |
| Murata | GRM(A) | `murata_GRM(A).py` | 58행 | fitz |
| Murata | GRM(B) | `murata_GRM(B).py` | 5행 | fitz |
| Murata | LQP | `murata_LQP.py` | 29행 | fitz + OpenCV + Tesseract OCR |
| Murata | NCP | `murata_NCP.py` | 5행 | fitz |

### 현재 문제점

1. **스크립트 분산**: 제조사/모델별로 개별 `.py` 파일이 존재, 통합 실행 불가
2. **경로 불일치**: 일부는 Windows 경로(`.\infineon`), 일부는 Unix 경로(`./CYNTEC`) 사용
3. **출력 컬럼 불일치**: Infineon만 `ESD Line`, `Top+Bottom View Page` 컬럼이 추가로 있음
4. **Part Number 품질 문제**: `murata_LQP`에서 OCR 오인식으로 `#'#` 같은 노이즈 포함
5. **하드코딩된 경로**: 각 스크립트 상단에 경로가 고정되어 있어 재사용 어려움
6. **Windows 종속성**: `murata_LQP.py`의 Tesseract 경로가 `C:\Program Files\...` 하드코딩

---

## UI 설계 (hwpx 문서 기반)

```
┌─────────────────────────────────────────────────────────────┐
│  [SELECTION]  Maker: [드롭다운▼]   Model: [드롭다운▼]       │
│  [FILE]       Input 폴더: [___________________] [Browse]    │
│               Output 경로: [__________________] [Browse]    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   [EXTRACTION 실행]        [COMPILATION 실행]               │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  실행 로그 (스크롤)                                          │
│  > Processing: example.pdf ...                              │
│  > Done. 45 rows saved.                                     │
│                                               Maker: Cyntec │
│                                               Model: -      │
└─────────────────────────────────────────────────────────────┘
```

### 핵심 기능

- **SELECTION**: `maker.txt` / `model.txt` 외부 파일에서 목록 로드
- **EXTRACTION**: 선택한 Maker/Model에 해당하는 파싱 스크립트 실행
- **COMPILATION**: 모든 모델별 CSV를 하나의 파일로 통합
- **로그 창**: 실행 결과 실시간 출력 (scroll 가능)
- **상태 표시**: 우측 하단에 현재 선택된 Maker/Model 표시

---

## 작업 목록

### Phase 1 — 스크립트 정리 및 통합 (우선순위: 높음)

- [ ] **1-1. 공통 유틸 모듈 분리** (`utils.py`)
  - `center_x`, `center_y`, `clean_text` 등 모든 스크립트에 중복된 함수 통합
  - 경로를 인자로 받도록 각 스크립트 함수화 (`run(pdf_folder, output_path)`)

- [ ] **1-2. 경로 처리 통일**
  - 하드코딩된 경로 제거, `pathlib.Path` 사용으로 OS 무관하게 처리
  - Tesseract 경로를 환경변수 또는 설정 파일로 분리

- [ ] **1-3. 출력 포맷 통일**
  - 모든 CSV 컬럼을 `pdfname, PartNumber, L, W, T` 로 통일
  - Infineon의 `ESD Line` 등 제조사 고유 컬럼은 별도 처리 방식 결정

- [ ] **1-4. Part Number 품질 개선**
  - `murata_LQP` OCR 후처리 로직 개선 (`#'#` 노이즈 제거)
  - 빈 Part Number 행 처리 정책 결정 (유지 vs 제외)

### Phase 2 — GUI 개발 (우선순위: 높음)

- [ ] **2-1. 프레임워크 선택**
  - 권장: `tkinter` (기본 내장, 설치 불필요) 또는 `PyQt5/PySide6` (더 나은 UI)
  - 의사결정 필요

- [ ] **2-2. 기본 레이아웃 구현**
  - 툴바 영역 (SELECTION, FILE)
  - 버튼 영역 (EXTRACTION, COMPILATION)
  - 로그 출력 창 (ScrolledText)
  - 상태 표시 영역 (하단 우측)

- [ ] **2-3. Maker/Model 드롭다운 연동**
  - `maker.txt`, `model.txt` 파일 로드
  - Maker 선택 시 해당 Maker의 Model 목록만 필터링하여 표시

- [ ] **2-4. EXTRACTION 실행 연동**
  - 선택된 Maker/Model에 맞는 파싱 함수 호출
  - `subprocess` 또는 직접 import로 백그라운드 실행
  - 실행 로그를 로그 창에 실시간 출력 (threading 활용)

- [ ] **2-5. COMPILATION 기능 구현**
  - `output/` 폴더 내 모든 `*_output.csv` 파일을 하나로 병합
  - 저장 경로 및 파일명 지정 기능

- [ ] **2-6. 파일/폴더 선택 다이얼로그**
  - Input PDF 폴더 선택 (`filedialog.askdirectory`)
  - Output 저장 경로 선택

### Phase 3 — 설정 파일 및 확장성 (우선순위: 보통)

- [ ] **3-1. `maker.txt` / `model.txt` 작성**
  - 현재 지원 Maker 4개, Model 8개 기재
  - 추후 추가 가능하도록 포맷 정의

- [ ] **3-2. `config.json` 또는 `.ini` 도입**
  - Tesseract 경로, 기본 입출력 경로 등 설정값 외부화

- [ ] **3-3. 에러 핸들링 강화**
  - PDF 열기 실패, L/W/T 미발견, OCR 실패 시 로그에 명확히 표시
  - Skip된 파일 목록 별도 저장 옵션

### Phase 4 — 검증 및 마무리 (우선순위: 낮음)

- [ ] **4-1. 기존 CSV 출력과 비교 검증**
  - 리팩토링 후 결과가 기존 output과 동일한지 확인

- [ ] **4-2. 실행 환경 패키징**
  - `requirements.txt` 작성 (`pymupdf`, `opencv-python`, `pytesseract`)
  - 선택적: `PyInstaller`로 단일 실행파일(.exe) 빌드

---

## 기술 스택 (권장)

| 항목 | 권장 | 비고 |
|------|------|------|
| GUI | `tkinter` | 설치 불필요, 크로스플랫폼 |
| PDF 파싱 | `PyMuPDF (fitz)` | 현재 사용 중 |
| OCR | `pytesseract` + `opencv-python` | LQP 전용, Tesseract 설치 필요 |
| 데이터 출력 | `csv` (표준 라이브러리) | 현재 사용 중 |
| 경로 처리 | `pathlib` | OS 무관 |
| 비동기 실행 | `threading` | UI 블로킹 방지 |

---

## 파일 구조 (목표)

```
MECHLab/
├── main.py              # GUI 진입점
├── config.json          # 경로, 설정값
├── maker.txt            # Maker 목록
├── model.txt            # Model 목록 (maker별)
├── parsers/
│   ├── __init__.py
│   ├── utils.py         # 공통 함수
│   ├── cyntec.py
│   ├── infineon.py
│   ├── kemet.py
│   ├── kyocera_CM.py
│   ├── kyocera_CT.py
│   ├── kyocera_CX.py
│   ├── murata_GJM.py
│   ├── murata_GRM_A.py
│   ├── murata_GRM_B.py
│   ├── murata_LQP.py
│   └── murata_NCP.py
├── input/               # PDF 원본 폴더
│   ├── CYNTEC/
│   ├── infineon/
│   └── ...
└── output/              # CSV 결과 폴더
    ├── cyntec_output.csv
    └── ...
```

---

## 우선 착수 권장 작업

1. **Phase 2-1**: GUI 프레임워크 결정 → 기본 레이아웃 뼈대 구현
2. **Phase 1-1**: 각 파서 스크립트를 `run(pdf_folder, output_path)` 함수 형태로 리팩토링
3. **Phase 2-3 ~ 2-4**: 드롭다운 연동 + EXTRACTION 실행 연결
