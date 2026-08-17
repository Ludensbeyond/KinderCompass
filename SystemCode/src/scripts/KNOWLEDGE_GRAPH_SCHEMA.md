# KinderCompass Neo4j Knowledge Graph Schema

This document is the authoritative reference for how the processed preschool
catalogue is represented in Neo4j. The graph is created by
`build_knowledge_graph.py` from
`SystemCode/data/processed/kindercompass_master.json`.

## Graph overview

```text
(Preschool)-[:LOCATED_IN]->(Town)
(Preschool)-[:SERVES_LEVEL]->(CareLevel)
(Preschool)-[:TEACHES_IN]->(Language)
(Preschool)-[:USES_PEDAGOGY]->(Pedagogy)
(Preschool)-[:PARTICIPATES_IN]->(OperatorScheme)
(Preschool)-[:HAS_CERTIFICATION]->(Certification)
```

`Preschool` is the central entity. Reusable concepts that are shared across
schools and useful for graph traversal are represented as nodes. Scalar values
that primarily describe one school remain properties.

## Node labels

| Label | Identity property | Purpose |
|---|---|---|
| `Preschool` | `school_id` | One ECDA preschool record. |
| `Town` | `name` | Planning area containing a preschool. |
| `CareLevel` | `name` | Care or education level offered by a preschool. |
| `Language` | `name` | Second language recorded as offered by a preschool. |
| `Pedagogy` | `name` | Teaching approach inferred or recorded for a preschool. |
| `OperatorScheme` | `name` | ECDA operator scheme associated with a preschool. |
| `Certification` | `name` | Certification associated with a preschool; currently `SPARK`. |

## Preschool properties

| Property | Type | Meaning or source |
|---|---|---|
| `school_id` | String | Stable identifier assembled from centre code or TP code. |
| `centre_code` | String or null | ECDA centre code. |
| `tp_code` | String or null | Alternative TP identifier. |
| `identifier_type` | String | Identifier used to construct `school_id`. |
| `name` | String | Preschool name. |
| `postal_code` | Integer or null | Registered postal code. |
| `longitude` | Float or null | Longitude parsed from the ECDA location GeoJSON. |
| `latitude` | Float or null | Latitude parsed from the ECDA location GeoJSON. |
| `base_fee` | Float or null | Lowest available fee in the processed service records. |
| `operator_scheme` | String or null | Compatibility property corresponding to `OperatorScheme`. |
| `care_levels` | List of strings | Compatibility property corresponding to `CareLevel` relationships. |
| `philosophy` | String or null | Conservatively inferred philosophy label. |
| `pedagogy` | String or null | Compatibility property corresponding to `Pedagogy`. |
| `second_languages_offered` | String or null | Source language field retained for compatibility. |
| `spark_certified` | String or null | Source SPARK value retained for compatibility. |
| `service_model` | String or null | ECDA service model. |
| `food_offered` | String or null | Recorded food arrangement. |
| `weekday_full_day` | String or null | Recorded weekday operating hours. |
| `provision_of_transport` | String or null | Recorded transport provision. |
| `last_updated` | String or null | Source catalogue update date. |

The compatibility properties remain because the current Stage 1 query and
ranking code reads them. They may coexist with normalized relationships until
all consumers have migrated.

## Relationships

| Relationship | From | To | Meaning |
|---|---|---|---|
| `LOCATED_IN` | `Preschool` | `Town` | The school lies within the planning area. |
| `SERVES_LEVEL` | `Preschool` | `CareLevel` | The school offers the care level. |
| `TEACHES_IN` | `Preschool` | `Language` | The record states that the language is offered. It does not establish teaching quality or intensity. |
| `USES_PEDAGOGY` | `Preschool` | `Pedagogy` | The processed record associates the school with the pedagogy. Most values are conservatively inferred from the school name. |
| `PARTICIPATES_IN` | `Preschool` | `OperatorScheme` | The school is recorded under the operator scheme. |
| `HAS_CERTIFICATION` | `Preschool` | `Certification` | The school has the recorded certification. Currently created only when SPARK is `Yes`. |

Relationships are directed from `Preschool` to the reusable concept, although
Cypher queries may traverse them in either direction.

## Why properties and nodes are used

Use a property when a value is scalar, mainly describes one school, and does not
need independent metadata or traversal. Examples include postal code, base fee,
coordinates, operating hours, and transport provision.

Use a node when a concept is shared by many schools and is useful for exact
matching, traversal, comparison, or future metadata. This is why town, care
level, language, pedagogy, operator scheme, and certification are nodes.

Some information is intentionally represented both ways during migration. The
relationship is the normalized graph representation, while the property keeps
existing application queries compatible.

## Constraints and indexes

The loader creates uniqueness constraints for:

- `Preschool.school_id`
- `Town.name`
- `CareLevel.name`
- `Language.name`
- `Pedagogy.name`
- `OperatorScheme.name`
- `Certification.name`

It also creates an index on `Preschool.name`.

Inspect the live definitions with:

```cypher
SHOW CONSTRAINTS;
SHOW INDEXES;
```

## Source mapping

| Graph information | Primary processed source |
|---|---|
| Preschool identity and operational properties | `ListingofCentres.csv` |
| Care levels and base fee | `ListingofCentreServices.csv` |
| Coordinates and centre-code location match | `PreSchoolsLocation.geojson` |
| Town | Spatial join with `MasterPlan2025PlanningArea.geojson` |
| Licence-derived fields | `ListingofCentresLicenceHistory.csv` |

The processed catalogue is the immediate graph input. Consult the data pipeline
guide for preparation and refresh instructions.

## Example queries

Show one school and all its connected concepts:

```cypher
MATCH (p:Preschool)
WHERE toLower(p.name) CONTAINS "star learners"
OPTIONAL MATCH (p)-[r]->(concept)
RETURN p, r, concept;
```

Find Chinese-language SPARK-certified schools:

```cypher
MATCH (p:Preschool)-[:TEACHES_IN]->(:Language {name: "Chinese"})
MATCH (p)-[:HAS_CERTIFICATION]->(:Certification {name: "SPARK"})
RETURN p.name
ORDER BY p.name;
```

Find schools by several connected concepts:

```cypher
MATCH (p:Preschool)-[:LOCATED_IN]->(:Town {name: "WOODLANDS"})
MATCH (p)-[:TEACHES_IN]->(:Language {name: "Chinese"})
MATCH (p)-[:SERVES_LEVEL]->(:CareLevel {name: "Nursery (4 yrs old)"})
RETURN p.name;
```

## Refresh behaviour

Normal graph builds are non-destructive. The loader upserts schools, replaces
their current concept relationships, and removes concept nodes that are no
longer connected to any school. It does not delete the entire database unless
the explicit `--clear-existing` option is supplied.

```powershell
.\.venv\Scripts\python.exe -m SystemCode.src.scripts.build_knowledge_graph
```

## Current limitations

- Detailed fees remain nested in the processed catalogue rather than modelled as
  service-offering nodes.
- Pedagogy is generally inferred from school-name keywords and must not be
  presented as independently verified teaching practice.
- A language relationship confirms only that the source record lists the
  language; it does not establish instructional intensity or quality.
- Provenance is documented by the application and source fields but is not yet
  represented with dedicated evidence nodes.
- Stage 1 still reads compatibility properties for filtering and ranking; the
  normalized relationships currently support exploration and future migration.
