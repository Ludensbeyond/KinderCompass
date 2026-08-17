def sample_preschool_keys(driver):
    """Return the property keys for a sample `Preschool` node (or [] if none)."""
    query = "MATCH (p:Preschool) RETURN keys(p) AS keys LIMIT 1"
    with driver.session() as session:
        rec = session.run(query).single()
        if rec:
            return rec["keys"]
    return []


def build_stage1_query(filters=None, include_base_fee=True):
    """Build a parameterized Cypher query for Stage 1.

    filters: dict may contain `town`, `level`, `philosophy` keys.
    Returns (query, params)
    """
    base_fields = "p.school_id AS school_id, p.centre_code AS centre_code, p.tp_code AS tp_code, p.name AS name"
    if include_base_fee:
        base_fields += (
            ", p.base_fee AS base_fee, p.operator_scheme AS operator_scheme,"
            " p.care_levels AS care_levels, p.philosophy AS philosophy, p.pedagogy AS pedagogy,"
            " p.second_languages_offered AS second_languages_offered,"
            " p.spark_certified AS spark_certified, p.service_model AS service_model,"
            " p.food_offered AS food_offered, p.weekday_full_day AS weekday_full_day,"
            " p.provision_of_transport AS provision_of_transport, p.last_updated AS last_updated"
        )

    where_clauses = []
    params = {}
    if filters:
        hard_constraints = filters.get("hard_constraints", {})
        if "level" in hard_constraints:
            where_clauses.append("c.name = $level")
            params["level"] = hard_constraints["level"]
        if "language" in hard_constraints:
            where_clauses.append("toLower(toString(p.second_languages_offered)) CONTAINS toLower($language)")
            params["language"] = hard_constraints["language"]
        if "town" in filters:
            location = str(filters["town"]).strip()
            if location.isdigit() and len(location) == 6:
                where_clauses.append("p.postal_code = $postal_code")
                params["postal_code"] = int(location)
            else:
                where_clauses.append("toLower(toString(t.name)) = toLower($town)")
                params["town"] = location
        if "level" in filters:
            where_clauses.append("c.name = $level")
            params["level"] = filters["level"]
        if "philosophy" in filters:
            # assumes `p.philosophy` is a property string; adjust if stored differently
            where_clauses.append("toLower(p.philosophy) CONTAINS toLower($philosophy)")
            params["philosophy"] = filters["philosophy"]
        if "pedagogy" in filters:
            where_clauses.append("toLower(p.pedagogy) CONTAINS toLower($pedagogy)")
            params["pedagogy"] = filters["pedagogy"]

    where = ""
    if where_clauses:
        where = "WHERE " + " AND ".join(where_clauses)

    query = f"""
MATCH (p:Preschool)
OPTIONAL MATCH (p)-[:LOCATED_IN]->(t:Town)
OPTIONAL MATCH (p)-[:SERVES_LEVEL]->(c:CareLevel)
WITH p, t, c
{where}
RETURN DISTINCT {base_fields}
"""
    return query, params
