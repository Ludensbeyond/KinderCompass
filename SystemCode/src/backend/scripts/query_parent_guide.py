"""Read-only standalone retrieval, with no server or document embedding calls."""

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

from dotenv import load_dotenv

from SystemCode.src.backend.agents.tools import CuratedGeneralKnowledgeRetriever
from SystemCode.src.backend.pipeline.general_knowledge_config import (
    GeneralKnowledgeRetrievalMode, REPOSITORY_ROOT, get_general_knowledge_config,
)
from SystemCode.src.backend.pipeline.parent_guide_retrieval import ParentGuideRetriever
from SystemCode.src.backend.repositories.parent_guide_index import json_bytes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument("--mode", choices=[mode.value for mode in GeneralKnowledgeRetrievalMode], default="lexical")
    parser.add_argument("--vector-path")
    parser.add_argument("--year", type=int)
    parser.add_argument("--topic", help="Exact reviewed topic, section heading or mapping ID")
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args(argv)
    load_dotenv(REPOSITORY_ROOT / ".env", override=False)
    try:
        config = get_general_knowledge_config()
        path = Path(args.vector_path) if args.vector_path else config.vector_path
        if not path.is_absolute():
            path = REPOSITORY_ROOT / path
        config = replace(config, mode=GeneralKnowledgeRetrievalMode(args.mode), vector_path=path)
        curated_path = REPOSITORY_ROOT / "SystemCode/src/backend/resources/web_rag/general_knowledge_index.json"
        curated = CuratedGeneralKnowledgeRetriever(json.loads(curated_path.read_text()))
        retriever = ParentGuideRetriever(config, curated=curated)
        matches = retriever.search(args.question, limit=args.limit, topic=args.topic, year=args.year)
        print(json_bytes({"status": asdict(retriever.status),
                          "evidence": [match.model_dump(mode="json") for match in matches]}).decode(), end="")
    except Exception as error:
        print("Parent-guide query failed: " + type(error).__name__)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
