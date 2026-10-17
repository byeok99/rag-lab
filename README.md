# TC RAG CLI

기존 테스트케이스(Test Case, TC) 파일을 파싱하고 검색 가능한 형태로 저장한 뒤, 관련 TC를 근거로 신규 TC 후보를 만드는 Python CLI MVP입니다.

이 도구는 기존 TC에서 확인할 수 없는 제품 동작이나 요구사항을 사실로 확정하지 않습니다. 근거가 부족한 후보는 `requires_confirmation=true`, `expected_result_basis=unknown`으로 저장하며 사람이 기대결과를 확인하기 전에는 승인할 수 없습니다. 웹 UI는 제공하지 않습니다.

## 1. 구현 범위

```text
TC 파일 → 파싱·정규화 → SQLite 저장 → 개발/평가 분리
       → 임베딩·색인 → 관련 TC 검색 → 조건 분석·후보 생성
       → 검증 → 사람 검토 → Excel/JSON/CSV 출력
```

구현된 기능:

- `.xls`, `.xlsx`, `.csv`, `.json` 입력
- 다중 행 Excel 헤더 탐지 및 기능 분류 병합 셀 복원
- 원본 시트·행 번호와 원문 보존
- TC_ID가 중복돼도 별도 레코드로 저장
- SQLite 기반 원본·후보·검토·실행 이력 관리
- 프로젝트·제품 버전 단위 검색 제한
- 평가용 TC를 검색에서 제외하는 holdout 분리
- 재현 가능한 로컬 해시 임베딩
- OpenAI 호환 임베딩 및 Responses API 연결
- 코사인 유사도 기반 Top-K 검색
- 보수적인 모의 LLM 후보 생성
- 후보 필드 및 근거 ID 검증
- 완전 중복과 의미 중복 의심 구분
- 후보 조회·수정·승인·반려·추가 확인 요청
- 검토용·승인본 `.xlsx`, JSON, CSV 출력
- Excel/CSV 수식 주입 방지
- 실행별 `run_id`, 설정, 결과, 성공·실패 기록

## 2. 핵심 원칙

### 원본과 생성 결과

- 입력 파일은 수정하거나 덮어쓰지 않습니다.
- `record_id`는 내부 고유 ID입니다.
- `original_tc_id`는 원본 TC_ID이며 중복될 수 있습니다.
- `generated_tc_id`는 생성 후보의 출력용 ID입니다.
- 원본 TC와 생성 TC는 `origin`으로 구분합니다.
- 생성 TC를 승인해도 시험 결과가 `P`로 바뀌지 않습니다.
- 생성 TC의 Excel H열과 I열은 항상 빈칸입니다.

### 근거가 부족한 기대결과

모의 LLM은 기존 TC만으로 확정할 수 없는 기대결과를 만들지 않습니다.

```json
{
  "expected_results": null,
  "expected_result_basis": "unknown",
  "requires_confirmation": true
}
```

이 상태의 후보를 승인하면 CLI가 거부합니다. 먼저 기대결과와 근거를 확인한 뒤 `review ... edit`으로 수정해야 합니다.

### 검색 점수

`score`는 코사인 유사도이며 내림차순입니다. 정답 확률이나 제품 동작의 신뢰도가 아닙니다.

## 3. 기술 구성

| 용도 | 구현 |
|---|---|
| CLI | Python `argparse` |
| 영속 저장소 | SQLite |
| 벡터 저장 | SQLite `vector_index` 테이블 |
| 로컬 임베딩 | 384차원 결정적 해시 벡터, 선택적 SentenceTransformer |
| 실제 임베딩 | OpenAI 호환 `/embeddings` API |
| 모의 LLM | 확인 필요 후보 생성기 |
| 실제 LLM | OpenAI 호환 `/responses` API |
| `.xlsx` | `openpyxl` |
| `.xls` | `xlrd` |

로컬 해시 임베딩은 서버 없이 전체 흐름을 검증하기 위한 구현입니다. 실제 의미 검색 품질을 보장하지 않습니다.

### 선택적 BGE-M3 로컬 임베딩

OpenAI API 없이 신경 임베딩을 비교하려면 선택적 의존성을 설치합니다.

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e '.[local-embedding]'
```

`embedding_provider: "local"`, `embedding_model: "BAAI/bge-m3"`를 평가 설정에 지정하면 문서와 질의를 같은 SentenceTransformer 모델로 임베딩합니다. 모델 차원은 로딩 후 실제 값과 설정을 검사하며, 모델을 다운로드할 수 없거나 캐시에 없으면 `not_run`으로 기록하고 Hash mock으로 대체하지 않습니다. `device: "auto"`는 CUDA, MPS, CPU 순으로 사용 가능 장치를 선택합니다.

Stage 7 비교 설정과 재현 절차는 다음 파일에 있습니다.

```bash
.venv/bin/python -m tc_rag.cli --db .tc-rag/tc-rag.db eval dry-run \
  --dataset examples/evaluation_cases.reviewed-v1.json \
  --config examples/evaluation_config.stage7-local-embedding-v2.json
```

`outputs/stage7-local-embedding-v2/`에는 실행 설정, 환경 메타데이터, 질문별 결과와 완료 보고서가 저장됩니다. 원본 TC와 모델 캐시는 저장소에 포함하지 않습니다.

## 4. 프로젝트 구조

```text
tc_rag/
  cli.py          CLI 명령과 실행 기록
  model.py        TC 데이터 모델과 임베딩 텍스트
  parsers.py      XLS/XLSX/CSV/JSON 파서
  storage.py      SQLite 스키마, 적재, 검토 이력
  providers.py    모의/실제 임베딩 및 LLM
  workflow.py     분리, 색인, 검색, 생성, 검증, 중복 검사
  exporters.py    XLSX/JSON/CSV 출력
tests/
  test_smoke.py   RAG 흐름 스모크 테스트
.tc-rag/
  tc-rag.db       기본 운영 데이터베이스
output/
  review.xlsx     검증 과정의 예제 출력
```

## 5. 설치

Python 3.11 이상을 사용합니다. 현재 검증 환경은 Python 3.12입니다.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e .
.venv\Scripts\tc-rag --help
```

테스트:

```powershell
.venv\Scripts\python -m pip install pytest
.venv\Scripts\python -m pytest -q
```

## 6. 모의 모드와 실제 API 모드

`--provider`는 임베딩, `--llm`은 생성 제공자를 선택합니다.

| 값 | 동작 |
|---|---|
| `mock` | 항상 로컬 임베딩 또는 모의 LLM 사용 |
| `openai` | 실제 API 사용, 키가 없으면 실패 |
| `auto` | API 키가 있으면 실제 API, 없으면 모의 모드 |

운영 기록을 명확히 하려면 `auto`보다 `mock` 또는 `openai`를 직접 지정하는 편이 좋습니다.

실제 API 설정은 프로젝트 루트의 `.env` 파일 또는 시스템 환경변수를 사용합니다. 예제 파일을 복사합니다.

```powershell
Copy-Item .env.example .env
```

`.env`에서 `OPENAI_API_KEY`를 실제 키로 교체합니다.

```dotenv
OPENAI_API_KEY=실제_API_키
OPENAI_BASE_URL=https://api.openai.com/v1
TC_RAG_EMBEDDING_MODEL=text-embedding-3-small
TC_RAG_EMBEDDING_DIMENSION=1536
TC_RAG_LLM_MODEL=gpt-4.1-mini
```

또는 현재 PowerShell 세션에 환경변수를 직접 설정할 수 있습니다.

```powershell
$env:OPENAI_API_KEY = "..."
$env:OPENAI_BASE_URL = "https://api.openai.com/v1"
$env:TC_RAG_EMBEDDING_MODEL = "text-embedding-3-small"
$env:TC_RAG_EMBEDDING_DIMENSION = "1536"
$env:TC_RAG_LLM_MODEL = "gpt-4.1-mini"
```

`OPENAI_BASE_URL`은 호환 API를 사용할 때만 변경합니다. API 키는 DB나 로그에 저장하지 않습니다.

CLI는 실행 시작 시 현재 작업 디렉터리의 `.env`를 자동으로 읽습니다. 이미 시스템 환경변수에 같은 키가 있으면 시스템 값을 우선하며 `.env`가 덮어쓰지 않습니다. `.env`는 `.gitignore`에 포함되어 있으므로 저장소에 커밋되지 않습니다.

## 7. 전체 실행 순서

아래 예시는 프로젝트 `demo`, 제품 버전 `1.0`을 사용합니다.

### 7.1 TC 파일 적재

```powershell
.venv\Scripts\tc-rag import "input.xls" `
  --project demo `
  --version 1.0
```

여러 파일:

```powershell
.venv\Scripts\tc-rag import "a.xls" "b.xlsx" "c.csv" `
  --project demo `
  --version 1.0
```

합성 자료:

```powershell
.venv\Scripts\tc-rag import "synthetic.json" `
  --project demo `
  --version 1.0 `
  --origin synthetic
```

같은 파일명·프로젝트·버전에 같은 내용의 파일을 재적재하면 `unchanged`입니다. 변경 파일은 삽입·갱신·삭제·식별 불명확 건수를 보고합니다.

### 7.2 개발용과 평가용 분리

```powershell
.venv\Scripts\tc-rag split `
  --project demo `
  --version 1.0 `
  --split-version split-v1 `
  --holdout 0.2 `
  --seed 42
```

- 약 20%를 평가용으로 숨깁니다.
- 동일하거나 표현이 매우 유사한 TC는 그룹 단위로 배치합니다.
- 평가용 TC는 해당 `split-version`을 사용한 색인에서 제외됩니다.
- 시드와 데이터가 같으면 분리를 재현할 수 있습니다.

### 7.3 임베딩 및 색인

로컬 모드:

```powershell
.venv\Scripts\tc-rag index `
  --project demo `
  --version 1.0 `
  --split-version split-v1 `
  --index-version index-v1 `
  --provider mock
```

실제 API:

```powershell
.venv\Scripts\tc-rag index `
  --project demo `
  --version 1.0 `
  --split-version split-v1 `
  --index-version openai-index-v1 `
  --provider openai
```

다른 임베딩 모델을 사용할 때는 새 `index-version`을 사용하십시오. 검색에서도 색인과 같은 제공자·모델·차원을 사용해야 합니다.

승인된 생성 TC를 명시적으로 포함하려면 다음 옵션을 추가합니다.

```powershell
--include-approved-generated
```

### 7.4 검색만 실행

```powershell
.venv\Scripts\tc-rag search "로그인 실패 후 재시도" `
  --project demo `
  --version 1.0 `
  --index-version index-v1 `
  --provider mock `
  --top-k 5
```

결과에는 내부 ID, 원본 TC_ID, 기능 분류, 시나리오, 입력과 절차, 기대결과, 코사인 유사도, 원본 파일·시트·행이 포함됩니다.

기본 검색은 같은 프로젝트와 제품 버전으로 제한됩니다. 교차 프로젝트 참고 검색은 다음과 같습니다.

```powershell
.venv\Scripts\tc-rag search "권한 없는 사용자 접근" `
  --project demo `
  --version 1.0 `
  --index-version index-v1 `
  --cross-project
```

교차 프로젝트 결과는 테스트 패턴 참고 자료일 뿐입니다. 다른 제품의 수치·정책·메뉴·기대결과를 대상 제품의 사실로 사용하면 안 됩니다.

### 7.5 조건 분석과 후보 생성

모의 LLM:

```powershell
.venv\Scripts\tc-rag generate "로그인 실패 후 재시도" `
  --conditions "일반 사용자, 비밀번호 오류 상태" `
  --project demo `
  --version 1.0 `
  --index-version index-v1 `
  --provider mock `
  --llm mock `
  --top-k 5
```

실제 API:

```powershell
.venv\Scripts\tc-rag generate "로그인 실패 후 재시도" `
  --conditions "일반 사용자, 비밀번호 오류 상태" `
  --project demo `
  --version 1.0 `
  --index-version openai-index-v1 `
  --provider openai `
  --llm openai `
  --top-k 5
```

생성 결과:

- 검색 근거 TC
- 기존 조건 분석
- 신규 TC 후보
- 근거 `record_id`
- 기존 TC와의 차이
- 가정과 검토자 질문
- 기대결과 근거 유형
- 확인 필요 여부
- 검증 실패 후보와 이유
- 처리 시간

모의 LLM은 제품 동작을 추정하지 않으므로 기대결과가 미확정인 후보를 생성합니다. 전체 흐름 검증용이며 생성 품질 비교용 모델이 아닙니다.

## 8. 후보 조회와 사람 검토

### 목록

```powershell
.venv\Scripts\tc-rag list `
  --project demo `
  --version 1.0 `
  --origin generated
```

상태 필터:

```powershell
.venv\Scripts\tc-rag list `
  --project demo `
  --version 1.0 `
  --origin generated `
  --status candidate
```

### 상세 조회

```powershell
.venv\Scripts\tc-rag show gen_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 수정

수정할 필드만 `patch.json`에 작성합니다.

```json
{
  "expected_results": "오류 메시지가 표시되고 로그인 상태가 유지되지 않는다.",
  "expected_result_basis": "existing_tc",
  "requires_confirmation": false,
  "reviewer_questions": []
}
```

```powershell
.venv\Scripts\tc-rag review gen_xxx edit `
  --reviewer "홍길동" `
  --reason "기대결과 근거 확인" `
  --patch patch.json
```

`record_id`, `origin`, `source_refs`는 수정할 수 없습니다. 수정 전후 값, 검토자, 이유, 시각이 기록됩니다.

### 승인

```powershell
.venv\Scripts\tc-rag review gen_xxx approve `
  --reviewer "홍길동" `
  --reason "기존 TC와 운영 정책에서 기대결과 확인"
```

다음 후보는 승인할 수 없습니다.

- 기대결과가 비어 있음
- `expected_result_basis=unknown`
- `requires_confirmation=true`
- 승인 이유가 비어 있음

승인은 시험 성공을 의미하지 않습니다.

### 반려와 추가 확인

```powershell
.venv\Scripts\tc-rag review gen_xxx reject `
  --reviewer "홍길동" `
  --reason "기존 TC와 완전 중복"

.venv\Scripts\tc-rag review gen_xxx request-confirmation `
  --reviewer "홍길동" `
  --reason "권한별 기대결과 확인 필요"
```

`needs-revision`도 사용할 수 있습니다.

## 9. 중복 검사

```powershell
.venv\Scripts\tc-rag duplicates gen_xxx
```

- `exact`: 정규화된 시나리오·입력/절차·기대결과가 동일
- `suspected_semantic`: 문자열 유사도가 높아 사람 확인 필요

유사도만으로 후보를 자동 삭제하지 않습니다. 입력, 권한, 상태 또는 기대결과가 다르면 별도 TC일 수 있습니다.

## 10. 결과 내보내기

내보내기는 생성 TC를 대상으로 합니다.

### 검토용 Excel

```powershell
.venv\Scripts\tc-rag export output\review.xlsx `
  --project demo `
  --version 1.0 `
  --mode review `
  --title "로그인 기능 테스트케이스 검토본" `
  --author "홍길동" `
  --reviewer "김검토"
```

### 승인본 Excel

```powershell
.venv\Scripts\tc-rag export output\approved.xlsx `
  --project demo `
  --version 1.0 `
  --mode approved `
  --title "로그인 기능 테스트케이스 승인본" `
  --author "홍길동" `
  --reviewer "김검토"
```

### JSON과 CSV

```powershell
.venv\Scripts\tc-rag export output\review.json `
  --project demo --version 1.0 --mode review

.venv\Scripts\tc-rag export output\review.csv `
  --project demo --version 1.0 --mode review
```

확장자로 형식을 판단하며 `--format xlsx|json|csv`로 명시할 수도 있습니다.

### Excel 열 매핑

| 열 | 내용 |
|---|---|
| A | 기능명 대분류 |
| B | 기능명 중분류 |
| C | 기능명 소분류 |
| D | 생성 TC_ID 또는 원본 TC_ID |
| E | 테스트 시나리오 |
| F | 사전조건, 입력, 번호가 있는 절차 |
| G | 기대 출력과 사후조건 |
| H | 생성 TC는 빈칸 |
| I | 생성 TC는 빈칸 |
| J | 확인 필요 여부와 간단한 비고 |

제목, 헤더 스타일, 자동 줄바꿈, 열 너비, 테두리, 틀 고정, 필터, 기능 분류 병합을 적용합니다. 병합은 출력 표현에만 적용되며 내부 TC에는 전체 분류가 유지됩니다. 작성자와 검토자는 CLI에서 전달된 값만 사용합니다.

## 11. 입력 파싱 상세

### Excel

- 첫 30행에서 TC 헤더 후보를 찾습니다.
- 다중 행 헤더는 최대 3행을 결합합니다.
- 시나리오·입력·기대 출력 헤더로 TC 영역을 판별합니다.
- 표준 A~J 구조가 확인되면 열 위치를 보완합니다.
- 제목·작성자·검토자·작성일은 TC로 읽지 않습니다.
- 대·중·소분류는 병합 범위의 값만 복원합니다.
- 입력·기대 출력·비고는 이전 행 값으로 채우지 않습니다.
- 셀 내부 줄바꿈을 보존합니다.
- 불명확한 행은 시트와 행 번호를 포함한 경고로 남깁니다.
- `.xls`는 `xlrd`, `.xlsx`는 `openpyxl`로 별도 처리합니다.
- `.xls` 확장자만 바꿔 `.xlsx`로 처리하지 않습니다.

### CSV

UTF-8 BOM, CP949, EUC-KR 순서로 디코딩하며 Excel과 같은 헤더 별칭을 사용합니다.

### JSON

최상위 배열 또는 `test_cases` 배열을 지원합니다.

```json
{
  "test_cases": [
    {
      "original_tc_id": "TC-001",
      "category_large": "회원",
      "category_medium": "인증",
      "category_small": "로그인",
      "scenario": "정상 계정으로 로그인할 시, 대시보드가 표시되는지 확인",
      "preconditions": "활성 계정이 존재한다.",
      "steps": [
        "로그인 화면에 접근한다.",
        "정상 계정 정보를 입력한다.",
        "로그인 버튼을 선택한다."
      ],
      "expected_results": "대시보드가 표시된다."
    }
  ]
}
```

Markdown과 TXT는 아직 구현하지 않았습니다.

## 12. 내부 TC 데이터

```json
{
  "record_id": "rec_...",
  "original_tc_id": "TC-001",
  "generated_tc_id": "GEN-0001",
  "project_id": "demo",
  "product_version": "1.0",
  "category_large": "회원",
  "category_medium": "인증",
  "category_small": "로그인",
  "scenario": "...",
  "preconditions": "...",
  "inputs": "...",
  "steps": ["..."],
  "expected_results": "...",
  "raw_input_text": "...",
  "raw_expected_output_text": "...",
  "source_refs": [],
  "origin": "generated",
  "review_status": "candidate",
  "assumptions": [],
  "expected_result_basis": "unknown",
  "requires_confirmation": true,
  "related_record_ids": []
}
```

허용 값:

- `origin`: `original`, `reconstructed`, `synthetic`, `generated`
- `review_status`: `candidate`, `needs_revision`, `approved`, `rejected`
- `expected_result_basis`: `existing_tc`, `inferred`, `unknown`

`source_refs`에는 문서 ID, 파일명, 시트, 원본 행, 원본 TC_ID가 저장됩니다.

## 13. SQLite 저장 구조

기본 DB는 `.tc-rag/tc-rag.db`이며 `--db`로 변경할 수 있습니다.

```powershell
.venv\Scripts\tc-rag --db data\project.db list --project demo
```

| 테이블 | 역할 |
|---|---|
| `documents` | 파일 해시, 프로젝트, 버전, 파싱 경고 |
| `test_cases` | 원본·생성 TC의 현재 상태 |
| `splits` | 개발/평가 분리와 유사 TC 그룹 |
| `vector_index` | 벡터, 모델, 차원, 인덱스 메타데이터 |
| `reviews` | 수정 전후 값과 검토 이력 |
| `runs` | 명령 설정, 결과, 성공·실패 시각 |
| `id_sequences` | 프로젝트별 생성 TC_ID 순번 |

## 14. 현재 참조 자료 검증 결과

2026-10-16 기준:

| 항목 | 결과 |
|---|---:|
| `.xls`/`.xlsx` 파일 | 10개 |
| 파싱된 TC | 2,571건 |
| 개발용 | 2,054건 |
| 평가용 holdout | 517건 |
| 파싱 실패 | 0건 |
| 파싱 경고 | 0건 |
| 자동 테스트 | 26건 통과 |

파일명의 문서번호를 임시 `project_id`로 사용했고 제품 버전을 확정할 수 없어 `product_version=unspecified`로 적재했습니다.

```text
GS-B-25-0207
GS-B-25-0208
TTA-26-00562
TTA-26-00668
TTA-26-00818
TTA-26-00905
TTA-26-01181
TTA-26-01732
TTA-26-01990
TTA-26-02565
```

실제 프로젝트와 제품 버전이 확정되면 새 값으로 다시 적재하고 별도 데이터·인덱스 버전을 생성해야 합니다.

## 15. 평가 방법

현재 구현은 holdout 생성과 숨긴 TC 기반 검색 점검을 지원합니다.

1. `split`으로 평가용 TC를 숨깁니다.
2. 개발용 TC만 `index`로 색인합니다.
3. 숨긴 TC의 기능 또는 시나리오를 공통 입력으로 사용합니다.
4. 다음 세 방식을 같은 입력·설정으로 비교합니다.
   - LLM만 사용
   - RAG + LLM 직접 생성
   - RAG + 조건 분석 + TC 생성
5. 검색 결과, 후보, 응답 시간, API 사용량을 저장합니다.
6. 숨긴 기존 조건의 재발견과 신규 후보 유용성을 구분합니다.

아래의 `eval` 명령군은 라벨이 있는 평가 데이터에 한해서 검색 지표와 G0/G1 생성 비교를 수행합니다. G2(사람이 고른 근거 제공)는 현재 실험 범위에서 제외합니다. 라벨이 초안이면 결과도 초안이며, 신규 후보의 유용성·실행 가능성·의미 중복·사람 수정 시간은 여전히 사람이 별도로 평가해야 합니다.

### 15.1 LAB-LOCKER 합성 프로그램 비교 실험

기존 TC에 존재하지 않는 합성 프로그램 `LAB-LOCKER 1.0`을 대상으로 기본 LLM 방식과 로컬 RAG 방식을 순서대로 비교했습니다. 입력에는 시약 상태, 보관함 상태, 예약·수령·반납·오프라인·감사 규칙을 명시했습니다.

실험 순서:

1. 기존 TC를 조회하지 않고 기본 LLM 결과를 먼저 생성하고 고정했습니다.
2. 기존 프로젝트 전체를 대상으로 로컬 해시 임베딩 교차 프로젝트 검색을 실행했습니다.
3. 검색 TC는 테스트 관점 참고에만 사용했습니다.
4. 다른 제품의 메뉴, 상태, 수치, 정책 및 기대결과는 LAB-LOCKER의 사실로 사용하지 않았습니다.
5. 두 방식 모두 같은 A~J Excel 형식으로 출력했습니다.

산출물:

- `outputs/rag-comparison/lab_locker_baseline.xlsx`
- `outputs/rag-comparison/lab_locker_rag.xlsx`

| 평가 항목 | 기본 LLM | 로컬 RAG |
|---|---:|---:|
| 생성 TC | 27건 | 27건 |
| 고유 시나리오 | 27건 | 27건 |
| 입력 요구사항 규칙 커버리지 | 37/37 | 37/37 |
| 제품 요구사항에서 기대결과 확인 가능 | 25건 | 25건 |
| 추가 확인 필요 | 2건 | 2건 |
| H·I열 공란 | 27건 | 27건 |
| 교차 프로젝트 패턴 근거가 추가된 TC | 0건 | 6건 |
| 두 방식의 핵심 내용 일치 | - | 27/27 |

추가 확인이 필요한 두 항목은 위험 시약 예약 반려 후 시약의 최종 상태와 반납 센서 오류 후 시약의 최종 상태입니다. 두 동작 모두 사용자 입력 요구사항에 최종 상태가 정의되지 않았습니다.

RAG 검색은 다섯 질의에서 각각 Top-5를 조회했습니다. 총 25개 결과 중 사람이 직접 참고 가능하다고 판단한 결과는 승인·반려 2건, 역할 기반 접근 차단 1건, 감사 기록 1건으로 총 4건입니다. 이 실험의 수동 관련성 기준 평균 `Precision@5`는 `0.16`입니다. 전체 관련 TC 정답 집합을 라벨링하지 않았으므로 Recall은 계산하지 않았습니다.

결론:

- 상세한 제품 규칙이 입력에 포함된 경우 기본 LLM만으로도 요구사항 기반 TC를 생성할 수 있었습니다.
- 로컬 RAG는 신규 프로그램의 TC 내용이나 커버리지를 개선하지 못했습니다.
- RAG가 추가한 정보는 승인·권한·감사 관점의 교차 프로젝트 근거 추적이었습니다.
- 로컬 해시 임베딩의 교차 프로젝트 검색에는 무관한 결과가 많았습니다.
- 대상 프로그램의 기존 TC가 없는 상황에서 다른 제품 TC를 검색하는 방식은 생성 효율을 높이지 않았고 검토할 근거만 증가시켰습니다.
- RAG는 대상 프로젝트의 기존 TC가 존재하거나 사용자 입력이 짧을 때 다시 평가하는 것이 적절합니다.

이 결과는 구조와 요구사항 매핑 평가입니다. 실제 시험 실행 가능성과 사람 수정 시간은 아직 측정하지 않았습니다.

## 16. 실행 기록과 실패 처리

모든 명령은 `run_id`를 발급합니다.

```json
{
  "run_id": "run_...",
  "result": {}
}
```

실패 시 표준 오류에 원인을 출력하고 `runs` 테이블에 명령, 설정, 오류, 시작·종료 시각을 기록합니다. API 호출은 60초 타임아웃과 최대 2회 추가 재시도를 사용합니다.

## 17. 문제 해결

### `openpyxl is required` 또는 `xlrd is required`

```powershell
.venv\Scripts\python -m pip install -e .
```

`.xls` 파일의 확장자만 바꾸지 마십시오.

### 검색 결과가 없음

- 색인과 검색의 `index-version`이 같은지 확인합니다.
- 프로젝트와 제품 버전이 같은지 확인합니다.
- 색인과 검색에서 같은 `--provider`를 사용합니다.
- 평가용으로 분리된 TC만 존재하는지 확인합니다.

### 실제 API 대신 모의 모드가 실행됨

`auto`는 API 키가 없으면 모의 모드입니다. 실제 호출을 강제하려면 `--provider openai`, `--llm openai`를 사용합니다.

### 후보를 승인할 수 없음

기대결과가 존재하고, 근거 유형이 `unknown`이 아니며, `requires_confirmation=false`이고, 승인 이유가 있어야 합니다.

### Windows 콘솔에서 한글이 깨짐

원본 및 출력 Excel의 문자열은 Unicode로 보존됩니다. 콘솔 코드 페이지 문제일 수 있습니다.

```powershell
chcp 65001
$env:PYTHONUTF8 = "1"
```

새 PowerShell에서 다시 실행합니다.

## 18. 현재 한계

- Markdown/TXT 파서 미구현
- 긴 TC의 다중 청크 분할 미구현
- 로컬 해시 임베딩의 의미 검색 품질 제한
- API 키가 없어 실제 임베딩·LLM 품질은 아직 미검증
- 실제 LLM JSON 응답의 세부 필드 스키마는 완전히 강제하지 않음
- 의미적 일관성은 사람 검토 필요
- 세 생성 방식을 자동 비교하는 `evaluate` 명령 미구현
- API 토큰 사용량 집계 미구현
- 참조 Excel 서식을 그대로 복제하지 않고 공통 서식을 적용
- 후보 편집은 대화형 편집기가 아닌 JSON patch 방식
- SQLite 전수 벡터 계산 방식이므로 대규모·다중 사용자 환경에는 부적합

외부 벡터 DB와 웹 UI는 현재 데이터 규모 및 검증 단계에 필요하지 않아 제외했습니다.

## 19. 권장 다음 단계

1. 실제 프로젝트 ID와 제품 버전 확정
2. 실제 임베딩·LLM API 설정
3. 새 인덱스 버전 생성
4. 대표 기능 10~20건의 검색 결과 검토
5. 실제 LLM 후보와 사람 수정 시간 기록
6. 기대결과 근거 및 중복 판정 보강
7. 필요할 때만 청킹·외부 벡터 DB·UI 추가

품질이 확인되기 전에는 검색 인프라나 UI를 확장하지 않는 것을 권장합니다.
## 성능 평가 및 실험

평가 기능은 기존 `test_cases` 저장소와 임베딩 제공자를 재사용한다. 운영 인덱스를 삭제하거나 덮어쓰지 않고 `exp:<experiment_id>:<설정 해시>` 버전으로 실험 벡터를 별도 저장한다. 검색 평가는 관련 정답이 인덱스에 있는 `retrieval`과 숨긴 TC를 인덱스·생성 컨텍스트에서 제외하는 `rediscovery`를 구분한다.

### 평가 데이터 준비

[`examples/evaluation_cases.example.json`](examples/evaluation_cases.example.json)을 복사한 뒤 실제 `record_id`로 교체한다. 자동 작성한 사례와 라벨은 반드시 `human_reviewed: false`로 시작하고, 사람이 관련 TC와 숨긴 조건을 확인한 뒤 `true`로 변경한다. 개발용 사례는 `split: development`, 마지막 검증에만 쓸 사례는 `split: final`로 지정한다. 같은 정답 TC를 두 split에 넣으면 검증이 실패한다.

현재 DB의 TTA-26-01181 TC로 작성한 20개 초안은 [`examples/evaluation_cases.dev.json`](examples/evaluation_cases.dev.json), 대응 설정은 [`examples/evaluation_config.dev.json`](examples/evaluation_config.dev.json)에 있다. 16개는 개발용 검색 사례이고 4개는 숨긴 조건 재발견용 최종 평가 사례다. 원본 초안은 보존한다.

개발 사례 16개의 사람 검토 완료본은 [`examples/evaluation_cases.reviewed-v1.json`](examples/evaluation_cases.reviewed-v1.json), 1단계 baseline 설정은 [`examples/evaluation_config.baseline-reviewed-v1.json`](examples/evaluation_config.baseline-reviewed-v1.json)에 있다. 개발 사례만 `human_reviewed: true`이며, 미사용 최종 평가 사례 4개는 별도 검토 전까지 `false`를 유지한다.

2단계 local-hash E1~E4 비교 설정은 [`examples/evaluation_config.stage2-local-e1-e4-v1.json`](examples/evaluation_config.stage2-local-e1-e4-v1.json)에 있다. TTA-26-01181 원본은 사전조건과 입력이 별도 필드로 분리되지 않아 E2와 E3 입력이 동일하다. 현재 데이터에서 E3의 추가 효과를 별도로 해석하지 않는다.

3단계 Top-K 비교 설정은 [`examples/evaluation_config.stage3-local-topk-v1.json`](examples/evaluation_config.stage3-local-topk-v1.json), 완료 보고서는 [`outputs/stage3-local-topk-v1/stage3-completion.md`](outputs/stage3-local-topk-v1/stage3-completion.md)에 있다. 현재 local-hash 개발셋에서는 K=10을 다음 단계 주 설정으로 선택했고 K=5를 효율 대안으로 보존했다. 이는 의미 임베딩의 보편적 최적값이 아니다.

4단계 검색 방식 비교의 수정 후 설정은 [`examples/evaluation_config.stage4-local-search-method-v2.json`](examples/evaluation_config.stage4-local-search-method-v2.json), 완료 보고서는 [`outputs/stage4-local-search-method-v2/stage4-completion.md`](outputs/stage4-local-search-method-v2/stage4-completion.md)에 있다. Hybrid RRF-60을 다음 단계 주 설정으로 선택하고 BM25를 비용·단순성 대안으로 보존했다. 수정 전 v1 결과는 RRF 결합 오류 때문에 비채택 처리했다.

5단계 재순위화 비교의 수정 후 설정은 [`examples/evaluation_config.stage5-local-rerank-v2.json`](examples/evaluation_config.stage5-local-rerank-v2.json), 완료 보고서는 [`outputs/stage5-local-rerank-v2/stage5-completion.md`](outputs/stage5-local-rerank-v2/stage5-completion.md)에 있다. RRF 원천 검색 깊이를 `rrf_candidate_k=50`으로 고정하고 `candidate_record_ids`로 동일 후보 비교를 검증했다. 현재 local-hash 개발셋에서는 재순위화 없음과 후보 20개를 잠정 유지했다. 수정 전 v1 결과는 두 변수가 함께 바뀐 설계 문제로 비채택 처리했다.

6단계 실패 사례 기반 비교 설정은 [`examples/evaluation_config.stage6-local-failure-focused-v1.json`](examples/evaluation_config.stage6-local-failure-focused-v1.json), 완료 보고서는 [`outputs/stage6-local-failure-focused-v1/stage6-completion.md`](outputs/stage6-local-failure-focused-v1/stage6-completion.md)에 있다. Q2/Q3, MMR, C2를 비교했으며 Q3를 다음 단계 질의 구성 후보로 잠정 선택했다. 제품 용어 사전이 없어 terms 전처리는 미실행으로 기록했다.

7단계 임베딩 모델 비교 설정은 [`examples/evaluation_config.stage7-embedding-model-v1.json`](examples/evaluation_config.stage7-embedding-model-v1.json), 미실행 기록은 [`outputs/stage7-embedding-model-v1/stage7-completion.md`](outputs/stage7-embedding-model-v1/stage7-completion.md)에 있다. OpenAI API 실험 제외 및 비교 가능한 로컬 모델 부재로 실제 비교는 실행하지 않았다.

사례의 핵심 필드는 다음과 같다.

- `evaluation_type`: `retrieval` 또는 `rediscovery`
- `relevant_record_ids`: 검색 평가의 관련 정답 TC
- `relevance_grades`: 선택 필드이며 숫자 등급이 있을 때만 nDCG를 계산
- `curated_evidence_ids`: 사람이 검토한 참고 근거 기록. 현재 생성 실험에서는 사용하지 않으며 숨긴 TC는 넣을 수 없음
- `hidden_record_ids`: 조건 재발견에서 검색·생성 입력에서 제외할 TC
- `hidden_conditions`: 문장 일치가 아닌 의미 단위의 재발견 정답
- `forbidden_inferences`: 근거 없이 확정하면 안 되는 정책·수치·오류 메시지
- `generation_criteria`: 실행 가능성, 판정 가능성 등 사람 평가 기준

정상 기능, 경계값, 입력 오류, 권한, 상태 전이, 정책 적용, 실패·복구, 여러 근거 조합, 무근거 요청, 충돌·정보 부족 사례를 각각 준비한다. TC만으로 제품의 전체 요구사항 커버리지나 실제 동작 정확성을 증명할 수는 없다.

### 설정

[`examples/evaluation_config.example.json`](examples/evaluation_config.example.json)의 baseline은 TC 한 건, E4, 벡터 검색, Top-5, 프로젝트·버전 범위, 재순위화 없음, 원문 질의, 4,000 토큰 예산이다. 한 번에 전체 조합을 실행하지 말고 `experiments`에 현재 단계의 차이만 추가한다.

임베딩 입력은 아래처럼 고정된다.

| 설정 | 입력 | 확인 목적 |
|---|---|---|
| E1 | 테스트 시나리오만 | 기능과 테스트 의도를 간결하게 검색하는가 |
| E2 | 기능 대/중/소분류 + 시나리오 | 비슷한 문장이 다른 기능과 혼동되는 것을 줄이는가 |
| E3 | E2 + 입력 및 사전조건 | 입력값과 상태에 맞는 TC를 찾는가 |
| E4 | E3 + 수행 절차 + 기대결과 | 구체적인 동작과 결과까지 검색에 도움이 되는가 |

검색 단위는 `C1`(TC 한 건), `C2`(긴 TC만 분할 후 원본 TC로 통합), `C3`(같은 소분류를 `group_size`만큼 묶고 결과를 TC로 펼침)를 지원한다. 검색 방식은 `vector`, `keyword`(BM25), `hybrid`(RRF)를 지원한다. 하이브리드는 이질적인 점수를 직접 더하지 않는다. `rerank`는 `none`, `lexical-20`, `lexical-50`, 선택 방식은 `similarity`, `mmr`이다. Q1~Q4는 각각 원문, 기능명+원문, 구조화 질의, 관점별 다중 질의다.

로컬 `mock` 임베딩은 API 없는 파이프라인·지표 검증용이며 실제 의미 검색 모델 성능으로 해석하면 안 된다. 비교 모델은 `embedding_provider: openai`로 별도 실험하고 문서와 질의를 같은 모델로 임베딩한다. 평가 설정에서는 `mock` 또는 `openai`를 명시해야 하며, 인증정보가 없을 때 조용히 mock으로 바뀌는 `auto`는 허용하지 않는다.

### 실행 순서

```powershell
# 1. 데이터와 설정 검증
tc-rag eval validate --dataset examples/evaluation_cases.json --config examples/evaluation_config.json

# 2. 실제 호출 전 실행 수, 백엔드 가용성, 확인 가능한 비용 하한 확인
tc-rag eval dry-run --dataset examples/evaluation_cases.json --config examples/evaluation_config.json

# 3. 사람 검토용 라벨 팩 생성 (설정의 evaluation_split만 포함)
tc-rag eval review-pack --dataset examples/evaluation_cases.dev.json --config examples/evaluation_config.dev.json --output outputs/evaluation-label-review-development.csv

# 4. 검색 평가. 결과와 실험 인덱스는 운영 인덱스와 분리됨
tc-rag eval retrieval --dataset examples/evaluation_cases.json --config examples/evaluation_config.json --output outputs/eval-001

# 중단 후 성공한 task_id는 건너뛰고 재개
tc-rag eval retrieval --dataset examples/evaluation_cases.json --config examples/evaluation_config.json --output outputs/eval-001 --resume

# 5. 실행하지 않고 G0/G1 × API/Codex 계획과 불가 사유 기록
tc-rag eval compare --dataset examples/evaluation_cases.json --config examples/evaluation_config.json --retrieval-results outputs/eval-001/retrieval_results.jsonl --output outputs/eval-001

# 6. 실제 API/Codex 실행. 키나 CLI가 없으면 not_run이며 mock으로 대체하지 않음
tc-rag eval compare --dataset examples/evaluation_cases.json --config examples/evaluation_config.json --retrieval-results outputs/eval-001/retrieval_results.jsonl --output outputs/eval-001 --execute --resume

# 7. JSONL/CSV 결과를 Markdown으로 집계
tc-rag eval report --results outputs/eval-001 --output outputs/eval-001/report.md
```

`review-pack`은 기존 DB와 평가 JSON을 변경하지 않는다. 같은 출력 파일이 이미 있으면 검토자 입력을 잃지 않도록 실패한다. CSV의 `reviewer_decision`과 `reviewer_notes`를 사람이 작성한 뒤, 사례 JSON의 `human_reviewed`와 라벨을 별도로 갱신해야 하며 명령이 이를 자동으로 승인 처리하지 않는다. 개발용 설정에 `evaluation_split: development`가 있으면 최종 평가 사례는 팩에 포함되지 않는다.

`generation`과 `compare`는 같은 실행기를 사용한다. 비교 시 설정의 `backends`를 `["api", "codex"]`로 두면 실제 작성 지침, JSON Schema, 질의, 저장된 근거 내용과 순서로 만든 동일 공통 입력 해시를 재사용한다. Codex는 매번 `codex exec --ephemeral --ignore-user-config --ignore-rules --sandbox read-only`로 시작하고, 최소 환경변수만 전달하며 공통 지침에서 도구·외부 자료 사용을 금지한다. 다만 Codex CLI의 built-in 읽기 도구를 기술적으로 완전히 끌 수 없으므로 기본 실행은 차단한다. 비밀이 전혀 없는 격리 환경에서만 `TC_RAG_ALLOW_CODEX_READ_TOOLS=1`을 명시해 허용한다. 현재 일반 출력 모드는 내부 도구 이벤트를 노출하지 않으므로 실제 도구 호출 여부는 `null`과 사유로 기록한다. API와 Codex의 내부 지침까지 같다고 주장하지 않으며, 이 차이를 순수 RAG 효과로 해석하지 않는다.

### 산출물과 해석

- `retrieval_results.jsonl`: 질의, 설정, 인덱스 버전, 원본 TC 단위 결과, 점수 종류, 실제 컨텍스트, 시간, 오류
- `retrieval_results.csv`: P@K, R@K, MRR@K, 조건부 nDCG@K 비교표
- `retrieval_summary.json`: actual과 mock을 분리하고 실패·미실행을 제외한 설정별 평균
- `generation_results.jsonl`: G0/G1, API/Codex, 공통 입력 해시, 결과, 자동 검증, 미실행 이유
- `generation_results.csv`: 생성 방식별 후보 수, 유효 후보 비율, 금지 추론 탐지, 상태와 시간
- `report.md`: actual/mock 검색 비교, 생성 실행 상태, 미실행 및 한계 요약

Precision@K 분모는 결과 부족 여부와 관계없이 K다. 청크와 묶음은 원본 `record_id`로 합친 후 지표를 계산한다. 미판정 TC는 `unjudged_retrieved`로 남겨 자동으로 무관하다고 확정하지 않는다. 관련성 등급이 없으면 nDCG는 `null`이다. 토큰 예산은 문자 수 기반 추정이며 TC를 중간에서 자르지 않고 초과 TC 전체를 제외한다.

생성 자동 검증은 스키마, 제공된 근거 ID, 금지 문자열 같은 기계 검증만 담당한다. 근거가 주장을 실제로 뒷받침하는지, 실행·판정 가능한지, 신규 가치가 있는지는 생성 방식을 가린 사람 A/B 평가로 기록해야 한다. 반복 결과는 독립 사례로 세지 말고 사례별 평균과 편차를 함께 해석한다.

비용은 설정에 기준일·출처·입출력 단가를 명시한 경우에만 입력 토큰 하한을 계산한다. 단가가 없거나 Codex 플랜의 실제 비용을 확인할 수 없으면 `null`과 이유를 저장한다. `actual`, `mock`, `not_run`, `failed`는 구분되며 실패·미실행은 정상 평균에서 제외된다.
