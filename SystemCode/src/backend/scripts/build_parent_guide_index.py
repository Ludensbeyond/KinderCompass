"""Offline parent-guide build CLI. Never imported by backend startup."""

import argparse

from dotenv import load_dotenv

from SystemCode.src.backend.pipeline.general_knowledge_config import REPOSITORY_ROOT, get_general_knowledge_config
from SystemCode.src.backend.pipeline.parent_guide_build import build_parent_guide_index
from SystemCode.src.backend.pipeline.parent_guide_embeddings import OpenAIEmbeddingProvider
from SystemCode.src.backend.repositories.parent_guide_index import json_bytes, load_active_index


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vector-path", help="Directory with sources.json and build artifacts")
    parser.add_argument("--validate-only", action="store_true", help="Load active artifacts without provider calls")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-retries", type=int, default=2)
    args = parser.parse_args(argv)
    load_dotenv(REPOSITORY_ROOT / ".env", override=False)
    try:
        config = get_general_knowledge_config()
        path = config.vector_path
        if args.vector_path:
            from pathlib import Path

            path = Path(args.vector_path)
            if not path.is_absolute():
                path = REPOSITORY_ROOT / path
        if args.validate_only:
            from SystemCode.src.backend.pipeline.parent_guide_embeddings import EmbeddingSettings

            index = load_active_index(path, expected_embedding=EmbeddingSettings.from_config(config))
            summary = {"build_id": index.build_id, "chunk_count": len(index.chunks), "validated": True}
        else:
            summary = build_parent_guide_index(path, OpenAIEmbeddingProvider(config),
                                              batch_size=args.batch_size, max_retries=args.max_retries,
                                              timeout_seconds=config.timeout_seconds)
    except Exception as error:
        # Provider errors can contain credentials/request details; report category only.
        print("Parent-guide index command failed: " + type(error).__name__)
        return 2
    print(json_bytes(summary).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
