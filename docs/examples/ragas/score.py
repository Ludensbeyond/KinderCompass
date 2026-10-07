"""Score captured agent answers; --validate-only makes no model calls."""

import argparse
import json
import os
from pathlib import Path


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def prepare(cases, runs):
    case_map = {case["case_id"]: case for case in cases}
    if len(case_map) != len(cases):
        raise ValueError("Duplicate case IDs in the dataset")
    seen = set()
    rows = []
    ids = []
    behaviour = []
    for run in runs:
        case_id = run["case_id"]
        if case_id in seen:
            raise ValueError(f"Duplicate run: {case_id}")
        seen.add(case_id)
        case = case_map[case_id]
        response = run["response"]
        contexts = run["retrieved_contexts"]
        if not isinstance(response, str) or not response.strip():
            raise ValueError(f"{case_id}: response must contain the actual agent answer")
        if not isinstance(contexts, list) or any(
            not isinstance(text, str) or not text.strip() for text in contexts
        ):
            raise ValueError(f"{case_id}: retrieved_contexts must be a list of passage texts")
        if case["evaluation"] == "behaviour":
            behaviour.append({
                "case_id": case_id,
                "response": response,
                "retrieved_contexts": contexts,
                "checks": case["checks"],
            })
            continue
        rows.append({
            "user_input": case["user_input"],
            "response": response,
            "retrieved_contexts": contexts,
            "reference": case["reference"],
        })
        ids.append(case_id)
    if seen != set(case_map):
        raise ValueError(f"Missing runs: {sorted(set(case_map) - seen)}")
    return rows, ids, behaviour


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=Path(__file__).with_name("cases.jsonl"))
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("/tmp/kindercompass-ragas.csv"))
    parser.add_argument("--judge-model", help="Model available to your evaluation provider")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    rows, ids, behaviour = prepare(read_jsonl(args.cases), read_jsonl(args.runs))
    print(f"Validated {len(rows)} RAGAS cases and {len(behaviour)} behaviour cases.")
    if args.validate_only:
        return
    if not args.judge_model:
        parser.error("--judge-model is required when scoring")
    if not os.getenv("OPENAI_API_KEY"):
        parser.error("Set OPENAI_API_KEY in your shell for the evaluation judge")

    # Optional evaluation dependencies; production backend dependencies stay unchanged.
    from langchain_openai import ChatOpenAI
    from ragas import EvaluationDataset, evaluate
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import (
        Faithfulness,
        LLMContextPrecisionWithReference,
        LLMContextRecall,
    )

    judge = LangchainLLMWrapper(ChatOpenAI(model=args.judge_model, temperature=0))
    result = evaluate(
        EvaluationDataset.from_list(rows),
        metrics=[Faithfulness(), LLMContextPrecisionWithReference(), LLMContextRecall()],
        llm=judge,
        raise_exceptions=True,
    )
    frame = result.to_pandas()
    frame.insert(0, "case_id", ids)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False)
    review_path = args.output.with_suffix(".behaviour.json")
    review_path.write_text(json.dumps(behaviour, indent=2) + "\n")
    print(f"Per-case scores: {args.output}")
    print(f"Behaviour checks awaiting manual review: {review_path}")


if __name__ == "__main__":
    main()
