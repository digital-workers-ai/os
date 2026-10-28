def _change(line, last_counts):
    before, counted = last_counts.get(line.get("product")), line.get("counted")
    if before is None or counted is None:
        return None
    return counted - before


async def fill(record, ctx):
    last = await ctx.previous({"location": record.get("location")}) or {}
    last_counts = {
        line.get("product"): line.get("counted") for line in last.get("lines") or []
    }
    lines = [
        {**line, "change": _change(line, last_counts)}
        for line in record.get("lines") or []
    ]
    return {**record, "lines": lines}
