# TC RAG evaluation report

Generated: 2026-10-16T11:26:18.979076+00:00

## Retrieval

### Actual retrieval

| Setting | Cases | P@K | R@K | MRR@K | nDCG@K |
|---|---:|---:|---:|---:|---:|
| _No successful runs_ | 0 | N/A | N/A | N/A | N/A |

### Mock retrieval

| Setting | Cases | P@K | R@K | MRR@K | nDCG@K |
|---|---:|---:|---:|---:|---:|
| baseline | 15 | 0.1733 | 0.3756 | 0.3500 | 0.3383 |
| E1 | 15 | 0.3867 | 0.7578 | 0.7667 | 0.6786 |
| E2 | 15 | 0.4267 | 0.8189 | 0.7722 | 0.7362 |
| E3 | 15 | 0.2667 | 0.5389 | 0.5500 | 0.4846 |
| E4 | 15 | 0.1733 | 0.3756 | 0.3500 | 0.3383 |

Metrics are based only on supplied relevance labels. They do not prove product requirements coverage.

### Retrieval failures by purpose

{"unspecified":46}

## Generation

Status counts: `{'not_run': 288}`

| Backend | Condition | Runs | Candidates mean | Valid ratio mean | Valid ratio SD | Forbidden hits | Mean seconds |
|---|---|---:|---:|---:|---:|---:|---:|
| _No successful generation runs_ | - | 0 | N/A | N/A | N/A | N/A | N/A |

Known generation cost total: `None`

Automatic checks cover schema/evidence IDs and explicit forbidden strings only. Evidence support, execution feasibility, judgeability, usefulness, duplication, and hidden-condition meaning require blinded human review.

## Not run / limitations

- Runs excluded from relevance metrics: 5
- Generation not-run or failed: 288
- Unknown cost remains null; Codex plan usage is not converted to API billing.
- Codex and API internal instructions are not assumed identical; their comparison is not a pure RAG-effect estimate.
- Next: human-review draft labels, run staged actual retrieval, then compare the top 2-3 settings.
