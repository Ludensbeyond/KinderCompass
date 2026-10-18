"""Generate one split of an LLM-assisted benchmark from a read-only Neo4j snapshot.

This command incurs a provider call and reads the live graph. Both actions are
disabled unless the matching explicit command-line switches are supplied.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

from dotenv import load_dotenv
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[4]
SRC = REPO_ROOT / "SystemCode" / "src"
BACKEND = SRC / "backend"
for path in (str(SRC), str(BACKEND), str(BACKEND / "pipeline")):
    if path not in sys.path:
        sys.path.insert(0, path)

from SystemCode.src.backend.evaluation.benchmark_generation import (  # noqa: E402
    NEO4J_SNAPSHOT_QUERY, ScenarioBatch, build_generated_dataset,
    prompt_for_generation, snapshot_school_records,
)
from stage1.kg_client import get_driver, verify_connectivity  # noqa: E402
from SystemCode.src.scripts.build_knowledge_graph import load_catalogue  # noqa: E402


def _generate(prompt: str, model: str, api_key: str, timeout: float) -> ScenarioBatch:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=timeout, max_retries=0)
    response = client.responses.parse(
        model=model,
        instructions=("Generate only fictional family scenario inputs. Treat supplied school data as immutable facts. "
                      "Never invent school facts or expected outcomes. Return only the requested structured object."),
        input=prompt,
        text_format=ScenarioBatch,
        store=False,
    )
    if response.output_parsed is None:
        raise ValueError("The provider returned no parsed scenarios")
    return response.output_parsed


def main(argv: list[str] | None = None) -> int:
    load_dotenv(override=False)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("development", "held_out_test"), required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New path; existing files are never overwritten")
    parser.add_argument("--model", help="Defaults to OPENAI_RECOMMENDATION_BENCHMARK_MODEL or OPENAI_PREFERENCE_MODEL")
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--allow-live-neo4j", action="store_true", help="Explicitly permit read-only Neo4j access")
    parser.add_argument("--allow-llm-cost", action="store_true", help="Explicitly permit a paid LLM request")
    parser.add_argument("--confirm-held-out-generation", action="store_true",
                        help="Required for the separate held-out invocation")
    args = parser.parse_args(argv)
    if not args.allow_live_neo4j or not args.allow_llm_cost:
        parser.error("pass --allow-live-neo4j and --allow-llm-cost to enable external access")
    if args.split == "held_out_test" and not args.confirm_held_out_generation:
        parser.error("held-out generation must be a deliberate separate invocation; pass --confirm-held-out-generation")
    if args.split == "held_out_test" and args.output.resolve().is_relative_to(REPO_ROOT.resolve()):
        parser.error("held-out output must be outside the development repository to reduce tuning leakage")
    count = 30 if args.split == "development" else 20
    if args.timeout < 1 or args.timeout > 30:
        parser.error("timeout must be between 1 and 30 seconds")
    if args.output.exists():
        parser.error(f"refusing to overwrite existing output: {args.output}")
    import os
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        parser.error("OPENAI_API_KEY is unavailable")
    model = args.model or os.environ.get(
        "OPENAI_RECOMMENDATION_BENCHMARK_MODEL",
        os.environ.get("OPENAI_PREFERENCE_MODEL", "gpt-4o-mini"),
    ).strip() or "gpt-4o-mini"

    # The caller supplied the seed and explicit switches. No credentials are
    # written to output or included in errors.
    driver = get_driver()
    try:
        verify_connectivity(driver)
        graph_rows = driver.execute(NEO4J_SNAPSHOT_QUERY, access_mode="Read")
    finally:
        driver.close()
    catalogue_path = REPO_ROOT / "SystemCode" / "data" / "processed" / "kindercompass_master.json"
    catalogue = load_catalogue(catalogue_path)
    schools = snapshot_school_records(graph_rows, catalogue)
    # Cap prompt size while making a deterministic, reproducible source subset.
    shuffled = list(schools)
    random.Random(args.seed).shuffle(shuffled)
    selected = shuffled[:min(len(shuffled), 120)]
    if len(selected) < 8:
        parser.error("at least eight overlapping Neo4j/catalogue schools are needed")
    prompt = prompt_for_generation(selected, count=count, seed=args.seed)
    try:
        proposals = _generate(prompt, model, api_key, args.timeout)
    except ValidationError as exc:
        parser.error(f"LLM structured output failed validation ({len(exc.errors())} schema errors)")
    if len(proposals.cases) != count:
        parser.error(f"LLM returned {len(proposals.cases)} cases; expected {count}")
    snapshot_version = hashlib.sha256(
        json.dumps(selected, sort_keys=True, default=str).encode()
    ).hexdigest()
    catalogue_version = hashlib.sha256(catalogue_path.read_bytes()).hexdigest()
    policy_path = BACKEND / "resources" / "policy" / "ecda_preschool_subsidies_2025-01-01.json"
    policy_version = hashlib.sha256(policy_path.read_bytes()).hexdigest()
    dataset = build_generated_dataset(
        proposals, split=args.split, seed=args.seed, school_snapshot=selected,
        snapshot_version=snapshot_version, catalogue_version=catalogue_version,
        policy_version=policy_version, model=model,
        generation_settings={"count": count, "timeout_seconds": args.timeout,
        "snapshot_school_count": len(selected), "source": "read-only Neo4j Preschool nodes plus processed service details"},
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive create closes the race between preflight check and write.
    with args.output.open("x", encoding="utf-8") as target:
        json.dump(dataset, target, indent=2, ensure_ascii=False)
        target.write("\n")
    print(f"Generated {count} {args.split} scenarios: {args.output}")
    print(f"Snapshot SHA-256: {dataset['source_snapshot']['sha256']}")
    print("No relevance labels were generated; independent human review is required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
