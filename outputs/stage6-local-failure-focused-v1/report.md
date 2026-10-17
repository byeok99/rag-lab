# TC RAG evaluation report

Generated: 2026-10-17T04:39:35.649141+00:00

## Retrieval

### Actual retrieval

| Setting | Cases | P@K | R@K | MRR@K | nDCG@K |
|---|---:|---:|---:|---:|---:|
| _No successful runs_ | 0 | N/A | N/A | N/A | N/A |

### Mock retrieval

| Setting | Cases | P@K | R@K | MRR@K | nDCG@K |
|---|---:|---:|---:|---:|---:|
| baseline | 15 | 0.2667 | 0.9733 | 0.9667 | 0.9031 |
| Q2 | 15 | 0.2800 | 1.0000 | 0.9667 | 0.9122 |
| Q3 | 15 | 0.2800 | 1.0000 | 0.9667 | 0.9227 |
| MMR-0.7 | 15 | 0.1467 | 0.5544 | 0.9333 | 0.5563 |
| C2-chunk-2000 | 15 | 0.2667 | 0.9733 | 0.9667 | 0.9031 |

Metrics are based only on supplied relevance labels. They do not prove product requirements coverage.

### Retrieval failures by purpose

{"경계값 및 집계 결과 검색":1,"권한 부여와 회수 상태 비교":1,"권한·조건별 출력 차이":1,"기존·신규 상태 조합":1,"동시 처리와 복구 완료 검증":3,"보안 모드별 동작":1,"설정값별 정책 비교":1,"여러 TC 근거 조합":1,"잠금과 복구 상태 전이":1,"정상 기능과 연속된 검증 근거 검색":1,"정책 적용과 권한별 결과":1,"충돌하거나 불명확한 기대결과 탐지":1,"허용 상태 전이":1}

## Generation

Status counts: `{}`

| Backend | Condition | Runs | Candidates mean | Valid ratio mean | Valid ratio SD | Forbidden hits | Mean seconds |
|---|---|---:|---:|---:|---:|---:|---:|
| _No successful generation runs_ | - | 0 | N/A | N/A | N/A | N/A | N/A |

Known generation cost total: `None`

Automatic checks cover schema/evidence IDs and explicit forbidden strings only. Evidence support, execution feasibility, judgeability, usefulness, duplication, and hidden-condition meaning require blinded human review.

## Not run / limitations

- Runs excluded from relevance metrics: 5
- Generation runs: 0 (retrieval-only; generation was not scheduled)
- Unknown cost remains null; Codex plan usage is not converted to API billing.
- Codex and API internal instructions are not assumed identical; their comparison is not a pure RAG-effect estimate.
- Next: human-review draft labels, run staged actual retrieval, then compare the top 2-3 settings.
