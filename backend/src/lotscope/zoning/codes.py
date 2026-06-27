def normalize_zoning_code(code: str) -> str:
    return code.upper().replace("-", "").replace(" ", "")
