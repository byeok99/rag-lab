# Stage 7 재현 절차

원본 TC 파일과 모델 캐시는 저장소에 포함하지 않는다. 동일한 TC를 별도로 준비해 기존 SQLite DB에 import한 뒤 다음을 실행한다.

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e '.[local-embedding]'
.venv/bin/python -m pytest -q
.venv/bin/python -m tc_rag.cli --db .tc-rag/tc-rag.db eval validate \
  --dataset examples/evaluation_cases.reviewed-v1.json \
  --config examples/evaluation_config.stage7-local-embedding-v2.json
.venv/bin/python -m tc_rag.cli --db .tc-rag/tc-rag.db eval dry-run \
  --dataset examples/evaluation_cases.reviewed-v1.json \
  --config examples/evaluation_config.stage7-local-embedding-v2.json
.venv/bin/python -m tc_rag.cli --db .tc-rag/tc-rag.db eval retrieval \
  --dataset examples/evaluation_cases.reviewed-v1.json \
  --config examples/evaluation_config.stage7-local-embedding-v2.json \
  --output outputs/stage7-local-embedding-v2 --resume
```

`BAAI/bge-m3` 가중치가 모델 캐시에 없으면 M2/M4는 `not_run`으로 기록되어 mock 결과로 대체되지 않는다. 모델을 다운로드할 수 있는 환경에서 동일 명령을 다시 실행하면 성공한 작업만 resume 대상으로 재사용한다. API 키는 필요하지 않다.
