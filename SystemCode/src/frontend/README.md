# Frontend

Next.js interface for the KinderCompass PoC 1 workflow.

From the repository root:

```powershell
npm install --prefix SystemCode/src/frontend
npm --prefix SystemCode/src/frontend run dev
```

The development server is available at `http://localhost:3000`. Configure its
backend URL in `SystemCode/src/frontend/.env.local`; the launcher creates that
file from `.env.local.example` when necessary.

See [the PoC 1 guide](../../../docs/poc1/Readme.md) for complete setup and usage.
