def resolved_zoning_code_sql(alias: str, resolved_alias: str | None = None) -> str:
    resolved = resolved_alias or alias
    return f"coalesce(nullif({alias}.base_zoning_code, ''), {resolved}.resolved_zoning_code)"


def normalized_name_sql(column: str) -> str:
    return (
        "nullif(upper(btrim("
        f"regexp_replace(regexp_replace({column}, '[.,#]', '', 'g'), '\\s+', ' ', 'g')"
        ")), '')"
    )


def package_deed_exclusion_sql(alias: str) -> str:
    return (
        f"({alias}.document_id IS NULL OR NOT EXISTS ("
        f"SELECT 1 FROM sale pkg WHERE pkg.document_id = {alias}.document_id "
        f"AND pkg.parcel_number <> {alias}.parcel_number))"
    )


def future_sale_exclusion_sql(alias: str) -> str:
    return f"{alias}.sale_date <= CURRENT_DATE"
