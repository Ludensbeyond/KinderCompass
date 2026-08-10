# Phase 9: Official-webpage RAG enrichment

Phase 9 aims to retrieve cited, school-specific evidence for preferences that the structured catalogue cannot currently verify. Webpage evidence is explanation-only until coverage and retrieval accuracy are audited.

## Step 1: website candidate inventory

`scripts/build_website_inventory.py` extracts `centre_website` and `website_lifesg` from the processed school catalogue. It runs offline and:

- adds a missing `https://` scheme;
- normalises host, path, fragments, and tracking parameters;
- deduplicates equivalent URLs;
- reports how many schools share a page;
- flags social-page candidates;
- distinguishes unavailable, shared-operator, and school-specific candidates; and
- leaves every candidate identity as `not_verified`.

The classification is a review queue, not proof that a unique URL belongs to a particular centre.

Current inventory:

| Candidate scope | Schools |
|---|---:|
| School-specific candidate | 520 |
| Shared operator-page candidate | 948 |
| Social-page candidate | 5 |
| Unavailable | 394 |

There are 659 normalised candidate URLs across 1,473 schools with at least one candidate.

## Run the inventory

From the repository root:

```powershell
.\.venv\Scripts\python.exe SystemCode\notebooks\poc1\scripts\build_website_inventory.py
```

Save the detailed JSON inventory:

```powershell
.\.venv\Scripts\python.exe SystemCode\notebooks\poc1\scripts\build_website_inventory.py --format json --output SystemCode\notebooks\poc1\output\website_inventory.json
```

Create a reviewable CSV:

```powershell
.\.venv\Scripts\python.exe SystemCode\notebooks\poc1\scripts\build_website_inventory.py --format csv --output SystemCode\notebooks\poc1\output\website_inventory.csv
```

## Identity-verification gate

Before fetching or indexing a page, verify at least two centre identifiers, such as centre name, address, postal code, centre code, and official operator domain. Shared operator pages may support operator-level claims only and must not be attributed to every branch as school-specific evidence.

## Remaining Phase 9 work

After reviewing a small pilot allowlist:

1. fetch approved official pages with rate limits and site-policy checks;
2. save retrieval date, final URL, content hash, title, and school ID;
3. extract main content and create school-isolated chunks;
4. retrieve passages only from the requested or selected school;
5. require citations for every school-specific claim; and
6. evaluate school isolation, citation correctness, unavailable evidence, and changed pages.

No webpage evidence should affect ranking until this evaluation passes.

