import json
import csv

from tc_rag.evaluation import (
    _rank_units,
    aggregate,
    collapse_units,
    embedding_text,
    export_review_pack,
    generation_plan,
    metrics,
    report,
    run_retrieval,
    run_generation,
    validate_inputs,
)
from tc_rag.model import TestCase as TC
from tc_rag.cli import main as cli_main
from tc_rag.storage import Store


def test_review_pack_merges_reference_roles_and_includes_no_evidence_case(tmp_path):
    store=Store(tmp_path/"db.sqlite")
    store.save_case(TC(
        record_id="=record", original_tc_id="TC-1", project_id="p", product_version="v",
        category_large="account", category_medium="login", category_small="lock",
        scenario="=danger", preconditions="signed out", inputs="bad password",
        steps=["try login", "retry"], expected_results="locked", origin="original",
    ))
    store.save_case(TC(record_id="final-record",project_id="p",product_version="v",scenario="audit archive expires",origin="original"))
    base={
        "project_id":"p","product_version":"v","evaluation_purpose":"review",
        "split":"development","generation_criteria":["executable"],
        "hidden_record_ids":[],"hidden_conditions":[],"forbidden_inferences":["guess timeout"],
        "human_reviewed":False,
    }
    dataset={"dataset_version":"d1","cases":[
        {**base,"case_id":"with-reference","evaluation_type":"retrieval","user_request":"check lock",
         "relevant_record_ids":["=record"],"curated_evidence_ids":["=record"],
         "relevance_grades":{"=record":2}},
        {**base,"case_id":"no-evidence","evaluation_type":"retrieval","user_request":"unknown feature",
         "relevant_record_ids":[],"curated_evidence_ids":[]},
        {**base,"case_id":"final-hidden","evaluation_type":"retrieval","user_request":"locked final",
         "split":"final","relevant_record_ids":["final-record"],"curated_evidence_ids":[]},
    ]}
    config={"dataset_version":"d1","evaluation_split":"development"}
    output=tmp_path/"review.csv"

    result=export_review_pack(store,dataset,config,output)

    with output.open(encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f))
    assert result == {"output":str(output),"cases":2,"rows":2}
    referenced=next(row for row in rows if row["case_id"]=="with-reference")
    assert referenced["roles"] == "relevant|curated"
    assert referenced["record_id"] == "'=record"
    assert referenced["scenario"] == "'=danger"
    assert referenced["categories"] == "account / login / lock"
    assert referenced["steps"] == "try login\nretry"
    assert referenced["relevance_grade"] == "2"
    assert referenced["generation_criteria"] == '["executable"]'
    assert referenced["human_reviewed"] == "False"
    assert referenced["reviewer_decision"] == referenced["reviewer_notes"] == ""
    empty=next(row for row in rows if row["case_id"]=="no-evidence")
    assert empty["roles"] == "no_evidence" and empty["record_id"] == ""
    store.close()


def test_review_pack_does_not_overwrite_existing_human_work(tmp_path):
    store=Store(tmp_path/"db.sqlite")
    dataset={"dataset_version":"d1","cases":[{
        "case_id":"c","evaluation_type":"retrieval","project_id":"p","product_version":"v",
        "user_request":"q","evaluation_purpose":"x","split":"development","relevant_record_ids":[],
        "curated_evidence_ids":[],"generation_criteria":[],"hidden_record_ids":[],
        "hidden_conditions":[],"forbidden_inferences":[],"human_reviewed":False,
    }]}
    output=tmp_path/"review.csv"; output.write_text("reviewer work",encoding="utf-8")

    try:
        export_review_pack(store,dataset,{"dataset_version":"d1"},output)
        assert False, "review output must not be overwritten"
    except FileExistsError:
        pass
    assert output.read_text(encoding="utf-8") == "reviewer work"
    store.close()


def test_review_pack_refuses_invalid_dataset_without_writing(tmp_path):
    store=Store(tmp_path/"db.sqlite")
    dataset={"dataset_version":"d1","cases":[{"case_id":"incomplete"}]}
    output=tmp_path/"review.csv"

    try:
        export_review_pack(store,dataset,{"dataset_version":"d1"},output)
        assert False, "invalid evaluation data must not be exported"
    except ValueError as exc:
        assert "invalid evaluation inputs" in str(exc)
    assert not output.exists()
    store.close()


def test_review_pack_cli_writes_requested_csv(tmp_path):
    db=tmp_path/"db.sqlite"
    store=Store(db); store.close()
    dataset={"dataset_version":"d1","cases":[{
        "case_id":"c","evaluation_type":"retrieval","project_id":"p","product_version":"v",
        "user_request":"unknown","evaluation_purpose":"no evidence","split":"development",
        "relevant_record_ids":[],"curated_evidence_ids":[],"generation_criteria":[],
        "hidden_record_ids":[],"hidden_conditions":[],"forbidden_inferences":[],"human_reviewed":False,
    }]}
    dataset_path=tmp_path/"dataset.json"; config_path=tmp_path/"config.json"; output=tmp_path/"review.csv"
    dataset_path.write_text(json.dumps(dataset),encoding="utf-8")
    config_path.write_text(json.dumps({"dataset_version":"d1"}),encoding="utf-8")

    exit_code=cli_main(["--db",str(db),"eval","review-pack","--dataset",str(dataset_path),"--config",str(config_path),"--output",str(output)])

    assert exit_code == 0 and output.is_file()


def test_metrics_are_computed_per_original_tc():
    result=metrics(["a","x","b"],{"a","b"},3,{"a":2,"b":1})
    assert result["precision_at_k"] == 2/3
    assert result["recall_at_k"] == 1
    assert result["mrr_at_k"] == 1
    assert round(result["ndcg_at_k"],6) == round((3+1/2)/(3+1/1.584962500721156),6)


def test_duplicate_chunks_do_not_inflate_ranking():
    cases={x:TC(record_id=x) for x in "ab"}
    units=[{"member_ids":["a"],"unit_score":.9,"score_type":"cosine"},{"member_ids":["a"],"unit_score":.8,"score_type":"cosine"},{"member_ids":["b"],"unit_score":.7,"score_type":"cosine"}]
    assert [x["record_id"] for x in collapse_units(units,cases,2)] == ["a","b"]


def test_e1_to_e4_add_only_the_documented_fields():
    tc=TC(category_large="L",category_medium="M",category_small="S",scenario="scenario",preconditions="pre",inputs="input",steps=["step"],expected_results="expected")
    e1=embedding_text(tc,"E1","raw"); e2=embedding_text(tc,"E2","raw"); e3=embedding_text(tc,"E3","raw"); e4=embedding_text(tc,"E4","raw")
    assert "scenario" in e1 and "L" not in e1 and "input" not in e1
    assert all(x in e2 for x in ("L","M","S","scenario")) and "input" not in e2
    assert all(x in e3 for x in ("pre","input")) and "step" not in e3 and "expected" not in e3
    assert all(x in e4 for x in ("step","expected"))


def test_e3_e4_do_not_reembed_raw_input_when_steps_were_split():
    tc=TC(
        category_large="L",scenario="scenario",preconditions="signed in",
        inputs="",steps=["open menu","submit form"],
        raw_input_text="signed in\n1. open menu\n2. submit form",
        expected_results="saved",
    )

    e3=embedding_text(tc,"E3","raw")
    e4=embedding_text(tc,"E4","raw")

    assert "signed in" in e3
    assert "open menu" not in e3 and "submit form" not in e3
    assert e4.count("signed in") == 1
    assert e4.count("open menu") == 1
    assert e4.count("submit form") == 1


def test_hidden_records_cannot_enter_generation_evidence():
    dataset={"cases":[{"case_id":"c","user_request":"q","hidden_record_ids":["secret"],"curated_evidence_ids":[]}]}
    config={"generation":{"backends":["api"],"conditions":["G1"],"repetitions":1}}
    retrieval=[{"case_id":"c","status":"actual","setting":{"name":"baseline"},"context_record_ids":["secret"]}]
    try:
        generation_plan(dataset,config,retrieval)
        assert False, "leak must fail"
    except ValueError as exc:
        assert "leaked" in str(exc)


def test_generation_plan_can_reuse_explicit_mock_retrieval_for_pipeline_checks():
    dataset={"cases":[{"case_id":"c","user_request":"q","hidden_record_ids":[],"curated_evidence_ids":[]}]}
    config={"generation":{"backends":["mock"],"conditions":["G1"],"repetitions":1}}
    retrieval=[{"case_id":"c","status":"mock","execution_mode":"mock","setting":{"name":"baseline"},"context_record_ids":["evidence"]}]

    plan=generation_plan(dataset,config,retrieval)

    assert plan[0]["evidence_record_ids"] == ["evidence"]


def test_generation_defaults_to_g0_g1_and_rejects_g2(tmp_path):
    store=Store(tmp_path/"db.sqlite")
    case={"case_id":"c","evaluation_type":"retrieval","project_id":"p","product_version":"v","user_request":"q","evaluation_purpose":"x","split":"development","relevant_record_ids":[],"curated_evidence_ids":[],"generation_criteria":[],"hidden_record_ids":[],"hidden_conditions":[],"forbidden_inferences":[],"human_reviewed":True}
    retrieval=[{"case_id":"c","status":"mock","execution_mode":"mock","setting":{"name":"baseline"},"context_record_ids":["evidence"]}]

    plan=generation_plan({"cases":[case]},{"generation":{"backends":["mock"],"repetitions":1}},retrieval)
    validation=validate_inputs(store,{"dataset_version":"d1","cases":[case]},{"dataset_version":"d1","generation":{"backends":["mock"],"conditions":["G2"]}})

    assert {item["condition"] for item in plan} == {"G0","G1"}
    assert any("G0 or G1" in error for error in validation["errors"])
    store.close()


def test_failed_and_not_run_are_not_aggregated():
    good={"status":"actual","setting":{"name":"baseline"},"metrics":{"precision_at_k":1,"recall_at_k":1,"mrr_at_k":1,"ndcg_at_k":None,"relevant_count":1},"duration_seconds":1}
    summary=aggregate([good,{"status":"failed"},{"status":"not_run"}])
    assert summary["settings"]["baseline"]["cases"] == 1
    assert summary["excluded_from_relevance_metrics"] == 2


def test_actual_and_mock_retrieval_metrics_are_aggregated_separately():
    metric={"precision_at_k":1,"recall_at_k":1,"mrr_at_k":1,"ndcg_at_k":None,"relevant_count":1}
    rows=[
        {"status":"actual","execution_mode":"actual","setting":{"name":"baseline"},"metrics":metric,"duration_seconds":1},
        {"status":"mock","execution_mode":"mock","setting":{"name":"baseline"},"metrics":metric,"duration_seconds":2},
        {"status":"failed","execution_mode":"actual","setting":{"name":"baseline"},"metrics":metric,"duration_seconds":3},
    ]
    summary=aggregate(rows)
    assert summary["settings_by_execution_mode"]["actual"]["baseline"]["cases"] == 1
    assert summary["settings_by_execution_mode"]["mock"]["baseline"]["cases"] == 1
    assert summary["excluded_from_relevance_metrics"] == 1


def test_vector_lexical_rerank_calculates_keyword_scores_for_full_pool():
    class Embedder:
        name="test"; dimension=2
        def embed(self,texts):
            return [[1,0]] if len(texts)==1 else [[1-i/100,0] for i in range(len(texts))]

    units=[{"member_ids":[str(i)],"text":"needle" if i==19 else f"other {i}"} for i in range(20)]
    setting={"search_method":"vector","candidate_k":20,"rerank":"lexical-20","rrf_k":60,"selection":"similarity","mmr_lambda":.7}
    ranked,_,_=_rank_units(Embedder(),["needle"],units,setting)
    assert ranked[0]["member_ids"] == ["19"]


def test_hybrid_rrf_uses_only_top_candidates_and_excludes_zero_keyword_scores():
    class Embedder:
        name="test"; dimension=2
        def embed(self,texts):
            if len(texts)==1:
                return [[1,0]]
            return [[0,0]]+[[1-i/100,0] for i in range(1,len(texts))]

    units=[{"member_ids":[str(i)],"text":"needle" if i==0 else f"other {i}"} for i in range(30)]
    setting={"search_method":"hybrid","candidate_k":20,"rerank":"none","rrf_k":60,"selection":"similarity","mmr_lambda":.7}
    ranked,_,_=_rank_units(Embedder(),["needle"],units,setting)
    scores={item["member_ids"][0]:item["initial_score"] for item in ranked}

    assert scores["0"] == 1/61
    assert scores["1"] == 1/61


def test_hybrid_rrf_source_depth_is_independent_from_rerank_candidate_pool():
    class Embedder:
        name="test"; dimension=2
        def embed(self,texts):
            if len(texts)==1:
                return [[1,0]]
            return [[1-i/100,0] for i in range(len(texts))]

    units=[{"member_ids":[str(i)],"text":"needle" if i==25 else f"other {i}"} for i in range(30)]
    setting={"search_method":"hybrid","candidate_k":30,"rrf_candidate_k":20,"rerank":"none","rrf_k":60,"selection":"similarity","mmr_lambda":.7}
    ranked,_,_=_rank_units(Embedder(),["needle"],units,setting)
    scores={item["member_ids"][0]:item["initial_score"] for item in ranked}

    assert scores["25"] == 1/61


def test_validation_rejects_unsafe_setting_ranges_and_reference_scope(tmp_path):
    store=Store(tmp_path/"db.sqlite")
    store.save_case(TC(record_id="foreign",project_id="other",product_version="v2",scenario="x"))
    dataset={"dataset_version":"d1","cases":[{
        "case_id":"c","evaluation_type":"retrieval","project_id":"p","product_version":"v",
        "user_request":"q","evaluation_purpose":"normal","split":"development",
        "relevant_record_ids":["foreign"],"curated_evidence_ids":[],"generation_criteria":[],
        "hidden_record_ids":[],"hidden_conditions":[],"forbidden_inferences":[],"human_reviewed":True,
    }]}
    config={"dataset_version":"d1","baseline":{"embedding_provider":"bogus","rerank":"lexical-50","candidate_k":20,"filters":"answer_key","selection":"mmr","mmr_lambda":1.1}}
    result=validate_inputs(store,dataset,config)
    assert any("project/product version" in error for error in result["errors"])
    assert any("embedding_provider" in error for error in result["errors"])
    assert any("candidate_k" in error for error in result["errors"])
    assert any("filters" in error for error in result["errors"])
    assert any("mmr_lambda" in error for error in result["errors"])
    store.close()


def test_validation_rejects_auto_provider_to_prevent_silent_mock_fallback(tmp_path):
    store=Store(tmp_path/"db.sqlite")
    dataset={"dataset_version":"d1","cases":[{
        "case_id":"c","evaluation_type":"retrieval","project_id":"p","product_version":"v",
        "user_request":"q","evaluation_purpose":"normal","split":"development",
        "relevant_record_ids":[],"curated_evidence_ids":[],"generation_criteria":[],
        "hidden_record_ids":[],"hidden_conditions":[],"forbidden_inferences":[],"human_reviewed":True,
    }]}

    result=validate_inputs(store,dataset,{"dataset_version":"d1","baseline":{"embedding_provider":"auto"}})

    assert any("embedding_provider" in error and "explicit" in error for error in result["errors"])
    store.close()


def test_validation_requires_complete_case_fields_and_rejects_rediscovery_leak(tmp_path):
    store=Store(tmp_path/"db.sqlite")
    store.save_case(TC(record_id="hidden",project_id="p",product_version="v",scenario="x"))
    incomplete={"dataset_version":"d1","cases":[{"case_id":"c","project_id":"p","product_version":"v","user_request":"q","evaluation_purpose":"x","split":"development"}]}
    result=validate_inputs(store,incomplete,{"dataset_version":"d1"})
    assert any("generation_criteria" in error for error in result["errors"])
    leaked={"dataset_version":"d1","cases":[{
        "case_id":"c","evaluation_type":"rediscovery","project_id":"p","product_version":"v",
        "user_request":"q","evaluation_purpose":"x","split":"development",
        "relevant_record_ids":["hidden"],"curated_evidence_ids":["hidden"],"generation_criteria":[],
        "hidden_record_ids":["hidden"],"hidden_conditions":["condition"],"forbidden_inferences":[],"human_reviewed":True,
    }]}
    result=validate_inputs(store,leaked,{"dataset_version":"d1"})
    assert any("hidden" in error and "curated" in error for error in result["errors"])
    assert any("hidden" in error and "relevant" in error for error in result["errors"])
    store.close()


def test_validation_rejects_similar_tc_labels_across_dataset_splits(tmp_path):
    store=Store(tmp_path/"db.sqlite")
    store.save_case(TC(record_id="dev",project_id="p",product_version="v",category_large="계정",scenario="사용자 계정을 잠금하고 로그인을 차단한다"))
    store.save_case(TC(record_id="final",project_id="p",product_version="v",category_large="계정",scenario="사용자 계정을 잠금하고 로그인을 차단함"))
    base={"project_id":"p","product_version":"v","user_request":"q","evaluation_purpose":"x","curated_evidence_ids":[],"generation_criteria":[],"hidden_record_ids":[],"hidden_conditions":[],"forbidden_inferences":[],"human_reviewed":True}
    dataset={"dataset_version":"d1","cases":[
        {**base,"case_id":"a","evaluation_type":"retrieval","split":"development","relevant_record_ids":["dev"]},
        {**base,"case_id":"b","evaluation_type":"retrieval","split":"final","relevant_record_ids":["final"]},
    ]}

    result=validate_inputs(store,dataset,{"dataset_version":"d1"})

    assert any("similar records" in error for error in result["errors"])
    store.close()


def test_retrieval_pipeline_writes_separate_experiment_index(tmp_path):
    store=Store(tmp_path/"db.sqlite")
    relevant=TC(record_id="r1",project_id="p",product_version="v",scenario="online index creation",inputs="concurrent update",expected_results="updated row remains searchable",origin="original")
    unrelated=TC(record_id="r2",project_id="p",product_version="v",scenario="account login",origin="original")
    store.save_case(relevant); store.save_case(unrelated)
    dataset={"dataset_version":"d1","cases":[{"case_id":"c1","evaluation_type":"retrieval","project_id":"p","product_version":"v","user_request":"online index concurrent update","evaluation_purpose":"normal","split":"development","relevant_record_ids":["r1"],"curated_evidence_ids":["r1"],"generation_criteria":[],"hidden_record_ids":[],"hidden_conditions":[],"forbidden_inferences":[],"human_reviewed":True}]}
    config={"experiment_id":"x1","dataset_version":"d1","baseline":{"top_k":3,"context_token_budget":2000}}
    result=run_retrieval(store,dataset,config,tmp_path/"out")
    row=json.loads((tmp_path/"out"/"retrieval_results.jsonl").read_text().splitlines()[0])
    assert result["new_runs"] == 1 and row["retrieval_results"][0]["record_id"] == "r1"
    assert row["status"] == row["execution_mode"] == "mock"
    assert row["index_version"].startswith("exp:x1:")
    assert store.db.execute("SELECT count(*) FROM vector_index WHERE index_version=?",(row["index_version"],)).fetchone()[0] == 2
    store.close()


def test_retrieval_embeds_shared_document_index_once_per_setting(tmp_path,monkeypatch):
    store=Store(tmp_path/"db.sqlite")
    store.save_case(TC(record_id="r1",project_id="p",product_version="v",scenario="alpha",origin="original"))
    store.save_case(TC(record_id="r2",project_id="p",product_version="v",scenario="beta",origin="original"))
    base={"evaluation_type":"retrieval","project_id":"p","product_version":"v","evaluation_purpose":"normal","split":"development","curated_evidence_ids":[],"generation_criteria":[],"hidden_record_ids":[],"hidden_conditions":[],"forbidden_inferences":[],"human_reviewed":True}
    dataset={"dataset_version":"d1","cases":[
        {**base,"case_id":"c1","user_request":"alpha","relevant_record_ids":["r1"]},
        {**base,"case_id":"c2","user_request":"beta","relevant_record_ids":["r2"]},
    ]}
    config={"experiment_id":"x1","dataset_version":"d1","baseline":{"top_k":3,"context_token_budget":2000}}

    class CountingEmbedder:
        name="counting"; dimension=2
        def __init__(self): self.batch_sizes=[]
        def embed(self,texts):
            self.batch_sizes.append(len(texts))
            return [[1.0,0.0] if "alpha" in text else [0.0,1.0] for text in texts]

    embedder=CountingEmbedder()
    monkeypatch.setattr("tc_rag.evaluation.get_embedder",lambda _:embedder)

    run_retrieval(store,dataset,config,tmp_path/"out")

    rows=[json.loads(line) for line in (tmp_path/"out"/"retrieval_results.jsonl").read_text().splitlines()]
    assert embedder.batch_sizes == [2,1,1]
    assert rows[0]["index_version"] == rows[1]["index_version"]
    store.close()


def test_retrieval_hash_changes_with_dataset_case_and_term_map(tmp_path):
    store=Store(tmp_path/"db.sqlite")
    store.save_case(TC(record_id="r1",project_id="p",product_version="v",scenario="alpha",origin="original"))
    case={"case_id":"c1","evaluation_type":"retrieval","project_id":"p","product_version":"v","user_request":"alpha","evaluation_purpose":"normal","split":"development","relevant_record_ids":["r1"],"curated_evidence_ids":[],"generation_criteria":[],"hidden_record_ids":[],"hidden_conditions":[],"forbidden_inferences":[],"human_reviewed":True}
    dataset1={"dataset_version":"d1","cases":[case]}; config1={"experiment_id":"x","dataset_version":"d1","term_map":{"alpha":"a"},"baseline":{"top_k":3,"context_token_budget":2000}}
    run_retrieval(store,dataset1,config1,tmp_path/"one")
    row1=json.loads((tmp_path/"one"/"retrieval_results.jsonl").read_text())
    dataset2={"dataset_version":"d2","cases":[{**case,"evaluation_purpose":"changed label"}]}; config2={**config1,"dataset_version":"d2","term_map":{"alpha":"b"}}
    run_retrieval(store,dataset2,config2,tmp_path/"two")
    row2=json.loads((tmp_path/"two"/"retrieval_results.jsonl").read_text())
    assert row1["task_id"] != row2["task_id"]
    assert row1["index_version"] != row2["index_version"]
    store.close()


def test_retrieval_records_identical_initial_candidates_for_rerank_comparison(tmp_path):
    store=Store(tmp_path/"db.sqlite")
    for i in range(25):
        store.save_case(TC(record_id=f"r{i}",project_id="p",product_version="v",scenario=f"alpha case {i}",origin="original"))
    case={"case_id":"c1","evaluation_type":"retrieval","project_id":"p","product_version":"v","user_request":"alpha","evaluation_purpose":"rerank","split":"development","relevant_record_ids":["r0"],"curated_evidence_ids":[],"generation_criteria":[],"hidden_record_ids":[],"hidden_conditions":[],"forbidden_inferences":[],"human_reviewed":True}
    dataset={"dataset_version":"d1","cases":[case]}
    config={"experiment_id":"rerank","dataset_version":"d1","evaluation_split":"development","baseline":{"search_method":"hybrid","top_k":10,"candidate_k":20,"rrf_candidate_k":50,"rerank":"none","context_token_budget":4000},"experiments":[{"name":"rerank-20","rerank":"lexical-20"},{"name":"rerank-50","candidate_k":50,"rerank":"lexical-50"}]}

    run_retrieval(store,dataset,config,tmp_path/"out")

    rows=[json.loads(line) for line in (tmp_path/"out"/"retrieval_results.jsonl").read_text().splitlines()]
    assert len(rows[0]["candidate_record_ids"]) == 20
    assert rows[0]["candidate_record_ids"] == rows[1]["candidate_record_ids"]
    assert rows[0]["candidate_record_ids"] == rows[2]["candidate_record_ids"][:20]
    store.close()


def test_report_labels_mock_retrieval_separately(tmp_path):
    results=tmp_path/"results"; results.mkdir()
    row={"status":"mock","execution_mode":"mock","setting":{"name":"baseline"},"metrics":{"precision_at_k":.2,"recall_at_k":.5,"mrr_at_k":1,"ndcg_at_k":None,"relevant_count":1},"duration_seconds":.1}
    (results/"retrieval_results.jsonl").write_text(json.dumps(row)+"\n",encoding="utf-8")
    (results/"generation_results.jsonl").write_text("",encoding="utf-8")

    report(results,tmp_path/"report.md")

    text=(tmp_path/"report.md").read_text(encoding="utf-8")
    assert "Actual retrieval" in text
    assert "Mock retrieval" in text
    assert "Generation runs: 0 (retrieval-only; generation was not scheduled)" in text
    assert "Generation not-run or failed: 0" not in text


def test_generation_validation_rejects_unknown_backend_and_condition(tmp_path):
    store=Store(tmp_path/"db.sqlite")
    dataset={"dataset_version":"d1","cases":[{"case_id":"c","evaluation_type":"retrieval","project_id":"p","product_version":"v","user_request":"q","evaluation_purpose":"x","split":"development","relevant_record_ids":[],"curated_evidence_ids":[],"generation_criteria":[],"hidden_record_ids":[],"hidden_conditions":[],"forbidden_inferences":[],"human_reviewed":True}]}
    config={"dataset_version":"d1","generation":{"backends":["typo"],"conditions":["G9"],"repetitions":0,"target_count":999}}

    result=validate_inputs(store,dataset,config)

    assert any("generation.backends" in error for error in result["errors"])
    assert any("generation.conditions" in error for error in result["errors"])
    assert any("generation.repetitions" in error for error in result["errors"])
    assert any("generation.target_count" in error for error in result["errors"])
    store.close()


def test_generation_fails_when_g1_retrieval_artifact_is_missing(tmp_path):
    store=Store(tmp_path/"db.sqlite")
    dataset={"dataset_version":"d1","cases":[{"case_id":"c","evaluation_type":"retrieval","project_id":"p","product_version":"v","user_request":"q","evaluation_purpose":"x","split":"development","relevant_record_ids":[],"curated_evidence_ids":[],"generation_criteria":[],"hidden_record_ids":[],"hidden_conditions":[],"forbidden_inferences":[],"human_reviewed":True}]}
    config={"experiment_id":"x","dataset_version":"d1","generation":{"backends":["api"],"conditions":["G1"],"repetitions":1,"target_count":1}}
    retrieval=tmp_path/"retrieval.jsonl"; retrieval.write_text("",encoding="utf-8")

    try:
        run_generation(store,dataset,config,retrieval,tmp_path/"out")
        assert False, "G1 must not silently run without a retrieval artifact"
    except ValueError as exc:
        assert "G1" in str(exc)
    store.close()
