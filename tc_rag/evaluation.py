from __future__ import annotations

import csv, functools, hashlib, json, math, os, re, shutil, statistics, subprocess, time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .model import TestCase
from .providers import build_generation_contract, get_embedder, get_llm
from .storage import Store, now
from .util import canonical, safe_cell, stable_json
from .workflow import validate_candidate


DEFAULTS = {
    "embedding_input": "E4", "search_unit": "C1", "search_method": "vector",
    "top_k": 5, "candidate_k": 20, "rerank": "none", "query_mode": "Q1",
    "selection": "similarity", "mmr_lambda": .7, "filters": "project_version",
    "context_token_budget": 4000, "preprocess": "whitespace", "chunk_chars": 2000,
    "chunk_overlap": 200, "group_size": 5, "rrf_k": 60, "rrf_candidate_k": 50,
    "embedding_provider": "mock", "embedding_model": "local-hash-v1",
    "model_revision": None, "dimension": 384, "device": "cpu", "batch_size": 16,
    "normalize_embeddings": True, "max_seq_length": None, "model_cache_dir": None,
    "vector_index_version": None,
}
REQUIRED_CASE = {
    "case_id", "project_id", "product_version", "user_request", "evaluation_purpose",
    "relevant_record_ids", "curated_evidence_ids", "generation_criteria",
    "hidden_record_ids", "hidden_conditions", "forbidden_inferences", "split",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def export_review_pack(store: Store, dataset: dict[str,Any], config: dict[str,Any], output: Path) -> dict[str,Any]:
    validation=validate_inputs(store,dataset,config)
    if not validation["valid"]: raise ValueError("invalid evaluation inputs: "+"; ".join(validation["errors"]))
    if output.exists(): raise FileExistsError(f"review pack already exists: {output}")
    fields=("case_id","split","evaluation_type","evaluation_purpose","user_request","roles","record_id","original_tc_id","categories","scenario","preconditions","inputs","steps","expected","relevance_grade","hidden_conditions","generation_criteria","forbidden_inferences","human_reviewed","reviewer_decision","reviewer_notes")
    selected=[case for case in dataset["cases"] if not config.get("evaluation_split") or case.get("split")==config["evaluation_split"]]
    rows=[]
    for case in selected:
        roles: dict[str,list[str]]=defaultdict(list)
        for role,key in (("relevant","relevant_record_ids"),("curated","curated_evidence_ids"),("hidden","hidden_record_ids")):
            for record_id in case[key]: roles[record_id].append(role)
        for record_id,record_roles in roles.items():
            tc=store.get(record_id)
            rows.append(_review_row(case,"|".join(record_roles),tc,case.get("relevance_grades",{}).get(record_id)))
        if not roles: rows.append(_review_row(case,"no_evidence",None,None))
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=fields); writer.writeheader()
        writer.writerows({key:safe_cell(value) for key,value in row.items()} for row in rows)
    return {"output":str(output),"cases":len(selected),"rows":len(rows)}


def _review_row(case: dict[str,Any], roles: str, tc: TestCase|None, grade: Any) -> dict[str,Any]:
    tc=tc or TestCase(record_id="")
    return {
        "case_id":case["case_id"],"split":case["split"],"evaluation_type":case.get("evaluation_type","retrieval"),
        "evaluation_purpose":case["evaluation_purpose"],"user_request":case["user_request"],"roles":roles,
        "record_id":tc.record_id,"original_tc_id":tc.original_tc_id,
        "categories":" / ".join(x for x in (tc.category_large,tc.category_medium,tc.category_small) if x),
        "scenario":tc.scenario,"preconditions":tc.preconditions,"inputs":tc.inputs or tc.raw_input_text,
        "steps":"\n".join(tc.steps),"expected":tc.expected_results or tc.raw_expected_output_text,
        "relevance_grade":grade,"hidden_conditions":stable_json(case["hidden_conditions"]),
        "generation_criteria":stable_json(case["generation_criteria"]),"forbidden_inferences":stable_json(case["forbidden_inferences"]),
        "human_reviewed":case.get("human_reviewed",False),"reviewer_decision":"","reviewer_notes":"",
    }


def sha(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode()).hexdigest()


def validate_inputs(store: Store, dataset: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    errors, warnings = [], []
    cases = dataset.get("cases")
    if not dataset.get("dataset_version"): errors.append("dataset_version is required")
    if not isinstance(cases, list) or not cases: errors.append("cases must be a non-empty array"); cases=[]
    ids = [c.get("case_id") for c in cases]
    if len(ids) != len(set(ids)): errors.append("case_id must be unique")
    known = {tc.record_id:tc for tc in store.list_cases()}
    split_groups: dict[str, set[str]] = defaultdict(set)
    for i, case in enumerate(cases):
        prefix=f"cases[{i}]"
        missing=REQUIRED_CASE-set(case)
        if missing: errors.append(f"{prefix}: missing {sorted(missing)}")
        for field in ("case_id","project_id","product_version","user_request","evaluation_purpose","split"):
            if not isinstance(case.get(field),str) or not case.get(field," ").strip(): errors.append(f"{prefix}.{field} must be a non-empty string")
        list_fields=("relevant_record_ids","curated_evidence_ids","generation_criteria","hidden_record_ids","hidden_conditions","forbidden_inferences")
        for field in list_fields:
            if field in case and not isinstance(case[field],list): errors.append(f"{prefix}.{field} must be an array")
        if "relevance_grades" in case and not isinstance(case["relevance_grades"],dict): errors.append(f"{prefix}.relevance_grades must be an object")
        kind=case.get("evaluation_type","retrieval")
        if kind not in {"retrieval","rediscovery"}: errors.append(f"{prefix}: invalid evaluation_type")
        relevant=set(case.get("relevant_record_ids",[]) if isinstance(case.get("relevant_record_ids",[]),list) else []); hidden=set(case.get("hidden_record_ids",[]) if isinstance(case.get("hidden_record_ids",[]),list) else []); curated=set(case.get("curated_evidence_ids",[]) if isinstance(case.get("curated_evidence_ids",[]),list) else []); graded=set(case.get("relevance_grades",{}) if isinstance(case.get("relevance_grades",{}),dict) else {})
        referenced=relevant|hidden|curated|graded
        absent=referenced-known.keys()
        if absent: errors.append(f"{prefix}: unknown record IDs {sorted(absent)}")
        wrong_scope=sorted(rid for rid in referenced & known.keys() if (known[rid].project_id,known[rid].product_version)!=(case.get("project_id"),case.get("product_version")))
        if wrong_scope: errors.append(f"{prefix}: referenced records must match case project/product version: {wrong_scope}")
        generated=sorted(rid for rid in referenced & known.keys() if known[rid].origin=="generated")
        if generated: errors.append(f"{prefix}: labels and evidence must reference original TC records: {generated}")
        if graded-relevant: errors.append(f"{prefix}: relevance_grades IDs must also be relevant_record_ids")
        if kind=="retrieval" and hidden: errors.append(f"{prefix}: retrieval case cannot hide records")
        if kind=="rediscovery" and not hidden: errors.append(f"{prefix}: rediscovery case requires hidden_record_ids")
        if kind=="rediscovery" and relevant: errors.append(f"{prefix}: rediscovery case cannot define retrieval relevant_record_ids")
        if kind=="rediscovery" and not case.get("hidden_conditions"): errors.append(f"{prefix}: rediscovery case requires hidden_conditions")
        if hidden & curated: errors.append(f"{prefix}: hidden records leaked into curated evidence")
        if hidden & relevant: errors.append(f"{prefix}: hidden records cannot also be relevant retrieval labels")
        if not case.get("human_reviewed",False): warnings.append(f"{prefix}: labels are a draft until human_reviewed=true")
        for rid in relevant|hidden: split_groups[rid].add(case.get("split",""))
    leaked=[rid for rid,parts in split_groups.items() if len(parts)>1]
    if leaked: errors.append(f"records appear in multiple dataset splits: {leaked[:10]}")
    labeled=list(split_groups)
    for index,left_id in enumerate(labeled):
        left=known[left_id]; left_text=canonical(" ".join((left.category_large,left.category_medium,left.category_small,left.scenario)))
        for right_id in labeled[index+1:]:
            if split_groups[left_id]==split_groups[right_id]: continue
            right=known[right_id]; right_text=canonical(" ".join((right.category_large,right.category_medium,right.category_small,right.scenario)))
            if left_text==right_text or SequenceMatcher(None,left_text,right_text).ratio()>=.88:
                errors.append(f"similar records appear in multiple dataset splits: {left_id}, {right_id}")
    baseline={**DEFAULTS,**config.get("baseline",{})}
    errors += _validate_setting(baseline,"baseline")
    for i, variant in enumerate(config.get("experiments",[])):
        errors += _validate_setting({**baseline,**variant},f"experiments[{i}]")
    if config.get("dataset_version") and config["dataset_version"] != dataset.get("dataset_version"):
        errors.append("config dataset_version does not match dataset")
    generation=config.get("generation",{})
    backends=generation.get("backends",[]); conditions=generation.get("conditions",["G0","G1"])
    if not isinstance(backends,list) or not set(backends)<= {"api","codex","mock"}: errors.append("generation.backends must contain only api, codex, or mock")
    if not isinstance(conditions,list) or not set(conditions)<= {"G0","G1"}: errors.append("generation.conditions must contain only G0 or G1")
    try: repetitions=int(generation.get("repetitions",3))
    except (TypeError,ValueError): repetitions=0
    try: target_count=int(generation.get("target_count",5))
    except (TypeError,ValueError): target_count=0
    if not 1 <= repetitions <= 20: errors.append("generation.repetitions must be between 1 and 20")
    if not 1 <= target_count <= 50: errors.append("generation.target_count must be between 1 and 50")
    return {"valid":not errors,"errors":errors,"warnings":warnings,"cases":len(cases),"dataset_version":dataset.get("dataset_version")}


def _validate_setting(s: dict[str,Any], name: str) -> list[str]:
    errors=[]
    allowed={"embedding_input":{"E1","E2","E3","E4"},"search_unit":{"C1","C2","C3"},"search_method":{"vector","keyword","hybrid"},"query_mode":{"Q1","Q2","Q3","Q4"},"selection":{"similarity","mmr"},"preprocess":{"raw","whitespace","terms"},"embedding_provider":{"mock","openai","local","sentence-transformers"},"rerank":{"none","lexical-20","lexical-50"},"filters":{"project_version","category_large","category_medium"}}
    for key,values in allowed.items():
        if s.get(key) not in values: errors.append(f"{name}.{key} must be one of {sorted(values)}")
    if s.get("embedding_provider")=="auto": errors.append(f"{name}.embedding_provider must be explicit; auto can silently fall back to mock")
    if s.get("embedding_provider") in {"local", "sentence-transformers"} and not str(s.get("embedding_model") or "").strip(): errors.append(f"{name}.embedding_model is required for local embeddings")
    for key in ("dimension", "batch_size"):
        try:
            if int(s.get(key, 0)) <= 0: errors.append(f"{name}.{key} must be positive")
        except (TypeError, ValueError): errors.append(f"{name}.{key} must be an integer")
    if s.get("device") not in {"auto", "cpu", "mps", "cuda"}: errors.append(f"{name}.device must be auto, cpu, mps, or cuda")
    try: top_k=int(s.get("top_k",0))
    except (TypeError,ValueError): top_k=0
    try: candidate_k=int(s.get("candidate_k",0))
    except (TypeError,ValueError): candidate_k=0
    if top_k not in {3,5,10,15}: errors.append(f"{name}.top_k must be 3, 5, 10, or 15")
    if candidate_k < top_k or candidate_k > 1000: errors.append(f"{name}.candidate_k must be between top_k and 1000")
    try: rrf_candidate_k=int(s.get("rrf_candidate_k",candidate_k))
    except (TypeError,ValueError): rrf_candidate_k=0
    if rrf_candidate_k < 1 or rrf_candidate_k > 1000: errors.append(f"{name}.rrf_candidate_k must be between 1 and 1000")
    rerank=s.get("rerank")
    if rerank in {"lexical-20","lexical-50"} and candidate_k != int(rerank.split("-")[1]): errors.append(f"{name}.candidate_k must match the {rerank} candidate pool")
    try: budget=int(s.get("context_token_budget",0))
    except (TypeError,ValueError): budget=0
    if budget not in {2000,4000,8000}: errors.append(f"{name}.context_token_budget must be 2000, 4000, or 8000")
    try: mmr_lambda=float(s.get("mmr_lambda",-1))
    except (TypeError,ValueError): mmr_lambda=-1
    if not 0 <= mmr_lambda <= 1: errors.append(f"{name}.mmr_lambda must be between 0 and 1")
    return errors


def experiment_settings(config: dict[str,Any]) -> list[dict[str,Any]]:
    baseline={**DEFAULTS,**config.get("baseline",{})}
    rows=[{"name":"baseline",**baseline}]
    for i,item in enumerate(config.get("experiments",[]),1): rows.append({**baseline,**item,"name":item.get("name",f"variant-{i}")})
    return rows


def dry_run(store: Store, dataset: dict[str,Any], config: dict[str,Any]) -> dict[str,Any]:
    validation=validate_inputs(store,dataset,config); settings=experiment_settings(config)
    gen=config.get("generation",{}); repeats=int(gen.get("repetitions",3)); conditions=gen.get("conditions",["G0","G1"]); backends=gen.get("backends",[])
    selected=[c for c in dataset.get("cases",[]) if not config.get("evaluation_split") or c.get("split")==config["evaluation_split"]]
    cases=len(selected); calls=cases*repeats*len(conditions)*len(backends)
    availability={"api":bool(os.getenv("OPENAI_API_KEY")),"codex_cli_detected":bool(_codex_executable()),"codex_execution_allowed":_codex_execution_allowed(),"mock":True}
    estimated_input=sum(max(1,len(c.get("user_request",""))//4) for c in selected)*max(1,repeats*len(conditions)*len(backends))
    pricing=config.get("pricing"); cost=None; reason="pricing not supplied; cost is not guessed"
    if pricing:
        cost=estimated_input/1_000_000*float(pricing.get("input_per_million",0))
        reason="input-only lower-bound estimate; output tokens are unknown before execution"
    return {"valid":validation["valid"],"validation":validation,"retrieval_runs":cases*len(settings),"generation_calls":calls,"settings":[x["name"] for x in settings],"backend_availability":availability,"estimated_input_tokens_lower_bound":estimated_input,"estimated_cost":cost,"cost_note":reason,"execution":"not_run"}


def embedding_text(tc: TestCase, mode: str, preprocess: str, terms: dict[str,str]|None=None) -> str:
    parts=[("SCENARIO",tc.scenario)]
    if mode in {"E2","E3","E4"}: parts=[("CATEGORY"," / ".join(x for x in (tc.category_large,tc.category_medium,tc.category_small) if x))]+parts
    if mode in {"E3","E4"}: parts += [("PRECONDITIONS",tc.preconditions),("INPUTS",tc.inputs)]
    if mode=="E4": parts += [("STEPS","\n".join(tc.steps)),("EXPECTED",tc.expected_results or tc.raw_expected_output_text),("POSTCONDITIONS",tc.postconditions)]
    text="\n".join(f"[{k}]\n{v}" for k,v in parts if v)
    if preprocess in {"whitespace","terms"}: text=re.sub(r"[ \t]+"," ",text).replace("\r\n","\n").strip()
    if preprocess=="terms":
        for old,new in (terms or {}).items(): text=text.replace(old,new)
    return text


def build_units(cases: list[TestCase], setting: dict[str,Any], terms: dict[str,str]|None=None) -> list[dict[str,Any]]:
    base=[{"member_ids":[tc.record_id],"text":embedding_text(tc,setting["embedding_input"],setting["preprocess"],terms),"tc":tc} for tc in cases]
    if setting["search_unit"]=="C1": return base
    if setting["search_unit"]=="C2":
        out=[]; limit=int(setting["chunk_chars"]); overlap=min(int(setting["chunk_overlap"]),limit-1)
        for u in base:
            if len(u["text"])<=limit: out.append(u); continue
            for n,start in enumerate(range(0,len(u["text"]),limit-overlap)):
                chunk=u["text"][start:start+limit]
                if chunk: out.append({**u,"text":chunk,"chunk":n})
                if start+limit>=len(u["text"]): break
        return out
    groups=defaultdict(list)
    for u in base: groups[(u["tc"].category_large,u["tc"].category_medium,u["tc"].category_small)].append(u)
    out=[]; size=int(setting["group_size"])
    for values in groups.values():
        for i in range(0,len(values),size):
            batch=values[i:i+size]; out.append({"member_ids":[rid for u in batch for rid in u["member_ids"]],"text":"\n\n".join(u["text"] for u in batch),"tc":batch[0]["tc"]})
    return out


def query_texts(case: dict[str,Any], mode: str) -> list[str]:
    raw=case["user_request"]
    structured=case.get("structured_query",{})
    feature=structured.get("feature",case.get("feature_name",""))
    if mode=="Q1": return [raw]
    if mode=="Q2": return [(feature+"\n"+raw).strip()]
    fields=[f"{k}: {v}" for k,v in structured.items() if v]
    if mode=="Q3": return ["\n".join(fields+[raw])]
    aspects=structured.get("aspects") or ["normal","boundary","invalid input","permission","state","failure recovery"]
    return ["\n".join(fields+[raw,f"viewpoint: {a}"]) for a in aspects]


def apply_filters(cases: list[TestCase], case: dict[str,Any], setting: dict[str,Any]) -> list[TestCase]:
    level=setting.get("filters","project_version"); structured=case.get("structured_query",{})
    if level in {"category_large","category_medium"}:
        value=structured.get(level)
        if value: cases=[tc for tc in cases if getattr(tc,level)==value]
    return cases


def _tokens(text: str) -> list[str]:
    return re.findall(r"[0-9A-Za-z_\uac00-\ud7a3]+",text.casefold())


def _keyword_scores(query: str, units: list[dict[str,Any]]) -> list[float]:
    docs=[_tokens(u["text"]) for u in units]; q=set(_tokens(query)); n=len(docs); avg=sum(map(len,docs))/max(1,n); df=Counter(t for d in docs for t in set(d)); scores=[]
    for d in docs:
        tf=Counter(d); score=0.0
        for t in q:
            freq=tf[t]; idf=math.log(1+(n-df[t]+.5)/(df[t]+.5)); score += idf*freq*2.2/(freq+1.2*(1-.75+.75*len(d)/max(1,avg)))
        scores.append(score)
    return scores


def _rank_units(embedder, queries: list[str], units: list[dict[str,Any]], setting: dict[str,Any], document_vectors: list[list[float]]|None=None) -> tuple[list[dict[str,Any]],dict[str,float],list[list[float]]|None]:
    started=time.perf_counter()
    method=setting["search_method"]; vector_scores=[0.0]*len(units); keyword_scores=[0.0]*len(units); vectors=None; qvectors=None
    embedding_started=time.perf_counter()
    if method in {"vector","hybrid"}:
        vectors=document_vectors if document_vectors is not None else embedder.embed([u["text"] for u in units]); qvectors=embedder.embed(queries)
        vector_scores=[max(sum(a*b for a,b in zip(qv,dv)) for qv in qvectors) for dv in vectors]
    embedding_seconds=round(time.perf_counter()-embedding_started,6) if method in {"vector","hybrid"} else 0.0
    if method in {"keyword","hybrid"} or setting.get("rerank") in {"lexical-20","lexical-50"}:
        per=[_keyword_scores(q,units) for q in queries]; keyword_scores=[max(row[i] for row in per) for i in range(len(units))]
    if method=="hybrid":
        rrf=int(setting["rrf_k"]); source_k=int(setting.get("rrf_candidate_k",setting["candidate_k"])); scores=[0.0]*len(units); fusion_candidates=set()
        for source,positive_only in ((vector_scores,False),(keyword_scores,True)):
            source_ranked=sorted((i for i in range(len(units)) if not positive_only or source[i]>0),key=lambda i:(source[i],-i),reverse=True)[:source_k]
            for rank,idx in enumerate(source_ranked,1): scores[idx]+=1/(rrf+rank); fusion_candidates.add(idx)
        score_type="rrf"
    else: scores=vector_scores if method=="vector" else keyword_scores; score_type="cosine_similarity" if method=="vector" else "bm25"
    ranked=sorted(fusion_candidates if method=="hybrid" else range(len(units)),key=lambda i:(scores[i],-i),reverse=True)[:int(setting["candidate_k"])]
    initial_rank={idx:rank for rank,idx in enumerate(ranked)}
    if setting.get("rerank") in {"lexical-20","lexical-50"}:
        ranked=sorted(ranked,key=lambda i:(keyword_scores[i],scores[i]),reverse=True)
    if setting.get("selection")=="mmr" and vectors is not None:
        chosen=[]; remaining=ranked[:]; lam=float(setting["mmr_lambda"])
        while remaining:
            idx=max(remaining,key=lambda i:lam*scores[i]-(1-lam)*max([sum(a*b for a,b in zip(vectors[i],vectors[j])) for j in chosen] or [0]))
            chosen.append(idx); remaining.remove(idx)
        ranked=chosen
    reranked=setting.get("rerank") in {"lexical-20","lexical-50"}
    timing={"embedding_calls":int(method in {"vector","hybrid"}),"embedding_seconds":embedding_seconds,"search_seconds":round(time.perf_counter()-started,6)}
    return [{**units[i],"unit_score":keyword_scores[i] if reranked else scores[i],"score_type":"bm25_rerank" if reranked else score_type,"initial_score":scores[i],"initial_rank":initial_rank[i]} for i in ranked],timing,vectors


def _persist_experiment_index(store: Store, units: list[dict[str,Any]], vectors: list[list[float]]|None, embedder, version: str, setting: dict[str,Any]) -> None:
    if vectors is None: return
    for i,(unit,vector) in enumerate(zip(units,vectors)):
        rid=unit["member_ids"][0]; metadata={"member_record_ids":unit["member_ids"],"project_id":unit["tc"].project_id,"product_version":unit["tc"].product_version,"experiment":True,"setting":setting["name"],"provider":setting.get("embedding_provider"),"model_id":setting.get("embedding_model",embedder.name),"revision":setting.get("model_revision"),"dimension":len(vector),"normalize_embeddings":setting.get("normalize_embeddings",True),"embedding_input":setting.get("embedding_input"),"preprocess":setting.get("preprocess"),"index_version":version}
        store.db.execute("INSERT OR IGNORE INTO vector_index VALUES(?,?,?,?,?,?,?,?,?)",(version,rid,f"unit:{i}",embedder.name,len(vector),f"{setting['embedding_input']}:{setting['preprocess']}:{setting['search_unit']}",json.dumps(vector),stable_json(metadata),now()))
    store.db.commit()


def _load_index_vectors(store: Store, index_version: str, embedder, units: list[dict[str,Any]]) -> list[list[float]]:
    rows = store.db.execute(
        "SELECT record_id, model, dimension, vector_json, metadata_json FROM vector_index WHERE index_version=? AND model=?",
        (index_version, embedder.name),
    ).fetchall()
    vectors = {}
    for row in rows:
        if int(row["dimension"]) != int(embedder.dimension):
            raise ValueError(f"stored index dimension mismatch for {index_version}")
        metadata = json.loads(row["metadata_json"])
        if metadata.get("embedding_input") != "E2":
            raise ValueError(f"stored index {index_version} is not an E2 index")
        vectors[row["record_id"]] = json.loads(row["vector_json"])
    missing = [rid for unit in units for rid in unit["member_ids"] if rid not in vectors]
    if missing:
        raise ValueError(f"stored index {index_version} is missing {len(missing)} searchable records")
    return [vectors[unit["member_ids"][0]] for unit in units]


def collapse_units(ranked: list[dict[str,Any]], cases: dict[str,TestCase], k: int) -> list[dict[str,Any]]:
    best={}
    for unit in ranked:
        for rid in unit["member_ids"]:
            if rid not in best: best[rid]={"record_id":rid,"score":unit["unit_score"],"score_type":unit["score_type"],"tc":cases[rid]}
    return list(best.values())[:k]


def metrics(retrieved: list[str], relevant: set[str], k: int, grades: dict[str,int]|None=None) -> dict[str,Any]:
    top=retrieved[:k]; hits=[rid in relevant for rid in top]; first=next((i+1 for i,x in enumerate(hits) if x),None)
    out={"precision_at_k":sum(hits)/k,"recall_at_k":sum(hits)/len(relevant) if relevant else None,"mrr_at_k":1/first if first else 0.0,"hit_rate_at_k":1.0 if any(hits) else 0.0,"relevant_count":len(relevant),"retrieved_count":len(top),"shortfall":max(0,k-len(top))}
    if grades:
        dcg=sum((2**grades.get(rid,0)-1)/math.log2(i+2) for i,rid in enumerate(top)); ideal=sorted(grades.values(),reverse=True)[:k]; idcg=sum((2**g-1)/math.log2(i+2) for i,g in enumerate(ideal)); out["ndcg_at_k"]=dcg/idcg if idcg else None
    else: out["ndcg_at_k"]=None
    return out


def _context(results: list[dict[str,Any]], budget: int) -> tuple[list[dict[str,Any]],int]:
    chosen=[]; used=0
    for r in results:
        tc=r["tc"]; text=embedding_text(tc,"E4","whitespace"); tokens=max(1,math.ceil(len(text)/4))
        if used+tokens<=budget: chosen.append({**tc.to_dict(),"score":r["score"]}); used+=tokens
    return chosen,used


def run_retrieval(store: Store, dataset: dict[str,Any], config: dict[str,Any], output: Path, resume: bool=False) -> dict[str,Any]:
    validation=validate_inputs(store,dataset,config)
    if not validation["valid"]: raise ValueError("invalid evaluation inputs: "+"; ".join(validation["errors"]))
    output.mkdir(parents=True,exist_ok=True); result_file=output/"retrieval_results.jsonl"; completed=set()
    if resume and result_file.exists():
        completed={json.loads(line)["task_id"] for line in result_file.read_text(encoding="utf-8").splitlines() if line.strip() and json.loads(line).get("status") in {"actual","mock"}}
    settings=experiment_settings(config); rows=[]
    terms=config.get("term_map",{}); document_vector_cache: dict[str,list[list[float]]]= {}
    selected=[c for c in dataset["cases"] if not config.get("evaluation_split") or c.get("split")==config["evaluation_split"]]
    for case in selected:
        all_cases=store.list_cases(case["project_id"],case["product_version"]); hidden=set(case.get("hidden_record_ids",[])); searchable=[tc for tc in all_cases if tc.record_id not in hidden and tc.origin!="generated"]
        for setting in settings:
            try:
                embedder=(get_embedder(setting["embedding_provider"], **setting) if setting["embedding_provider"] in {"local", "sentence-transformers"} else get_embedder(setting["embedding_provider"]))
                embedder_identity={"provider":setting["embedding_provider"],"name":embedder.name,"model":getattr(embedder,"model_id",embedder.name),"revision":getattr(embedder,"model_revision",None),"dimension":embedder.dimension,"normalize_embeddings":getattr(embedder,"normalize_embeddings",True),"device":getattr(embedder,"device",None)}
            except Exception as exc:
                embedder_identity={"provider":setting["embedding_provider"],"name":setting.get("embedding_model"),"model":setting.get("embedding_model"),"revision":setting.get("model_revision"),"dimension":setting.get("dimension"),"normalize_embeddings":setting.get("normalize_embeddings"),"device":setting.get("device")}
                task_id=sha({"dataset_version":dataset["dataset_version"],"case":case,"setting":setting,"term_map":terms,"embedder":embedder_identity})
                if task_id in completed: continue
                row={"experiment_id":config.get("experiment_id","experiment"),"task_id":task_id,"case_id":case["case_id"],"evaluation_type":case.get("evaluation_type","retrieval"),"evaluation_purpose":case.get("evaluation_purpose"),"run_id":"ret_"+task_id[:12],"executed_at":now(),"dataset_version":dataset["dataset_version"],"setting":setting,"embedder":embedder_identity,"status":"not_run","execution_mode":"not_run","duration_seconds":0.0,"error":str(exc),"not_run_reason":"local embedding model unavailable or failed to load"}
                with result_file.open("a",encoding="utf-8") as f: f.write(stable_json(row)+"\n")
                rows.append(row)
                continue
            fingerprint={"dataset_version":dataset["dataset_version"],"case":case,"setting":setting,"term_map":terms,"embedder":embedder_identity}
            task_id=sha(fingerprint)
            if task_id in completed: continue
            started=time.perf_counter(); execution_mode="mock" if embedder.name=="local-hash-v1" else "actual"; status=execution_mode; error=None
            try:
                filtered=apply_filters(searchable,case,setting); lookup={tc.record_id:tc for tc in filtered}
                units=build_units(filtered,setting,terms); queries=query_texts(case,setting["query_mode"])
                index_fingerprint={"dataset_version":dataset["dataset_version"],"setting":setting,"term_map":terms,"embedder":embedder_identity,"project_id":case["project_id"],"product_version":case["product_version"],"units":sha([[u["member_ids"],u["text"]] for u in units])}
                index_version="exp:"+config.get("experiment_id","experiment")+":"+sha(index_fingerprint)[:16]
                cached_vectors=document_vector_cache.get(index_version)
                persisted_index=setting.get("vector_index_version")
                if cached_vectors is None and persisted_index and setting["search_method"] in {"vector","hybrid"}:
                    cached_vectors=_load_index_vectors(store,persisted_index,embedder,units)
                    document_vector_cache[index_version]=cached_vectors
                ranked,timing,vectors=_rank_units(embedder,queries,units,setting,cached_vectors)
                timing["document_embedding_cache_hit"]=cached_vectors is not None
                timing["vector_index_source"]=persisted_index
                embedder_identity={"provider":setting["embedding_provider"],"name":embedder.name,"model":getattr(embedder,"model_id",embedder.name),"revision":getattr(embedder,"model_revision",None),"dimension":embedder.dimension,"normalize_embeddings":getattr(embedder,"normalize_embeddings",True),"device":getattr(embedder,"device",None)}
                fingerprint["embedder"]=embedder_identity
                if vectors is not None and cached_vectors is None:
                    document_vector_cache[index_version]=vectors
                    _persist_experiment_index(store,units,vectors,embedder,index_version,setting)
                initial_candidates=collapse_units(sorted(ranked,key=lambda unit:unit["initial_rank"]),lookup,int(setting["candidate_k"]))
                collapsed=collapse_units(ranked,lookup,int(setting["top_k"])); ids=[r["record_id"] for r in collapsed]
                relevant=set(case.get("relevant_record_ids",[]))-hidden; score=metrics(ids,relevant,int(setting["top_k"]),case.get("relevance_grades"))
                context,context_tokens=_context(collapsed,int(setting["context_token_budget"])); unjudged=[rid for rid in ids if rid not in relevant and rid not in case.get("relevance_grades",{})]
                payload={"queries":queries,"index_version":index_version,"candidate_record_ids":[r["record_id"] for r in initial_candidates],"retrieval_results":[{"record_id":r["record_id"],"score":r["score"],"score_type":r["score_type"]} for r in collapsed],"context_record_ids":[x["record_id"] for x in context],"context_tokens_estimated":context_tokens,"metrics":score,"unjudged_retrieved":unjudged,"no_evidence_case":not relevant,"hidden_record_ids":sorted(hidden),**timing}
            except Exception as exc: status="failed"; error=str(exc); payload={}
            row={"experiment_id":config.get("experiment_id","experiment"),"task_id":task_id,"case_id":case["case_id"],"evaluation_type":case.get("evaluation_type","retrieval"),"evaluation_purpose":case.get("evaluation_purpose"),"run_id":"ret_"+task_id[:12],"executed_at":now(),"dataset_version":dataset["dataset_version"],"setting":setting,"embedder":embedder_identity,"status":status,"execution_mode":execution_mode,"duration_seconds":round(time.perf_counter()-started,6),"error":error,**payload}
            with result_file.open("a",encoding="utf-8") as f: f.write(stable_json(row)+"\n")
            rows.append(row)
    all_rows=_read_jsonl(result_file); summary=aggregate(all_rows); _write_csv(output/"retrieval_results.csv",all_rows); (output/"retrieval_summary.json").write_text(stable_json(summary),encoding="utf-8")
    return {"output":str(output),"new_runs":len(rows),"summary":summary,"execution":"actual_or_explicit_mock"}


def aggregate(rows: list[dict[str,Any]]) -> dict[str,Any]:
    successful=[r for r in rows if r.get("status") in {"actual","mock"}]
    valid=[r for r in successful if r.get("metrics") and r["metrics"].get("relevant_count",0)>0]
    by_mode={}
    for mode in ("actual","mock"):
        groups=defaultdict(list)
        for r in valid:
            if r.get("execution_mode",r.get("status"))==mode: groups[r["setting"]["name"]].append(r)
        by_mode[mode]={}
        for name,items in groups.items():
            keys=("precision_at_k","recall_at_k","mrr_at_k","ndcg_at_k","hit_rate_at_k")
            by_mode[mode][name]={"cases":len(items),**{k:(sum(v)/len(v) if (v:=[x["metrics"].get(k) for x in items if x["metrics"].get(k) is not None]) else None) for k in keys},"mean_duration_seconds":sum(x["duration_seconds"] for x in items)/len(items),"mean_search_seconds":sum(x.get("search_seconds",0) for x in items)/len(items),"mean_embedding_seconds":sum(x.get("embedding_seconds",0) for x in items)/len(items)}
    no_evidence={mode:sum(r.get("no_evidence_case",False) and r.get("execution_mode",r.get("status"))==mode for r in successful) for mode in ("actual","mock")}
    return {"settings":by_mode["actual"],"settings_by_execution_mode":by_mode,"no_evidence_runs":sum(no_evidence.values()),"no_evidence_runs_by_execution_mode":no_evidence,"excluded_from_relevance_metrics":len(rows)-len(valid),"note":"Actual and mock metrics are reported separately and use labeled relevance only. Cases without relevance labels and rediscovery cases are not scored as irrelevant."}


def generation_plan(dataset: dict[str,Any], config: dict[str,Any], retrieval_rows: list[dict[str,Any]]) -> list[dict[str,Any]]:
    selected=[c for c in dataset["cases"] if not config.get("evaluation_split") or c.get("split")==config["evaluation_split"]]
    cases={c["case_id"]:c for c in selected}; best={}
    preferred=config.get("generation",{}).get("retrieval_setting","baseline")
    for r in retrieval_rows:
        if r.get("status") in {"actual","mock"} and r.get("setting",{}).get("name")==preferred:
            if r["case_id"] not in best or r.get("status")=="actual": best[r["case_id"]]=r
    gen=config.get("generation",{}); plans=[]
    for case_id,case in cases.items():
        actual=best.get(case_id,{}).get("context_record_ids",[])
        hidden=set(case.get("hidden_record_ids",[])); curated=set(case.get("curated_evidence_ids",[]))
        if hidden & curated: raise ValueError(f"{case_id}: hidden answer leaked into curated evidence")
        if hidden & set(actual): raise ValueError(f"{case_id}: hidden answer leaked into retrieved evidence")
        for condition in gen.get("conditions",["G0","G1"]):
            if condition=="G1" and case_id not in best: raise ValueError(f"{case_id}: G1 requires one successful retrieval result")
            evidence=[] if condition=="G0" else actual if condition=="G1" else case.get("curated_evidence_ids",[])
            if set(evidence)&hidden: raise ValueError(f"{case_id}: hidden answer leaked into {condition}")
            common={"case_id":case_id,"user_request":case["user_request"],"evidence_record_ids":evidence,"retrieval_execution_mode":best.get(case_id,{}).get("execution_mode") if condition=="G1" else None,"retrieval_task_id":best.get(case_id,{}).get("task_id") if condition=="G1" else None,"instructions_version":gen.get("instructions_version","generation-v1"),"schema_version":gen.get("schema_version","candidate-v1"),"target_count":gen.get("target_count",5)}
            common_hash=sha(common)
            for backend in gen.get("backends",[]):
                for repeat in range(int(gen.get("repetitions",3))): plans.append({**common,"condition":condition,"backend":backend,"repeat":repeat+1,"common_input_hash":common_hash,"task_id":sha([common_hash,backend,repeat+1])})
    return plans


def run_generation(store: Store, dataset: dict[str,Any], config: dict[str,Any], retrieval_path: Path, output: Path, execute: bool=False, resume: bool=False) -> dict[str,Any]:
    validation=validate_inputs(store,dataset,config)
    if not validation["valid"]: raise ValueError("invalid evaluation inputs: "+"; ".join(validation["errors"]))
    rows=_validate_retrieval_artifact(store,dataset,config,_read_jsonl(retrieval_path)); plans=generation_plan(dataset,config,rows); output.mkdir(parents=True,exist_ok=True); target=output/"generation_results.jsonl"; done=set()
    if resume and target.exists(): done={r["task_id"] for r in _read_jsonl(target) if r.get("status") in {"actual","mock"}}
    case_map={c["case_id"]:c for c in dataset["cases"]}; produced=[]
    for plan in plans:
        contexts=[store.get(rid).to_dict() for rid in plan["evidence_record_ids"] if store.get(rid)]
        case=case_map[plan["case_id"]]
        if len(contexts)!=len(plan["evidence_record_ids"]): raise ValueError(f"{plan['case_id']}: generation evidence record is missing")
        if any((tc["project_id"],tc["product_version"])!=(case["project_id"],case["product_version"]) or tc["origin"]=="generated" for tc in contexts): raise ValueError(f"{plan['case_id']}: generation evidence is outside the case scope")
        query={"project_id":case_map[plan["case_id"]]["project_id"],"product_version":case_map[plan["case_id"]]["product_version"],"scenario":plan["user_request"],"conditions":""}
        contract=build_generation_contract(query,contexts,target_count=int(plan["target_count"]),condition=plan["condition"],instructions_version=plan["instructions_version"],schema_version=plan["schema_version"])
        common_hash=sha(contract); backend_identity=_backend_identity(plan["backend"]); task_id=sha([common_hash,plan["backend"],plan["repeat"],backend_identity]); plan={**plan,"common_input_hash":common_hash,"backend_identity":backend_identity,"task_id":task_id}
        if task_id in done: continue
        status="not_run"; error=None; result=None; usage=None; started=time.perf_counter(); backend=plan["backend"]
        if not execute: error="dry-run: pass --execute to call the generation backend"
        elif backend=="api" and not os.getenv("OPENAI_API_KEY"): error="OPENAI_API_KEY is missing"
        elif backend=="codex" and not _codex_executable(): error="codex CLI is unavailable"
        elif backend=="codex" and not _codex_execution_allowed(): error="Codex execution is disabled: built-in read tools cannot be fully isolated; set TC_RAG_ALLOW_CODEX_READ_TOOLS=1 only in a secret-free environment"
        else:
            try:
                if backend=="api":
                    llm=get_llm("openai"); result=llm.generate_contract(contract); usage=getattr(llm,"last_usage",None); status="actual"
                elif backend=="mock":
                    llm=get_llm("mock"); result=llm.analyze_and_generate(query,contexts); status="mock"
                else: result=_run_codex(contract,plan); status="actual"
            except Exception as exc: status="failed"; error=str(exc)
        validation=_evaluate_generation(result,plan,case_map[plan["case_id"]]) if result else None
        row={**plan,"status":status,"execution_mode":status,"model":_model_name(backend),"backend_version":_codex_version() if backend=="codex" else "OpenAI-compatible HTTP" if backend=="api" else "local mock v1","tool_calls_observed":None if backend=="codex" else False,"tool_calls_note":"plain Codex output does not expose tool events; read-only sandbox and no-tool instruction applied" if backend=="codex" else None,"result":result,"automatic_evaluation":validation,"duration_seconds":round(time.perf_counter()-started,6),"usage":usage,"cost":None,"cost_note":"provider usage or verifiable billing cost unavailable" if status in {"actual","mock"} else "not executed","error":error,"executed_at":now()}
        with target.open("a",encoding="utf-8") as f: f.write(stable_json(row)+"\n")
        produced.append(row)
    _write_generation_csv(output/"generation_results.csv",_read_jsonl(target))
    return {"planned":len(plans),"new_results":len(produced),"status_counts":dict(Counter(x["status"] for x in produced)),"output":str(target)}


def _validate_retrieval_artifact(store: Store, dataset: dict[str,Any], config: dict[str,Any], rows: list[dict[str,Any]]) -> list[dict[str,Any]]:
    cases={c["case_id"]:c for c in dataset["cases"]}
    settings={s["name"]:s for s in experiment_settings(config)}; successful={}
    for row in rows:
        if row.get("status") not in {"actual","mock"}: continue
        if row.get("dataset_version")!=dataset["dataset_version"]: raise ValueError("retrieval artifact dataset_version does not match")
        if row.get("experiment_id")!=config.get("experiment_id","experiment"): raise ValueError("retrieval artifact experiment_id does not match")
        case=cases.get(row.get("case_id"))
        if not case: raise ValueError("retrieval artifact contains an unknown case_id")
        setting=row.get("setting",{}); expected_setting=settings.get(setting.get("name"))
        if setting!=expected_setting: raise ValueError(f"{case['case_id']}: retrieval setting does not match current config")
        fingerprint={"dataset_version":dataset["dataset_version"],"case":case,"setting":setting,"term_map":config.get("term_map",{}),"embedder":row.get("embedder")}
        if row.get("task_id")!=sha(fingerprint): raise ValueError(f"{case['case_id']}: retrieval task fingerprint does not match current inputs")
        hidden=set(case.get("hidden_record_ids",[]))
        for rid in row.get("context_record_ids",[]):
            tc=store.get(rid)
            if not tc or tc.origin=="generated" or (tc.project_id,tc.product_version)!=(case["project_id"],case["product_version"]): raise ValueError(f"{case['case_id']}: retrieval evidence is outside the case scope")
            if rid in hidden: raise ValueError(f"{case['case_id']}: hidden answer leaked into retrieval evidence")
        key=(row["case_id"],setting["name"]); previous=successful.get(key)
        if previous and previous["task_id"]!=row["task_id"]: raise ValueError(f"{case['case_id']}: multiple successful retrieval artifacts match one setting")
        if not previous or row.get("status")=="actual": successful[key]=row
    return list(successful.values())


def _run_codex(contract: dict[str,Any], plan: dict[str,Any]) -> dict[str,Any]:
    prompt=contract["instructions"]+"\nReturn one JSON object only.\n"+stable_json({k:v for k,v in contract.items() if k!="instructions"})
    command=[_codex_executable(),"exec","--ephemeral","--ignore-user-config","--ignore-rules","--skip-git-repo-check","--sandbox","read-only"]
    if model:=_model_name("codex"): command += ["--model",model]
    allowed_env=("PATH","HOME","CODEX_HOME","TMPDIR","TMP","TEMP","USER","LOGNAME","LANG","LC_ALL")
    clean_env={key:os.environ[key] for key in allowed_env if key in os.environ}
    completed=subprocess.run(command+["-"],input=prompt.encode("utf-8"),capture_output=True,timeout=180,env=clean_env)
    stdout=completed.stdout.decode("utf-8",errors="replace"); stderr=completed.stderr.decode("utf-8",errors="replace")
    if completed.returncode: raise RuntimeError((stderr or stdout).strip()[:2000])
    text=stdout.strip(); start=text.find("{"); end=text.rfind("}")
    if start<0 or end<start: raise ValueError("Codex CLI did not return a JSON object")
    return json.loads(text[start:end+1])


def _codex_executable() -> str|None:
    return shutil.which("codex.cmd") if os.name=="nt" else shutil.which("codex")


def _codex_execution_allowed() -> bool:
    return bool(_codex_executable()) and os.getenv("TC_RAG_ALLOW_CODEX_READ_TOOLS")=="1"


@functools.lru_cache(maxsize=1)
def _codex_version() -> str|None:
    executable=_codex_executable()
    if not executable: return None
    try: return subprocess.run([executable,"--version"],capture_output=True,text=True,timeout=10).stdout.strip() or None
    except (OSError,subprocess.SubprocessError): return None


def _model_name(backend: str) -> str|None:
    if backend=="api": return os.getenv("TC_RAG_LLM_MODEL","gpt-4.1-mini")
    if backend=="codex": return os.getenv("TC_RAG_CODEX_MODEL")
    if backend=="mock": return "mock-evidence-llm-v1"
    return None


def _backend_identity(backend: str) -> dict[str,Any]:
    if backend=="api": return {"model":_model_name(backend),"base_url":os.getenv("OPENAI_BASE_URL","https://api.openai.com/v1"),"transport":"responses-http"}
    if backend=="codex": return {"model":_model_name(backend),"cli_version":_codex_version()}
    return {"model":_model_name(backend)}


def _evaluate_generation(result: dict[str,Any], plan: dict[str,Any], case: dict[str,Any]) -> dict[str,Any]:
    top_valid=isinstance(result,dict) and set(result)=={"analysis","candidates"} and isinstance(result.get("analysis"),list) and isinstance(result.get("candidates"),list)
    analysis_required={"condition","reason","evidence_record_ids","evidence_summary","assumptions","questions_for_reviewer"}
    if top_valid:
        top_valid=all(isinstance(item,dict) and set(item)==analysis_required and all(isinstance(item[field],str) for field in ("condition","reason","evidence_summary")) and all(isinstance(item[field],list) and all(isinstance(value,str) for value in item[field]) for field in ("evidence_record_ids","assumptions","questions_for_reviewer")) for item in result["analysis"])
    candidates=result.get("candidates",[]) if isinstance(result,dict) and isinstance(result.get("candidates"),list) else []; evidence=set(plan["evidence_record_ids"]); invalid=0; unsupported=0
    required={"category_large","category_medium","category_small","scenario","preconditions","inputs","steps","expected_results","related_record_ids","difference_from_existing","assumptions","expected_result_basis","requires_confirmation","reviewer_questions"}
    for c in candidates:
        if not isinstance(c,dict): invalid+=1; continue
        schema_errors=list(required-set(c))
        if set(c)-required: schema_errors.append("additionalProperties")
        for field in ("category_large","category_medium","category_small","scenario","preconditions","inputs","difference_from_existing"):
            if field in c and not isinstance(c[field],str): schema_errors.append(field)
        for field in ("steps","related_record_ids","assumptions","reviewer_questions"):
            if field in c and (not isinstance(c[field],list) or not all(isinstance(value,str) for value in c[field])): schema_errors.append(field)
        if c.get("expected_result_basis") not in {"existing_tc","inferred","unknown"}: schema_errors.append("expected_result_basis")
        if not isinstance(c.get("requires_confirmation"),bool): schema_errors.append("requires_confirmation")
        if c.get("expected_results") is not None and not isinstance(c.get("expected_results"),str): schema_errors.append("expected_results")
        invalid += bool(schema_errors or validate_candidate(c,evidence))
        text=stable_json(c)
        unsupported += any(str(x).casefold() in text.casefold() for x in case.get("forbidden_inferences",[]))
    no_evidence=not evidence
    abstained=no_evidence and all(not c.get("related_record_ids") and c.get("expected_results") is None and c.get("expected_result_basis")=="unknown" and c.get("requires_confirmation") is True for c in candidates)
    schema_valid=max(0,len(candidates)-invalid) if top_valid else 0
    return {"candidate_count":len(candidates),"schema_valid_count":schema_valid,"valid_candidate_ratio":schema_valid/len(candidates) if candidates else 0,"forbidden_inference_hits":unsupported,"no_evidence_case":no_evidence,"abstained_without_evidence":abstained if no_evidence else None,"hidden_condition_semantic_evaluation":"human_required" if case.get("hidden_conditions") else None,"human_evaluation_required":True}


def report(results_dir: Path, output: Path) -> dict[str,Any]:
    retrieval=_read_jsonl(results_dir/"retrieval_results.jsonl"); generation=_read_jsonl(results_dir/"generation_results.jsonl"); summary=aggregate(retrieval)
    status=Counter(x.get("status","unknown") for x in generation); lines=["# TC RAG evaluation report","",f"Generated: {datetime.now(timezone.utc).isoformat()}","","## Retrieval",""]
    for mode,settings in summary["settings_by_execution_mode"].items():
        lines += [f"### {mode.title()} retrieval","","| Setting | Cases | P@K | R@K | MRR@K | nDCG@K | Hit@K | Mean sec |","|---|---:|---:|---:|---:|---:|---:|---:|"]
        for name,x in settings.items(): lines.append(f"| {name} | {x['cases']} | {_fmt(x['precision_at_k'])} | {_fmt(x['recall_at_k'])} | {_fmt(x['mrr_at_k'])} | {_fmt(x['ndcg_at_k'])} | {_fmt(x.get('hit_rate_at_k'))} | {_fmt(x.get('mean_duration_seconds'))} |")
        if not settings: lines.append("| _No successful runs_ | 0 | N/A | N/A | N/A | N/A | N/A | N/A |")
        lines.append("")
    failures=Counter(r.get("evaluation_purpose") or "unspecified" for r in retrieval if r.get("status") in {"actual","mock"} and r.get("metrics",{}).get("relevant_count",0)>0 and (r.get("metrics",{}).get("recall_at_k") or 0)<1)
    lines += ["Metrics are based only on supplied relevance labels. They do not prove product requirements coverage.","","### Retrieval failures by purpose","",stable_json(dict(failures)),"","## Generation","",f"Status counts: `{dict(status)}`","","| Backend | Condition | Runs | Candidates mean | Valid ratio mean | Valid ratio SD | Forbidden hits | Mean seconds |","|---|---|---:|---:|---:|---:|---:|---:|"]
    quality=defaultdict(list)
    for row in generation:
        if row.get("status") in {"actual","mock"} and row.get("automatic_evaluation"): quality[(row.get("backend"),row.get("condition"))].append(row)
    for (backend,condition),items in sorted(quality.items()):
        ratios=[x["automatic_evaluation"]["valid_candidate_ratio"] for x in items]; candidates=[x["automatic_evaluation"]["candidate_count"] for x in items]
        forbidden=sum(x["automatic_evaluation"]["forbidden_inference_hits"] for x in items); duration=sum(x["duration_seconds"] for x in items)/len(items)
        lines.append(f"| {backend} | {condition} | {len(items)} | {sum(candidates)/len(candidates):.2f} | {sum(ratios)/len(ratios):.4f} | {statistics.pstdev(ratios):.4f} | {forbidden} | {duration:.4f} |")
    if not quality: lines.append("| _No successful generation runs_ | - | 0 | N/A | N/A | N/A | N/A | N/A |")
    known_cost=sum(float(x["cost"]) for x in generation if isinstance(x.get("cost"),(int,float)))
    generation_status="Generation runs: 0 (retrieval-only; generation was not scheduled)" if not generation else f"Generation not-run or failed: {status['not_run']+status['failed']}"
    lines += ["",f"Known generation cost total: `{known_cost if known_cost else None}`","", "Automatic checks cover schema/evidence IDs and explicit forbidden strings only. Evidence support, execution feasibility, judgeability, usefulness, duplication, and hidden-condition meaning require blinded human review.","","## Not run / limitations","",f"- Runs excluded from relevance metrics: {summary['excluded_from_relevance_metrics']}",f"- {generation_status}","- Unknown cost remains null; Codex plan usage is not converted to API billing.","- Codex and API internal instructions are not assumed identical; their comparison is not a pure RAG-effect estimate.","- Next: human-review draft labels, run staged actual retrieval, then compare the top 2-3 settings."]
    output.parent.mkdir(parents=True,exist_ok=True); output.write_text("\n".join(lines)+"\n",encoding="utf-8")
    return {"output":str(output),"retrieval_runs":len(retrieval),"generation_runs":len(generation)}


def _fmt(value): return "N/A" if value is None else f"{value:.4f}"


def _read_jsonl(path: Path) -> list[dict[str,Any]]:
    if not path.exists(): return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _write_csv(path: Path, rows: list[dict[str,Any]]) -> None:
    fields=["experiment_id","case_id","run_id","status","execution_mode","setting_name","precision_at_k","recall_at_k","mrr_at_k","ndcg_at_k","hit_rate_at_k","duration_seconds","search_seconds","embedding_seconds","error"]
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for r in rows:
            m=r.get("metrics",{}); values={"experiment_id":r.get("experiment_id"),"case_id":r.get("case_id"),"run_id":r.get("run_id"),"status":r.get("status"),"execution_mode":r.get("execution_mode"),"setting_name":r.get("setting",{}).get("name"),"precision_at_k":m.get("precision_at_k"),"recall_at_k":m.get("recall_at_k"),"mrr_at_k":m.get("mrr_at_k"),"ndcg_at_k":m.get("ndcg_at_k"),"hit_rate_at_k":m.get("hit_rate_at_k"),"duration_seconds":r.get("duration_seconds"),"search_seconds":r.get("search_seconds"),"embedding_seconds":r.get("embedding_seconds"),"error":r.get("error")}; w.writerow({key:safe_cell(value) for key,value in values.items()})


def _write_generation_csv(path: Path, rows: list[dict[str,Any]]) -> None:
    fields=["case_id","condition","backend","repeat","common_input_hash","status","model","candidate_count","valid_candidate_ratio","forbidden_inference_hits","duration_seconds","error"]
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for r in rows:
            a=r.get("automatic_evaluation") or {}; values={"case_id":r.get("case_id"),"condition":r.get("condition"),"backend":r.get("backend"),"repeat":r.get("repeat"),"common_input_hash":r.get("common_input_hash"),"status":r.get("status"),"model":r.get("model"),"candidate_count":a.get("candidate_count"),"valid_candidate_ratio":a.get("valid_candidate_ratio"),"forbidden_inference_hits":a.get("forbidden_inference_hits"),"duration_seconds":r.get("duration_seconds"),"error":r.get("error")}; w.writerow({key:safe_cell(value) for key,value in values.items()})
