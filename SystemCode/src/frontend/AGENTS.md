# Frontend contributor guidance

This file supplements [`README.md`](README.md).

- Follow the Next.js App Router structure in `app/`: `layout.tsx` owns the root
  layout and metadata, `page.tsx` owns the client workflow, `LiveMap.tsx` owns
  the client-only Leaflet map, and `globals.css` owns shared styling.
- The browser integrates only with FastAPI. Do not connect frontend code
  directly to Neo4j, OneMap, OpenAI, or backend webpage-RAG resources, and do
  not duplicate backend ranking, eligibility, fee, or authoritative-data logic.
- Read the backend base URL from `NEXT_PUBLIC_API_URL`, retaining the documented
  local default when appropriate. This value is public and must never contain
  credentials; restart Next.js after changing it.
- Keep TypeScript strict: model API payloads explicitly, narrow nullable and
  unknown values, avoid `any`, and do not weaken `tsconfig.json` to bypass an
  error.

After frontend changes, run from `SystemCode/src`:

```bash
npm --prefix frontend run build
```

Put substantial, durable frontend design documentation in this project's `doc/` and
link it from this project's [`README.md`](README.md). Do not use `doc/` for
temporary notes or to duplicate README content.
