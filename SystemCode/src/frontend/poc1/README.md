# PoC 1 frontend

A Next.js interface for the PoC 1 pipeline. It uses a conversational prompt for non-sensitive preschool preferences and structured forms for child, household, and location details.

## Run

Start the PoC 1 FastAPI backend first, then:

```powershell
cd SystemCode/src/frontend/poc1
Copy-Item .env.local.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000`. The default API URL is `http://localhost:8000` and can be changed with `NEXT_PUBLIC_API_URL`.

The four-step flow is preference search, private eligibility calculation, centre selection and location entry, then the optimized route result.
