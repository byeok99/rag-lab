# Stage 7 BGE-M3 재현 절차

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e '.[local-embedding]'
.venv/bin/python -m pytest -q
HF_HUB_OFFLINE=0 .venv/bin/python - <<'PY'
from tc_rag.providers import SentenceTransformerEmbedder
m=SentenceTransformerEmbedder(model='BAAI/bge-m3', dimension=1024, device='auto', batch_size=8, max_seq_length=8192, model_cache_dir='.tc-rag/models')
print(m.dimension, m.device)
PY
HF_HUB_OFFLINE=1 .venv/bin/python -m tc_rag.cli --db .tc-rag/tc-rag.db eval retrieval \
  --dataset examples/evaluation_cases.reviewed-v1.json \
  --config examples/evaluation_config.stage7-local-embedding-v3.json \
  --output outputs/stage7-local-embedding-v3
```

원본 TC와 모델 캐시는 Git에 포함하지 않는다. 모델이 캐시에 없으면 다운로드를 먼저 수행하고, 실패 시 해당 조건은 `not_run`으로 기록한다.
