async def fill(record, ctx):
    if record.get("stage") != "end":
        return {**record, "miles": None}
    start = await ctx.previous({"vehicle": record.get("vehicle"), "stage": "start"})
    began = None if start is None else start.get("odometer")
    ended = record.get("odometer")
    if began is None or ended is None or ended < began:
        return {**record, "miles": None}
    return {**record, "miles": ended - began}
