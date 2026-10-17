# TC RAG evaluation report

Generated: 2026-10-17T05:44:58.414826+00:00

## Retrieval

### Actual retrieval

| Setting | Cases | P@K | R@K | MRR@K | nDCG@K | Hit@K | Mean sec |
|---|---:|---:|---:|---:|---:|---:|---:|
| M2-bge-m3-vector | 15 | 0.2800 | 1.0000 | 1.0000 | 0.9848 | 1.0000 | 0.6149 |
| M4-bge-m3-hybrid-rrf | 15 | 0.2800 | 1.0000 | 0.9667 | 0.9501 | 1.0000 | 0.4796 |

### Mock retrieval

| Setting | Cases | P@K | R@K | MRR@K | nDCG@K | Hit@K | Mean sec |
|---|---:|---:|---:|---:|---:|---:|---:|
| M0-bm25 | 15 | 0.2667 | 0.9778 | 0.9667 | 0.9147 | 1.0000 | 0.0051 |
| M1-local-hash-vector | 15 | 0.2733 | 0.9889 | 0.9333 | 0.8460 | 1.0000 | 0.0058 |
| M3-local-hash-hybrid-rrf | 15 | 0.2800 | 1.0000 | 0.9667 | 0.9227 | 1.0000 | 0.0094 |

Metrics are based only on supplied relevance labels. They do not prove product requirements coverage.

### Retrieval failures by purpose

{"여러 TC 근거 조합":2}

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
