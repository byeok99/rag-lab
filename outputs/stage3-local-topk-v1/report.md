# TC RAG evaluation report

Generated: 2026-10-16T23:42:52.622552+00:00

## Retrieval

### Actual retrieval

| Setting | Cases | P@K | R@K | MRR@K | nDCG@K |
|---|---:|---:|---:|---:|---:|
| _No successful runs_ | 0 | N/A | N/A | N/A | N/A |

### Mock retrieval

| Setting | Cases | P@K | R@K | MRR@K | nDCG@K |
|---|---:|---:|---:|---:|---:|
| baseline | 15 | 0.4267 | 0.8189 | 0.7722 | 0.7362 |
| TopK-3 | 15 | 0.5778 | 0.7089 | 0.7556 | 0.7009 |
| TopK-10 | 15 | 0.2467 | 0.9267 | 0.7722 | 0.7850 |
| TopK-15 | 15 | 0.1733 | 0.9600 | 0.7722 | 0.8001 |

Metrics are based only on supplied relevance labels. They do not prove product requirements coverage.

### Retrieval failures by purpose

{"경계값 및 집계 결과 검색":2,"기존·신규 상태 조합":2,"동시 처리와 복구 완료 검증":4,"보안 모드별 동작":3,"여러 TC 근거 조합":3,"충돌하거나 불명확한 기대결과 탐지":2,"허용 상태 전이":2}

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
