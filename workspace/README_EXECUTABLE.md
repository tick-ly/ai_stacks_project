# Stacks Project Production Retrieval Pipeline

This workspace now includes:

- configuration-driven execution (`JSON` / `YAML`)
- leveled logging (`DEBUG` / `INFO` / `WARNING` / `ERROR`)
- parallel + incremental data ingestion
- pluggable embedding providers (`hash`, `openai`, `local`)
- lexical BM25 index via SQLite FTS5
- hybrid retrieval (BM25 + vector fusion)
- retrieval evaluation (`Recall@K`, `MRR@K`) and regression baseline checks

## 1. Install

Run from `workspace`:

```powershell
pip install -r requirements.txt
```

Optional local embedding provider:

```powershell
pip install sentence-transformers
```

## 2. Config Fileization

Copy the sample config and edit:

```powershell
copy config\pipeline.example.yaml config\pipeline.yaml
```

Or use JSON:

```powershell
copy config\pipeline.example.json config\pipeline.json
```

All major scripts accept:

- `--config <path/to/config.{json|yaml|yml}>`
- `--log-level INFO`

Section mapping in config:

- `run_pipeline`
- `fetch_api`
- `parse_tex`
- `build_corpus`
- `build_embeddings`
- `build_lexical_index`
- `search_demo`
- `eval_retrieval`

If a section is missing, script defaults are used.

## 3. Production Pipeline

### 3.1 Config-driven incremental run

```powershell
python scripts/run_pipeline.py --config config/pipeline.yaml --incremental
```

### 3.2 CLI override on top of config

```powershell
python scripts/run_pipeline.py --config config/pipeline.yaml --incremental --workers 16 --provider hash --dim 1536
```

### 3.3 OpenAI embedding run

```powershell
$env:OPENAI_API_KEY="YOUR_KEY"
python scripts/run_pipeline.py --config config/pipeline.yaml --incremental --provider openai --model text-embedding-3-large --dim 1536
```

## 4. Hybrid Search

```powershell
python scripts/search_demo.py --config config/pipeline.yaml --query "Cartan-Eilenberg resolution" --top-k 5
```

Filters:

```powershell
python scripts/search_demo.py --config config/pipeline.yaml --query "base change theorem" --chapter flat --env lemma --top-k 5
```

## 5. Evaluation and Regression Baseline

Sample query set:

- `config/eval_queries.sample.jsonl`

### 5.1 Run evaluation

```powershell
python scripts/eval_retrieval.py --config config/pipeline.yaml
```

This writes:

- `data/eval/latest_metrics.json`

### 5.2 Create / update baseline

```powershell
python scripts/eval_retrieval.py --config config/pipeline.yaml --update-baseline
```

This writes:

- `data/eval/baseline_metrics.json`

### 5.3 Regression check in CI

```powershell
python scripts/eval_retrieval.py --config config/pipeline.yaml --regression-tolerance 0.001
```

Exit codes:

- `0`: passed
- `3`: regression detected (`current + tolerance < baseline` for monitored metrics)

Monitored metrics default:

- `mrr@10`
- `recall@10`

Override:

```powershell
python scripts/eval_retrieval.py --config config/pipeline.yaml --regress-if-below "mrr@5,recall@5"
```

## 6. Logs

Each script uses structured timestamps and levels, for example:

```text
2026-04-09 20:15:10 | INFO | run_pipeline | Pipeline completed successfully.
```

Set verbosity:

```powershell
python scripts/run_pipeline.py --config config/pipeline.yaml --log-level DEBUG
```

## 7. Main Outputs

- `data/raw/tags.csv`
- `data/raw/api/tags/<TAG>.json`
- `data/raw/api/fetch_summary.json`
- `data/raw/api/changed_tags.json`
- `data/processed/tag_metadata.jsonl`
- `data/processed/corpus.jsonl`
- `data/processed/ref_edges.jsonl`
- `data/index/embeddings.npy`
- `data/index/ids.json`
- `data/index/doc_hashes.json`
- `data/index/index_meta.json`
- `data/index/query_embedding_config.json`
- `data/index/lexical.db`
- `data/eval/latest_metrics.json`
- `data/eval/baseline_metrics.json`

## 8. Script Reference

- `scripts/runtime_utils.py`: config loader + logging setup
- `scripts/retrieval_engine.py`: shared hybrid retrieval logic
- `scripts/eval_retrieval.py`: metrics + regression checks
