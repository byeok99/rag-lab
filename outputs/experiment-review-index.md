# TC RAG 실험 사람 검토 인덱스

각 단계의 `review-notes.md`에는 결과 해석, 설정 선택 이유, 반대 선택 가능성, 확인 질문, 확정하면 안 되는 주장과 검토 기록란이 있다.

| 단계 | 실험 | 선택 결과 | 사람 검토 문서 | 상세 완료 보고서 |
|---:|---|---|---|---|
| 1 | baseline 및 평가 데이터 검증 | 파이프라인 검증 완료 | [1단계 검토 노트](stage1-baseline-reviewed-v1/review-notes.md) | [1단계 완료 보고](stage1-baseline-reviewed-v1/stage1-completion.md) |
| 2 | 임베딩 입력 E1~E4 | E2를 개발 후보로 선택 | [2단계 검토 노트](stage2-local-e1-e4-v1/review-notes.md) | [2단계 완료 보고](stage2-local-e1-e4-v1/stage2-completion.md) |
| 3 | Top-K 3/5/10/15 | K=10 선택, K=5 대안 | [3단계 검토 노트](stage3-local-topk-v1/review-notes.md) | [3단계 완료 보고](stage3-local-topk-v1/stage3-completion.md) |
| 4 | 벡터/BM25/Hybrid RRF | Hybrid 선택, BM25 대안 | [4단계 검토 노트](stage4-local-search-method-v2/review-notes.md) | [4단계 완료 보고](stage4-local-search-method-v2/stage4-completion.md) |
| 5 | 재순위화 및 후보 20/50 | 재순위화 없음·후보 20 잠정 유지 | [5단계 검토 노트](stage5-local-rerank-v2/review-notes.md) | [5단계 완료 보고](stage5-local-rerank-v2/stage5-completion.md) |
| 6 | 실패 사례 기반 질의·다양성·청킹 | Q3 잠정 선택, MMR 보류 | [6단계 검토 노트](stage6-local-failure-focused-v1/review-notes.md) | [6단계 완료 보고](stage6-local-failure-focused-v1/stage6-completion.md) |
| 7 | 임베딩 모델 비교 | 미실행: 승인된 로컬 비교 모델 없음, OpenAI API 제외 | [7단계 검토 노트](stage7-embedding-model-v1/review-notes.md) | [7단계 완료 기록](stage7-embedding-model-v1/stage7-completion.md) |

## 공통 검토 원칙

- 개발셋에서 선택한 설정을 최종 성능으로 해석하지 않는다.
- `local-hash-v1` 결과를 실제 의미 임베딩 성능으로 일반화하지 않는다.
- 미판정 TC를 자동으로 무관하다고 확정하지 않는다.
- 검색 지표 향상을 생성 품질 향상으로 간주하지 않는다.
- 기존 TC만으로 전체 요구사항 커버리지나 실제 제품 동작 정확성을 주장하지 않는다.
- API 직접 호출과 G2는 제외하며, 생성 비교는 Codex CLI G0/G1만 수행한다.

## 전체 검토 기록

| 검토자 | 검토일 | 검토 완료 단계 | 주요 결정/수정 요청 |
|---|---|---|---|
|  |  |  |  |
