# TC RAG evaluation report

Generated: 2026-10-16T23:22:55.702395+00:00

## Retrieval

### Actual retrieval

| Setting | Cases | P@K | R@K | MRR@K | nDCG@K |
|---|---:|---:|---:|---:|---:|
| _No successful runs_ | 0 | N/A | N/A | N/A | N/A |

### Mock retrieval

| Setting | Cases | P@K | R@K | MRR@K | nDCG@K |
|---|---:|---:|---:|---:|---:|
| baseline | 15 | 0.1733 | 0.3756 | 0.3500 | 0.3383 |

Metrics are based only on supplied relevance labels. They do not prove product requirements coverage.

### Retrieval failures by purpose

{"경계값 및 집계 결과 검색":1,"권한 부여와 회수 상태 비교":1,"권한·조건별 출력 차이":1,"기존·신규 상태 조합":1,"동시 처리와 복구 완료 검증":1,"보안 모드별 동작":1,"여러 TC 근거 조합":1,"잠금과 복구 상태 전이":1,"정책 적용과 권한별 결과":1,"충돌하거나 불명확한 기대결과 탐지":1,"허용 상태 전이":1}

## Generation

Status counts: `{}`

| Backend | Condition | Runs | Candidates mean | Valid ratio mean | Valid ratio SD | Forbidden hits | Mean seconds |
|---|---|---:|---:|---:|---:|---:|---:|
| _No successful generation runs_ | - | 0 | N/A | N/A | N/A | N/A | N/A |

Known generation cost total: `None`

Automatic checks cover schema/evidence IDs and explicit forbidden strings only. Evidence support, execution feasibility, judgeability, usefulness, duplication, and hidden-condition meaning require blinded human review.

## Not run / limitations

- Runs excluded from relevance metrics: 1
- Generation not-run or failed: 0
- Unknown cost remains null; Codex plan usage is not converted to API billing.
- Codex and API internal instructions are not assumed identical; their comparison is not a pure RAG-effect estimate.
- Development labels are human-reviewed. Next: run staged actual retrieval, then compare the top 2-3 settings. Final-split labels remain draft until the final validation stage.
