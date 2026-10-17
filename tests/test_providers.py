import json

from tc_rag import providers


def test_hash_embedder_is_deterministic_and_normalized():
    embedder=providers.HashEmbedder(32)
    first,second=embedder.embed(["한글 SQL test","한글 SQL test"])
    assert first == second
    assert round(sum(value*value for value in first),8) == 1


def test_openai_embedder_uses_configured_model_and_actual_dimension(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY","secret-for-test")
    monkeypatch.setenv("TC_RAG_EMBEDDING_MODEL","embedding-test")
    captured={}

    def fake_post(url,key,payload):
        captured.update(url=url,key=key,payload=payload)
        return {"data":[{"index":0,"embedding":[0.1,0.2]}]}

    monkeypatch.setattr(providers,"_post",fake_post)
    embedder=providers.OpenAICompatibleEmbedder()

    assert embedder.embed(["query"]) == [[0.1,0.2]]
    assert embedder.dimension == 2
    assert captured["key"] == "secret-for-test"
    assert captured["payload"] == {"model":"embedding-test","input":["query"]}


def test_openai_llm_uses_contract_schema_and_records_usage(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY","secret-for-test")
    captured={}

    def fake_post(url,key,payload):
        captured.update(payload=payload)
        return {"id":"response-1","usage":{"input_tokens":12,"output_tokens":3},"output_text":json.dumps({"analysis":[],"candidates":[]})}

    monkeypatch.setattr(providers,"_post",fake_post)
    contract=providers.build_generation_contract({"scenario":"q"},[],target_count=2,condition="G0",instructions_version="v1",schema_version="s1")
    llm=providers.OpenAICompatibleLLM()

    assert llm.generate_contract(contract) == {"analysis":[],"candidates":[]}
    assert captured["payload"]["text"]["format"]["schema"] == contract["output_schema"]
    assert captured["payload"]["text"]["format"]["strict"] is True
    assert llm.last_usage == {"input_tokens":12,"output_tokens":3}
    assert llm.last_response_id == "response-1"


def test_unknown_provider_modes_fail_closed():
    for factory in (providers.get_embedder,providers.get_llm):
        try:
            factory("typo")
            assert False, "unknown providers must not silently become mock"
        except ValueError as exc:
            assert "unsupported" in str(exc)
