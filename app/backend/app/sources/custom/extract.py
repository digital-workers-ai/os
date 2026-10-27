from app.engine import apps

CARRIED = ("currency", "recorded_at", "recorded_by", "transcript")
TEMPLATE_PARTS = (
    ("rows", "row", ("row",)),
    ("cells", "cell", ("row", "column")),
    ("items", "item", ("section", "item")),
)


def _value(field, value):
    if value is None:
        return None
    if field.type == "lookup":
        return str(value)
    if field.type == "many_of":
        return ", ".join(value) or None
    return value


def _landed(fields, values: dict, prefix: str = "") -> dict:
    return {
        f"{prefix}{field.name}": _value(field, values[field.name])
        for field in fields
        if field.type != "list" and field.name in values
    }


def _scanned(fields, parent: dict) -> list[dict]:
    return [
        {"_source_id": parent[field.name], f"_{field.name}": parent[field.name]}
        for field in fields
        if field.type == "lookup" and field.from_scan and parent.get(field.name)
    ]


def _list_rows(record: str, field, rows: list) -> list[dict]:
    prefix = f"_{field.name}_"
    return [
        {
            "_source_id": f"{record}:{field.name}:{index}",
            f"{prefix}parent": record,
            **_landed(field.fields, row, prefix),
        }
        for index, row in enumerate(rows)
    ]


def _template_children(record: str, template, given: dict) -> list[dict]:
    children = []
    for part, singular, names in TEMPLATE_PARTS:
        spec = getattr(template, part)
        if spec is None:
            continue
        prefix = f"_{part}_"
        for key, values in given.get(part, {}).items():
            place = zip(names, key.split(":", len(names) - 1), strict=True)
            children.append(
                {
                    "_source_id": f"{record}:{singular}:{key}",
                    f"{prefix}parent": record,
                    **{f"{prefix}{name}": value for name, value in place},
                    **_landed(spec["fields"], values, prefix),
                }
            )
    return children


def reshape(object_type: str, payload: dict) -> list[dict]:
    if payload["removed"]:
        return []
    app = apps.load(object_type)
    record = payload["record"]
    fields = payload["fields"]
    parent = {
        "_source_id": record,
        **_landed(app.fields, fields),
        **{key: payload[key] for key in CARRIED if key in payload},
    }
    children = [
        child
        for field in app.fields
        if field.type == "list"
        for child in _list_rows(record, field, fields.get(field.name) or [])
    ]
    if app.template is not None:
        children += _template_children(
            record, app.template, payload.get("template", {})
        )
    return [parent, *_scanned(app.fields, parent), *children]
