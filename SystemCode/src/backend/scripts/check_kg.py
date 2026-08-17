"""Inspect Neo4j preschool counts, property keys, and sample records.

Run from the repository root in PowerShell:

    $env:PYTHONPATH = "SystemCode/src/backend;SystemCode/src/backend/pipeline"
    python SystemCode/src/backend/scripts/check_kg.py
"""
from dotenv import load_dotenv
import random

from stage1.kg_client import get_driver, run_query


def main():
    load_dotenv()
    try:
        driver = get_driver()
    except Exception as e:
        print("Failed to create Neo4j driver:", e)
        return

    try:
        print("Verifying connectivity...")
        driver.verify_connectivity()
        print("Connected to Neo4j")
    except Exception as e:
        print("Connectivity check failed:", e)
        return

    # Count preschools (used for efficient random sampling)
    query_count = "MATCH (p:Preschool) RETURN count(p) AS count"
    try:
        count_res = run_query(driver, query_count)
        total = int(count_res[0].get("count") if count_res else 0)
        print("Preschool node count:", total)
    except Exception as e:
        print("Error counting preschools:", e)
        total = 0

    # Inspect a random node's keys using SKIP (more efficient than ORDER BY rand())
    try:
        if total > 0:
            skip = int(random.random() * total)
            query_keys = "MATCH (p:Preschool) RETURN keys(p) AS keys SKIP $skip LIMIT 1"
            sample_keys = run_query(driver, query_keys, {"skip": skip})
            print("Sample preschool keys:", sample_keys[0].get("keys") if sample_keys else [])
        else:
            print("Sample preschool keys: [] (no nodes)")
    except Exception as e:
        print("Error fetching sample keys:", e)

    # Print a few sample rows with fields used by the runner; pick a random window when possible
    try:
        limit = 20
        if total > limit:
            max_skip = total - limit
            skip = int(random.random() * (max_skip + 1))
        else:
            skip = 0
        query_sample = (
            "MATCH (p:Preschool) RETURN p.centre_code AS centre_code, p.name AS name,"
            " p.philosophy AS philosophy, p.pedagogy AS pedagogy, p.base_fee AS base_fee SKIP $skip LIMIT $limit"
        )
        samples = run_query(driver, query_sample, {"skip": skip, "limit": limit})
        print(f"Printing up to {len(samples)} sample preschool rows (skip={skip}):")
        for r in samples:
            print(r)
    except Exception as e:
        print("Error fetching sample rows:", e)


if __name__ == "__main__":
    main()
