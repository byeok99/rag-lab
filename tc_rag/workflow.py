from __future__ import annotations

import json, math, random, re, time
from difflib import SequenceMatcher
from typing import Any

from .model import TestCase, embedding_text, new_id
from .providers import Embedder, LLM
from .storage import Store, now
from .util import canonical, sha256_text, stable_json


def make_split(store: Store, project: str, version: str, split_version: str, holdout: float = .2, seed: int = 42) -> dict[str, int]:
    cases = [tc for tc in store.list_cases(project, version) if tc.origin != "generated"]
    groups: list[list[TestCase]] = []
    for tc in cases:
        signature = canonical(" ".join((tc.category_large, tc.category_medium, tc.category_small, tc.scenario)))
        for group in groups:
            other = canonical(" ".join((group[0].category_large, group[0].category_medium, group[0].category_small, group[0].scenario)))
            if signature == other or SequenceMatcher(None, signature, other).ratio() >= .88:
                group.append(tc); break
        else: groups.append([tc])
    random.Random(seed).shuffle(groups)
    target = round(len(cases) * holdout); held = 0
    store.db.execute("""DELETE FROM splits WHERE split_version=? AND record_id IN
        (SELECT record_id FROM test_cases WHERE project_id=? AND product_version=?)""",
        (split_version, project, version))
    for i, group in enumerate(groups):
        partition = "evaluation" if held < target else "development"
        if partition == "evaluation": held += len(group)
        gid = f"grp_{i:05d}"
        store.db.executemany("INSERT INTO splits VALUES(?,?,?,?,?)", [(split_version, tc.record_id, partition, gid, now()) for tc in group])
    store.db.commit()
    return {"development": len(cases) - held, "evaluation": held, "groups": len(groups)}


def build_index(store: Store, embedder: Embedder, project: str, version: str, index_version: str, split_version: str | None = None, include_approved_generated: bool = False) -> dict[str, Any]:
    cases = store.list_cases(project, version)
    if split_version:
        allowed = {r[0] for r in store.db.execute("SELECT record_id FROM splits WHERE split_version=? AND partition='development'", (split_version,))}
        cases = [tc for tc in cases if tc.record_id in allowed]
    cases = [tc for tc in cases if tc.origin != "generated" or (include_approved_generated and tc.review_status == "approved")]
    texts = [embedding_text(tc) for tc in cases]
    vectors = embedder.embed(texts) if texts else []
    store.db.execute("""DELETE FROM vector_index WHERE index_version=? AND record_id IN
        (SELECT record_id FROM test_cases WHERE project_id=? AND product_version=?)""",
        (index_version, project, version))
    for tc, vector in zip(cases, vectors):
        source = tc.source_refs[0] if tc.source_refs else {}
        metadata = {"record_id":tc.record_id,"project_id":tc.project_id,"product_version":tc.product_version,"category_large":tc.category_large,"category_medium":tc.category_medium,"category_small":tc.category_small,"origin":tc.origin,"source_document_id":source.get("source_document_id", ""),"source":source,"data_version":split_version or "all"}
        store.db.execute("INSERT INTO vector_index VALUES(?,?,?,?,?,?,?,?,?)", (index_version,tc.record_id,f"{tc.record_id}:0",embedder.name,len(vector),"fields-v1",json.dumps(vector),stable_json(metadata),now()))
    store.db.commit()
    return {"indexed":len(cases),"index_version":index_version,"model":embedder.name,"dimension":embedder.dimension,"mode":"real" if embedder.name != "local-hash-v1" else "mock/local"}


def search(store: Store, embedder: Embedder, query: str, project: str, version: str, index_version: str, top_k: int = 5, cross_project: bool = False) -> list[dict[str, Any]]:
    q = embedder.embed([query])[0]
    rows = store.db.execute("SELECT * FROM vector_index WHERE index_version=? AND model=? AND dimension=?", (index_version,embedder.name,len(q))).fetchall()
    results = []
    for row in rows:
        meta=json.loads(row["metadata_json"])
        if not cross_project and (meta["project_id"] != project or meta["product_version"] != version): continue
        vector=json.loads(row["vector_json"]); score=sum(a*b for a,b in zip(q,vector))
        tc=store.get(row["record_id"])
        if tc: results.append({**tc.to_dict(),"score":round(score,6),"score_type":"cosine_similarity","cross_project_reference":meta["project_id"] != project})
    results.sort(key=lambda x:x["score"], reverse=True)
    return results[:top_k]


def validate_candidate(data: dict[str, Any], evidence_ids: set[str]) -> list[str]:
    errors=[]
    if not str(data.get("scenario","")).strip(): errors.append("empty scenario")
    steps=data.get("steps")
    if not isinstance(steps,list) or not any(str(x).strip() for x in steps): errors.append("empty steps")
    related=data.get("related_record_ids",[])
    if not isinstance(related,list) or any(x not in evidence_ids for x in related): errors.append("invalid evidence record_id")
    basis=data.get("expected_result_basis","unknown"); confirmation=bool(data.get("requires_confirmation"))
    if basis == "unknown" and not confirmation: errors.append("unknown expectation must require confirmation")
    if not data.get("expected_results") and not confirmation: errors.append("missing expectation must require confirmation")
    return errors


def generate(store: Store, llm: LLM, query: dict[str, Any], contexts: list[dict[str, Any]]) -> dict[str, Any]:
    started=time.perf_counter(); output=llm.analyze_and_generate(query,contexts)
    evidence={x["record_id"] for x in contexts}; accepted=[]; failed=[]
    for data in output.get("candidates",[]):
        errors=validate_candidate(data,evidence)
        if errors: failed.append({"candidate":data,"errors":errors}); continue
        tc=TestCase.from_dict(data); tc.record_id=new_id("gen"); tc.generated_tc_id=store.next_tc_id(query["project_id"])
        tc.project_id=query["project_id"]; tc.product_version=query["product_version"]; tc.origin="generated"; tc.review_status="candidate"
        tc.test_result=""; tc.detailed_test_result=""; store.save_case(tc); accepted.append(tc.to_dict())
    return {"analysis":output.get("analysis",[]),"candidates":accepted,"validation_failures":failed,"provider":llm.name,"duration_seconds":round(time.perf_counter()-started,3),"retrieved_record_ids":list(evidence),"notice":output.get("notice","")}


def exact_and_suspected_duplicates(candidate: TestCase, cases: list[TestCase]) -> dict[str, list[str]]:
    target=canonical(" ".join((candidate.scenario,candidate.raw_input_text or " ".join(candidate.steps),candidate.expected_results or "")))
    exact=[]; suspected=[]
    for tc in cases:
        if tc.record_id == candidate.record_id: continue
        other=canonical(" ".join((tc.scenario,tc.raw_input_text or " ".join(tc.steps),tc.expected_results or "")))
        ratio=SequenceMatcher(None,target,other).ratio()
        if target and target==other: exact.append(tc.record_id)
        elif ratio >= .82: suspected.append(tc.record_id)
    return {"exact":exact,"suspected_semantic":suspected}

