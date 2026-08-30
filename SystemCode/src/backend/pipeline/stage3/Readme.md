# Stage 3 — Home-to-preschool distance

Stage 3 takes one eligible preschool and the family's six-digit home postal code.
It resolves home through OneMap, joins the preschool to its ECDA coordinates,
and the web API requests a OneMap driving route:

```text
home -> selected preschool
```

There is no workplace destination, multiple-stop route, or genetic algorithm.

## Run

From the repository root:

```powershell
$env:PYTHONPATH = "SystemCode/src/backend/pipeline"
python -m stage3.runner `
  --input "SystemCode/src/backend/output/stage2_results.json" `
  --select "CENTRE:PT8718" `
  --home-postal-code "540231" `
  --output "SystemCode/src/backend/output/stage3_route.json"
```

`--select` accepts exactly one eligible `school_id` (or a legacy centre code in
older Stage 2 output). The web UI supports selecting multiple schools by calling
the route independently for each one. Its API result contains driving distance,
estimated duration, decoded road geometry, and a two-point schedule for the
live map. If routing fails, it returns a labelled Haversine straight-line
fallback without inventing a travel-duration estimate. The CLI runner remains
an offline straight-line calculation and does not call routing.

Every selected centre must have matching coordinates in the ECDA GeoJSON.
Driving duration is a routing estimate and is not presented as live traffic
time. Broad shortlist filtering continues to use straight-line distance so the
application does not issue a OneMap routing request for every candidate.
