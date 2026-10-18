"""Stage 1 Cypher: structured property filters plus graph-relationship constraints."""


def sample_preschool_keys(driver):
    """Return the property keys for a sample `Preschool` node (or [] if none)."""
    query = "MATCH (p:Preschool) RETURN keys(p) AS keys LIMIT 1"
    with driver.session() as session:
        rec = session.run(query).single()
        if rec:
            return rec["keys"]
    return []


def _path_map(rel: str, label: str, name_expr: str) -> str:
    return "{rel: '%s', label: '%s', name: %s}" % (rel, label, name_expr)


def build_stage1_query(filters=None, include_base_fee=True):
    """Build a parameterized Cypher query for Stage 1.

    Hard graph constraints (town name, care level, required language) use
    relationship MATCH. Postal code remains a Preschool property filter.
    Preferred SPARK, pedagogy, operator, food, and transport stay out of Cypher
    so unknown evidence is not treated as a failed must-have.

    Legacy top-level `philosophy` / `pedagogy` keys still filter through
    USES_PEDAGOGY for older callers and tests.

    Returns (query, params).
    """
    filters = filters or {}
    hard_constraints = filters.get("hard_constraints") or {}

    base_fields = (
        "p.school_id AS school_id, p.centre_code AS centre_code, p.tp_code AS tp_code, "
        "p.name AS name, p.postal_code AS postal_code"
    )
    if include_base_fee:
        base_fields += (
            ", p.base_fee AS base_fee, p.operator_scheme AS operator_scheme,"
            " p.care_levels AS care_levels, p.philosophy AS philosophy, p.pedagogy AS pedagogy,"
            " p.second_languages_offered AS second_languages_offered,"
            " p.spark_certified AS spark_certified, p.service_model AS service_model,"
            " p.food_offered AS food_offered, p.weekday_full_day AS weekday_full_day,"
            " p.provision_of_transport AS provision_of_transport, p.last_updated AS last_updated"
        )

    match_clauses = ["MATCH (p:Preschool)"]
    where_clauses = []
    params = {}
    aliases = ["p"]
    path_parts = []

    town = filters.get("town")
    if town is not None and str(town).strip():
        location = str(town).strip()
        if location.isdigit() and len(location) == 6:
            where_clauses.append("p.postal_code = $postal_code")
            params["postal_code"] = int(location)
            path_parts.append(_path_map("POSTAL_CODE", "Preschool", "toString(p.postal_code)"))
        else:
            match_clauses.append("MATCH (p)-[:LOCATED_IN]->(t:Town)")
            where_clauses.append("toLower(toString(t.name)) = toLower($town)")
            params["town"] = location
            aliases.append("t")
            path_parts.append(_path_map("LOCATED_IN", "Town", "t.name"))

    level = hard_constraints.get("level", filters.get("level"))
    if level:
        match_clauses.append("MATCH (p)-[:SERVES_LEVEL]->(c:CareLevel)")
        where_clauses.append("c.name = $level")
        params["level"] = level
        aliases.append("c")
        path_parts.append(_path_map("SERVES_LEVEL", "CareLevel", "c.name"))

    language = hard_constraints.get("language")
    if language:
        match_clauses.append("MATCH (p)-[:TEACHES_IN]->(lang:Language)")
        where_clauses.append("toLower(toString(lang.name)) = toLower($language)")
        params["language"] = language
        aliases.append("lang")
        path_parts.append(_path_map("TEACHES_IN", "Language", "lang.name"))

    pedagogy = filters.get("pedagogy")
    philosophy = filters.get("philosophy")
    pedagogy_value = pedagogy or philosophy
    if pedagogy_value:
        param_name = "pedagogy" if pedagogy else "philosophy"
        match_clauses.append("MATCH (p)-[:USES_PEDAGOGY]->(ped:Pedagogy)")
        where_clauses.append(f"toLower(toString(ped.name)) CONTAINS toLower(${param_name})")
        params[param_name] = pedagogy_value
        aliases.append("ped")
        path_parts.append(_path_map("USES_PEDAGOGY", "Pedagogy", "ped.name"))

    where = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    with_clause = "WITH DISTINCT " + ", ".join(aliases)
    path_expr = "[" + ", ".join(path_parts) + "]" if path_parts else "[]"

    query = f"""
{chr(10).join(match_clauses)}
{where}
{with_clause}
RETURN DISTINCT {base_fields}, {path_expr} AS retrieval_path
"""
    return query, params
