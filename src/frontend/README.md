# Frontend

The KinderCompass website — parents search, compare, and explore preschool options.

## Planned stack

- **Next.js** (React)
- Calls the FastAPI backend in `src/backend/`

## Planned pages / features

| Page | Purpose |
|------|---------|
| Home | Search by location, programme type, budget |
| Centre detail | Full profile, services, licence history, map |
| Compare | Side-by-side comparison of selected centres |
| Recommend | Guided questionnaire → ranked suggestions |
| About | Project overview for practice module presentation |

## Planned structure

```
frontend/
├── app/ or pages/     # Routes
├── components/        # Reusable UI
├── lib/               # API client, helpers
└── public/            # Static assets
```

## Dev (future)

```bash
npm run dev
```

Backend must be running at the configured API URL.
