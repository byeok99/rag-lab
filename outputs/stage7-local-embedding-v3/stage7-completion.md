# Stage 7 완료 보고서: BGE-M3 실제 실행

## 목적

E2/C1/Q3, Top-K 10, Candidate-K 20, RRF candidate-K 50, RRF K 60, rerank 없음, project/version 필터를 고정하고 BM25·Local Hash·BGE-M3를 비교했다.

## 실행 환경

- Python 3.11.6, macOS arm64
- sentence-transformers 5.7.0, torch 2.14.1
- BGE-M3 차원 1024, MPS 실행
- 모델 다운로드 및 로컬 캐시 성공
- OpenAI API 호출 없음

## 정량 결과

| 조건 | 실행 모드 | 사례 | P@10 | R@10 | MRR@10 | nDCG@10 | Hit@10 | 평균 초 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| M0 BM25 | mock/local | 15 | 0.2667 | 0.9778 | 0.9667 | 0.9147 | 1.0000 | 0.0051 |
| M1 Local Hash + Vector | mock/local | 15 | 0.2733 | 0.9889 | 0.9333 | 0.8460 | 1.0000 | 0.0058 |
| M2 BGE-M3 + Vector | actual | 15 | 0.2800 | 1.0000 | 1.0000 | 0.9848 | 1.0000 | 0.6149 |
| M3 Local Hash + Hybrid RRF | mock/local | 15 | 0.2800 | 1.0000 | 0.9667 | 0.9227 | 1.0000 | 0.0094 |
| M4 BGE-M3 + Hybrid RRF | actual | 15 | 0.2800 | 1.0000 | 0.9667 | 0.9501 | 1.0000 | 0.4796 |

관련 라벨이 있는 15개 사례만 정량 지표에 포함했다. 관련 근거가 없는 사례는 무관으로 확정하지 않았다.

## 해석

이번 개발셋에서는 M2 BGE-M3 Vector가 M1 Local Hash Vector보다 MRR과 nDCG가 높았다. M4 Hybrid는 M3보다 nDCG가 높지만 MRR은 동일했다. M2/M4의 평균 처리 시간은 Hash 방식보다 크다.

따라서 현재 개발셋 기준 의미 임베딩이 순위 품질을 개선할 가능성은 확인했지만, 사례 수가 작고 최종 평가셋이 아니므로 보편적인 우열이나 제품 전체 커버리지로 해석하지 않는다.

## 인덱스

BGE-M3 Vector와 Hybrid 각각 별도 `index_version`으로 208개 TC 벡터를 SQLite `vector_index`에 저장했다. Local Hash 인덱스와 벡터를 혼용하지 않았다.

## 한계와 다음 단계

최종 평가셋에서 동일 설정을 고정해 검증하고, 모델 캐시·인덱스 저장 용량과 질문별 순위 변화를 함께 분석한다. 이후 상위 검색 설정 2개에 대해 Codex CLI G0/G1 생성 품질 비교를 별도 수행한다.
