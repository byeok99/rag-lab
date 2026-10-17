# Vector DB 재검증 재현 절차

전체 TC E2 인덱스가 먼저 존재해야 한다. `stage7-full-local-hash-e2-v1`과 `stage7-full-bge-m3-e2-v1`은 SQLite `vector_index`에 저장된 별도 인덱스다.

```bash
HF_HUB_OFFLINE=1 .venv/bin/python -m tc_rag.cli --db .tc-rag/tc-rag.db eval retrieval \
  --dataset examples/evaluation_cases.reviewed-v1.json \
  --config examples/evaluation_config.stage7-vector-db-v1.json \
  --output outputs/stage7-vector-db-v1
```

설정의 `vector_index_version`이 지정된 조건은 저장 벡터를 로드한다. 인덱스 모델, 차원, E2 profile이 맞지 않거나 레코드가 누락되면 실패하며 다른 모델이나 mock으로 대체하지 않는다.
