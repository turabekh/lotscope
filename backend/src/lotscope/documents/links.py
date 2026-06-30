from urllib.parse import quote


def philadox_document_url(template: str, document_id: str | None) -> str | None:
    if not document_id:
        return None
    return template.format(document_id=quote(document_id.strip(), safe=""))
