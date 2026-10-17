from pathlib import Path

from tc_rag.model import TestCase as Case
from tc_rag.providers import HashEmbedder, MockLLM
from tc_rag.storage import Store
from tc_rag.workflow import build_index, generate, search
from tc_rag.util import load_dotenv


def test_rag_smoke(tmp_path: Path):
    store=Store(tmp_path/"test.db")
    tc=Case(project_id="p",product_version="1",scenario="login succeeds",steps=["enter credentials"],expected_results="dashboard shown",origin="original",review_status="approved")
    store.save_case(tc)
    embedder=HashEmbedder(64)
    assert build_index(store,embedder,"p","1","v1")["indexed"]==1
    found=search(store,embedder,"login","p","1","v1")
    assert found[0]["record_id"]==tc.record_id
    result=generate(store,MockLLM(),{"project_id":"p","product_version":"1","scenario":"login","conditions":""},found)
    assert result["candidates"][0]["requires_confirmation"] is True
    store.close()


def test_dotenv_does_not_override_environment(tmp_path: Path, monkeypatch):
    env=tmp_path/".env"
    env.write_text("OPENAI_API_KEY=file-key\nTC_RAG_LLM_MODEL='model-x'\n",encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY","process-key")
    monkeypatch.delenv("TC_RAG_LLM_MODEL",raising=False)
    assert load_dotenv(env)
    assert __import__("os").environ["OPENAI_API_KEY"]=="process-key"
    assert __import__("os").environ["TC_RAG_LLM_MODEL"]=="model-x"

