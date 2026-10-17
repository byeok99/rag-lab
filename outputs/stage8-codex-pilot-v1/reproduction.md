# Stage 8 Codex CLI 재현 절차

```bash
TC_RAG_ALLOW_CODEX_READ_TOOLS=1 .venv/bin/python -m tc_rag.cli \
  --db .tc-rag/tc-rag.db eval generation \
  --dataset examples/evaluation_cases.reviewed-v1.json \
  --config examples/evaluation_config.stage8-codex-pilot-v1.json \
  --retrieval-results outputs/stage7-vector-db-v1/retrieval_results.jsonl \
  --output outputs/stage8-codex-pilot-v1 --execute --resume
```

파일의 `generation.case_ids`를 제거하고 `repetitions`를 3으로 바꾸면 개발 분할 전체 반복 계획으로 확장할 수 있다. 검색 근거는 저장된 Vector DB 결과 파일을 재사용하며, API provider는 사용하지 않는다.
