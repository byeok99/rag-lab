# Stage 7 모델별 차이 분석

이번 실행에서 실제 검색 결과가 생성된 조건은 BM25, Local Hash Vector, Local Hash Hybrid RRF뿐이다. BGE-M3 Vector와 BGE-M3 Hybrid RRF는 모델 가중치 다운로드 실패로 결과 목록과 지표가 없다.

- BM25는 임베딩 호출 없이 키워드 점수만 계산했다.
- Local Hash Vector는 결정적 해시 벡터를 사용했으며 P@10 0.2733, R@10 0.9889, MRR@10 0.9333을 기록했다.
- Local Hash Hybrid RRF는 Hash 벡터와 BM25의 순위를 RRF(K=60, 각 후보 깊이 50)로 결합했으며 P@10 0.2800, R@10 1.0000, MRR@10 0.9667을 기록했다.
- BGE-M3의 개선·악화 질문, 순위, 지연시간, 저장 용량은 측정하지 못했다.

따라서 이번 파일은 BGE-M3가 Local Hash보다 나은지에 대한 결론이 아니라, 비교 파이프라인이 실패를 숨기지 않고 기록했음을 보여주는 실행 기록이다.
