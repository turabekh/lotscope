def resolved_zoning_code_sql(alias: str, resolved_alias: str | None = None) -> str:
    resolved = resolved_alias or alias
    return f"coalesce(nullif({alias}.base_zoning_code, ''), {resolved}.resolved_zoning_code)"
