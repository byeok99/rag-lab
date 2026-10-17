import json

from tc_rag import evaluation
from tc_rag.model import TestCase as TC
from tc_rag.providers import build_generation_contract
from tc_rag.storage import Store


def test_generation_contract_contains_the_shared_prompt_schema_and_evidence():
    query = {"scenario": "권한 전이를 검증한다"}
    evidence = [{"record_id": "rec-1", "scenario": "권한을 회수한다"}]

    contract = build_generation_contract(
        query,
        evidence,
        target_count=3,
        condition="G1",
        instructions_version="generation-v1",
        schema_version="candidate-v1",
    )

    assert contract["query"] == query
    assert contract["evidence"] == evidence
    assert contract["target_count"] == 3
    assert contract["condition"] == "G1"
    assert contract["instructions_version"] == "generation-v1"
    assert contract["schema_version"] == "candidate-v1"
    assert contract["output_schema"]["required"] == ["analysis", "candidates"]
    candidate = contract["output_schema"]["properties"]["candidates"]["items"]
    assert "related_record_ids" in candidate["required"]
    assert "requires_confirmation" in candidate["required"]


def test_generation_contract_for_g0_forbids_evidence():
    try:
        build_generation_contract(
            {"scenario": "근거 없는 요청"},
            [{"record_id": "must-not-be-used"}],
            target_count=1,
            condition="G0",
            instructions_version="generation-v1",
            schema_version="candidate-v1",
        )
        assert False, "G0 evidence must be rejected"
    except ValueError as exc:
        assert "G0" in str(exc)


def test_api_and_codex_runs_share_the_exact_contract_hash(tmp_path, monkeypatch):
    store = Store(tmp_path / "db.sqlite")
    store.save_case(TC(record_id="rec-1", project_id="p", product_version="v", scenario="권한 회수", origin="original"))
    dataset = {"dataset_version": "d1", "cases": [{
        "case_id": "case-1", "project_id": "p", "product_version": "v",
        "evaluation_type": "retrieval", "evaluation_purpose": "comparison", "split": "development",
        "user_request": "권한 전이를 검증한다", "relevant_record_ids": [], "hidden_record_ids": [],
        "curated_evidence_ids": [], "generation_criteria": [], "hidden_conditions": [],
        "forbidden_inferences": [], "human_reviewed": True,
    }]}
    config = {"experiment_id": "x", "dataset_version": "d1", "generation": {
        "retrieval_setting": "baseline", "conditions": ["G1"],
        "backends": ["api", "codex"], "repetitions": 1, "target_count": 2,
        "instructions_version": "generation-v1", "schema_version": "candidate-v1",
    }}
    retrieval_output=tmp_path/"retrieval"
    evaluation.run_retrieval(store,dataset,config,retrieval_output)
    retrieval_path=retrieval_output/"retrieval_results.jsonl"
    captured = []

    class FakeLLM:
        name = "fake-api"
        last_usage = {"input_tokens": 10, "output_tokens": 1}

        def generate_contract(self, contract):
            captured.append(contract)
            return {"analysis": [], "candidates": []}

    monkeypatch.setenv("OPENAI_API_KEY", "configured-for-test")
    monkeypatch.setenv("TC_RAG_ALLOW_CODEX_READ_TOOLS", "1")
    monkeypatch.setattr(evaluation, "get_llm", lambda _: FakeLLM())
    monkeypatch.setattr(evaluation, "_codex_executable", lambda: "codex")
    monkeypatch.setattr(evaluation, "_run_codex", lambda contract, plan: captured.append(contract) or {"analysis": [], "candidates": []})

    evaluation.run_generation(store, dataset, config, retrieval_path, tmp_path / "out", execute=True)

    rows = [json.loads(line) for line in (tmp_path / "out" / "generation_results.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["common_input_hash"] == rows[1]["common_input_hash"]
    assert captured[0] == captured[1]
    assert rows[0]["usage"] == {"input_tokens": 10, "output_tokens": 1}
    store.close()
