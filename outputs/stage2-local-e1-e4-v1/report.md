# TC RAG evaluation report

Generated: 2026-10-16T23:38:26.712098+00:00

## Retrieval

### Actual retrieval

| Setting | Cases | P@K | R@K | MRR@K | nDCG@K |
|---|---:|---:|---:|---:|---:|
| _No successful runs_ | 0 | N/A | N/A | N/A | N/A |

### Mock retrieval

| Setting | Cases | P@K | R@K | MRR@K | nDCG@K |
|---|---:|---:|---:|---:|---:|
| baseline | 15 | 0.2400 | 0.5011 | 0.5556 | 0.4798 |
| E1 | 15 | 0.3867 | 0.7578 | 0.7667 | 0.6786 |
| E2 | 15 | 0.4267 | 0.8189 | 0.7722 | 0.7362 |
| E3 | 15 | 0.4267 | 0.8189 | 0.7722 | 0.7362 |

Metrics are based only on supplied relevance labels. They do not prove product requirements coverage.

### Retrieval failures by purpose

{"경계값 및 집계 결과 검색":4,"권한 부여와 회수 상태 비교":1,"권한·조건별 출력 차이":1,"기존·신규 상태 조합":4,"동시 처리와 복구 완료 검증":4,"보안 모드별 동작":4,"여러 TC 근거 조합":4,"정책 적용과 권한별 결과":1,"충돌하거나 불명확한 기대결과 탐지":4,"허용 상태 전이":4}

## Generation

Status counts: `{}`

| Backend | Condition | Runs | Candidates mean | Valid ratio mean | Valid ratio SD | Forbidden hits | Mean seconds |
|---|---|---:|---:|---:|---:|---:|---:|
| _No successful generation runs_ | - | 0 | N/A | N/A | N/A | N/A | N/A |

Known generation cost total: `None`

Automatic checks cover schema/evidence IDs and explicit forbidden strings only. Evidence support, execution feasibility, judgeability, usefulness, duplication, and hidden-condition meaning require blinded human review.

## Not run / limitations

- Runs excluded from relevance metrics: 4
- Generation not-run or failed: 0
- Unknown cost remains null; Codex plan usage is not converted to API billing.
- Codex and API internal instructions are not assumed identical; their comparison is not a pure RAG-effect estimate.
- Next: human-review draft labels, run staged actual retrieval, then compare the top 2-3 settings.
