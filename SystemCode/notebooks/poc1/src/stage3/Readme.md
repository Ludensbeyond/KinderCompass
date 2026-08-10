# Stage 3 — Home-to-preschool distance

Stage 3 takes one eligible preschool and the family's six-digit home postal code.
It resolves home through OneMap, joins the preschool to its ECDA coordinates,
and calculates the Haversine straight-line distance:

```text
home -> selected preschool
```

There is no workplace destination, multiple-stop route, or genetic algorithm.

## Run

From the repository root:

```powershell
$env:PYTHONPATH = "SystemCode/notebooks/poc1/src"
python -m stage3.runner `
  --input "SystemCode/notebooks/poc1/output/stage2_results.json" `
  --select "CENTRE:PT8718" `
  --home-postal-code "540231" `
  --output "SystemCode/notebooks/poc1/output/stage3_route.json"
```

`--select` accepts exactly one eligible `school_id` (or a legacy centre code in
older Stage 2 output). The web UI supports selecting multiple schools by calling
this calculation independently for each one. The result contains the resolved home and preschool coordinates,
the straight-line distance, and a two-point schedule for the live map.

Every selected centre must have matching coordinates in the ECDA GeoJSON. This
proof of concept does not calculate road distance, traffic, travel time, or
turn-by-turn directions.
