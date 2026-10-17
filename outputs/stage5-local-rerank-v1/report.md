# TC RAG evaluation report

Generated: 2026-10-17T00:01:13.496817+00:00

## Retrieval

### Actual retrieval

| Setting | Cases | P@K | R@K | MRR@K | nDCG@K |
|---|---:|---:|---:|---:|---:|
| _No successful runs_ | 0 | N/A | N/A | N/A | N/A |

### Mock retrieval

| Setting | Cases | P@K | R@K | MRR@K | nDCG@K |
|---|---:|---:|---:|---:|---:|
| baseline | 15 | 0.2600 | 0.9600 | 0.9667 | 0.9012 |
| BM25-Rerank-20 | 15 | 0.2667 | 0.9778 | 0.9133 | 0.8904 |
| BM25-Rerank-50 | 15 | 0.2667 | 0.9778 | 0.9133 | 0.8904 |

Metrics are based only on supplied relevance labels. They do not prove product requirements coverage.

### Retrieval failures by purpose

{"동시 처리와 복구 완료 검증":1,"여러 TC 근거 조합":2}

## Generation

Status counts: `{}`

| Backend | Condition | Runs | Candidates mean | Valid ratio mean | Valid ratio SD | Forbidden hits | Mean seconds |
|---|---|---:|---:|---:|---:|---:|---:|
| _No successful generation runs_ | - | 0 | N/A | N/A | N/A | N/A | N/A |

Known generation cost total: `None`

Automatic checks cover schema/evidence IDs and explicit forbidden strings only. Evidence support, execution feasibility, judgeability, usefulness, duplication, and hidden-condition meaning require blinded human review.

## Not run / limitations

- Runs excluded from relevance metrics: 3
- Generation runs: 0 (retrieval-only; generation was not scheduled)
- Unknown cost remains null; Codex plan usage is not converted to API billing.
- Codex and API internal instructions are not assumed identical; their comparison is not a pure RAG-effect estimate.
- Next: human-review draft labels, run staged actual retrieval, then compare the top 2-3 settings.
