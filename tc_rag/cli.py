from __future__ import annotations

import argparse, hashlib, json, sys
from pathlib import Path
from uuid import uuid4

from .exporters import export_csv, export_json, export_xlsx
from .evaluation import dry_run as eval_dry_run, export_review_pack as eval_review_pack, load_json as eval_load_json, report as eval_report, run_generation as eval_generation, run_retrieval as eval_retrieval, validate_inputs as eval_validate
from .parsers import parse_file
from .providers import get_embedder, get_llm
from .storage import Store, now
from .util import load_dotenv, load_json, stable_json
from .workflow import build_index, exact_and_suspected_duplicates, generate, make_split, search


def emit(value): print(json.dumps(value,ensure_ascii=False,indent=2))


def parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(prog="tc-rag",description="Evidence-first TC RAG CLI")
    p.add_argument("--db",default=".tc-rag/tc-rag.db")
    sub=p.add_subparsers(dest="command",required=True)
    x=sub.add_parser("import"); x.add_argument("files",nargs="+"); x.add_argument("--project",required=True); x.add_argument("--version",required=True); x.add_argument("--origin",choices=["original","synthetic"],default="original")
    x=sub.add_parser("split"); x.add_argument("--project",required=True); x.add_argument("--version",required=True); x.add_argument("--split-version",required=True); x.add_argument("--holdout",type=float,default=.2); x.add_argument("--seed",type=int,default=42)
    x=sub.add_parser("index"); x.add_argument("--project",required=True); x.add_argument("--version",required=True); x.add_argument("--index-version",required=True); x.add_argument("--split-version"); x.add_argument("--provider",choices=["auto","mock","openai","local"],default="auto"); x.add_argument("--embedding-model",default="BAAI/bge-m3"); x.add_argument("--model-revision"); x.add_argument("--dimension",type=int); x.add_argument("--device",choices=["auto","cpu","mps","cuda"],default="auto"); x.add_argument("--batch-size",type=int,default=16); x.add_argument("--normalize-embeddings",action=argparse.BooleanOptionalAction,default=True); x.add_argument("--max-seq-length",type=int); x.add_argument("--model-cache-dir"); x.add_argument("--embedding-input",choices=["E2","E4"],default="E4"); x.add_argument("--include-approved-generated",action="store_true")
    x=sub.add_parser("search"); _search_args(x)
    x=sub.add_parser("generate"); _search_args(x); x.add_argument("--conditions",default=""); x.add_argument("--llm",choices=["auto","mock","openai"],default="auto")
    x=sub.add_parser("list"); x.add_argument("--project"); x.add_argument("--version"); x.add_argument("--origin"); x.add_argument("--status")
    x=sub.add_parser("show"); x.add_argument("record_id")
    x=sub.add_parser("review"); x.add_argument("record_id"); x.add_argument("action",choices=["approve","reject","request-confirmation","needs-revision","edit"]); x.add_argument("--reviewer",required=True); x.add_argument("--reason",default=""); x.add_argument("--patch",type=Path)
    x=sub.add_parser("duplicates"); x.add_argument("record_id")
    x=sub.add_parser("export"); x.add_argument("output",type=Path); x.add_argument("--project",required=True); x.add_argument("--version",required=True); x.add_argument("--mode",choices=["review","approved"],default="review"); x.add_argument("--format",choices=["xlsx","json","csv"]); x.add_argument("--title",default="Test Cases"); x.add_argument("--author",default=""); x.add_argument("--reviewer",default="")
    x=sub.add_parser("eval"); es=x.add_subparsers(dest="eval_command",required=True)
    for name in ("validate","dry-run","retrieval"):
        e=es.add_parser(name); e.add_argument("--dataset",type=Path,required=True); e.add_argument("--config",type=Path,required=True)
        if name=="retrieval": e.add_argument("--output",type=Path,required=True); e.add_argument("--resume",action="store_true")
    e=es.add_parser("review-pack"); e.add_argument("--dataset",type=Path,required=True); e.add_argument("--config",type=Path,required=True); e.add_argument("--output",type=Path,required=True)
    for name in ("generation","compare"):
        e=es.add_parser(name); e.add_argument("--dataset",type=Path,required=True); e.add_argument("--config",type=Path,required=True); e.add_argument("--retrieval-results",type=Path,required=True); e.add_argument("--output",type=Path,required=True); e.add_argument("--execute",action="store_true"); e.add_argument("--resume",action="store_true")
    e=es.add_parser("report"); e.add_argument("--results",type=Path,required=True); e.add_argument("--output",type=Path,required=True)
    return p


def _search_args(x):
    x.add_argument("query"); x.add_argument("--project",required=True); x.add_argument("--version",required=True); x.add_argument("--index-version",required=True); x.add_argument("--top-k",type=int,default=5); x.add_argument("--provider",choices=["auto","mock","openai","local"],default="auto"); x.add_argument("--embedding-model",default="BAAI/bge-m3"); x.add_argument("--model-revision"); x.add_argument("--dimension",type=int); x.add_argument("--device",choices=["auto","cpu","mps","cuda"],default="auto"); x.add_argument("--batch-size",type=int,default=16); x.add_argument("--normalize-embeddings",action=argparse.BooleanOptionalAction,default=True); x.add_argument("--max-seq-length",type=int); x.add_argument("--model-cache-dir"); x.add_argument("--cross-project",action="store_true")


def _public_result(item):
    return {k:item.get(k) for k in ("record_id","original_tc_id","category_large","category_medium","category_small","scenario","raw_input_text","expected_results","score","score_type","source_refs","cross_project_reference")}


def main(argv=None) -> int:
    load_dotenv()
    args=parser().parse_args(argv); store=Store(Path(args.db)); run_id="run_"+uuid4().hex
    store.db.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?)",(run_id,args.command,"running",stable_json({k:str(v) for k,v in vars(args).items() if k!="command"}),None,now(),None)); store.db.commit()
    try:
        if args.command=="eval":
            if args.eval_command=="report": result=eval_report(args.results,args.output)
            else:
                dataset=eval_load_json(args.dataset); config=eval_load_json(args.config)
                if args.eval_command=="validate": result=eval_validate(store,dataset,config)
                elif args.eval_command=="dry-run": result=eval_dry_run(store,dataset,config)
                elif args.eval_command=="retrieval": result=eval_retrieval(store,dataset,config,args.output,args.resume)
                elif args.eval_command=="review-pack": result=eval_review_pack(store,dataset,config,args.output)
                else: result=eval_generation(store,dataset,config,args.retrieval_results,args.output,args.execute,args.resume)
        elif args.command=="import":
            result=[]
            for name in args.files:
                path=Path(name); report=parse_file(path,args.project,args.version,args.origin); info=store.import_report(report,args.project,args.version,hashlib.sha256(path.read_bytes()).hexdigest()); result.append({**info,"file":path.name,"parsed":len(report.records),"warnings":report.warnings})
        elif args.command=="split":
            if not 0 <= args.holdout < 1: raise ValueError("holdout must be >= 0 and < 1")
            result=make_split(store,args.project,args.version,args.split_version,args.holdout,args.seed)
        elif args.command=="index": result=build_index(store,get_embedder(args.provider, embedding_model=args.embedding_model, model_revision=args.model_revision, dimension=args.dimension, device=args.device, batch_size=args.batch_size, normalize_embeddings=args.normalize_embeddings, max_seq_length=args.max_seq_length, model_cache_dir=args.model_cache_dir),args.project,args.version,args.index_version,args.split_version,args.include_approved_generated,args.embedding_input)
        elif args.command in {"search","generate"}:
            found=search(store,get_embedder(args.provider, embedding_model=args.embedding_model, model_revision=args.model_revision, dimension=args.dimension, device=args.device, batch_size=args.batch_size, normalize_embeddings=args.normalize_embeddings, max_seq_length=args.max_seq_length, model_cache_dir=args.model_cache_dir),args.query,args.project,args.version,args.index_version,args.top_k,args.cross_project)
            if args.command=="search": result={"results":[_public_result(x) for x in found],"score":"cosine similarity, descending; not a probability","insufficient_evidence":len(found)<min(3,args.top_k)}
            else:
                query={"project_id":args.project,"product_version":args.version,"scenario":args.query,"conditions":args.conditions}
                result=generate(store,get_llm(args.llm),query,found); result["retrieval"]=[_public_result(x) for x in found]; result["insufficient_evidence"]=len(found)<min(3,args.top_k)
        elif args.command=="list": result=[{"record_id":x.record_id,"tc_id":x.generated_tc_id or x.original_tc_id,"scenario":x.scenario,"origin":x.origin,"review_status":x.review_status,"requires_confirmation":x.requires_confirmation} for x in store.list_cases(args.project,args.version,args.origin,args.status)]
        elif args.command=="show":
            tc=store.get(args.record_id)
            if not tc: raise ValueError("record not found")
            result=tc.to_dict()
        elif args.command=="review": result=store.review(args.record_id,args.action,args.reviewer,args.reason,load_json(args.patch) if args.patch else None).to_dict()
        elif args.command=="duplicates":
            tc=store.get(args.record_id)
            if not tc: raise ValueError("record not found")
            result=exact_and_suspected_duplicates(tc,store.list_cases(tc.project_id,tc.product_version))
        elif args.command=="export":
            cases=[x for x in store.list_cases(args.project,args.version,"generated") if args.mode=="review" or x.review_status=="approved"]
            fmt=args.format or args.output.suffix.lstrip(".").lower(); meta={"mode":args.mode,"project_id":args.project,"product_version":args.version,"count":len(cases)}
            if fmt=="xlsx": export_xlsx(args.output,cases,args.title,args.author,args.reviewer)
            elif fmt=="json": export_json(args.output,cases,meta)
            elif fmt=="csv": export_csv(args.output,cases)
            else: raise ValueError("format must be xlsx, json, or csv")
            result={**meta,"output":str(args.output)}
        store.db.execute("UPDATE runs SET status='complete',result_json=?,finished_at=? WHERE run_id=?",(stable_json(result),now(),run_id)); store.db.commit(); emit({"run_id":run_id,"result":result}); return 0
    except Exception as e:
        store.db.execute("UPDATE runs SET status='failed',result_json=?,finished_at=? WHERE run_id=?",(stable_json({"error":str(e)}),now(),run_id)); store.db.commit(); print(f"ERROR: {e}",file=sys.stderr); return 1
    finally: store.close()


if __name__=="__main__": raise SystemExit(main())
