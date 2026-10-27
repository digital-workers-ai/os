async def _price(item, ctx):
    product, shelf_price = item.get("product"), item.get("shelf_price")
    if product is None or shelf_price is None:
        return None
    listed = await ctx.entity("product", "name", product, "price")
    if listed is None:
        return None
    return (
        "matches"
        if round(float(listed), 2) == round(float(shelf_price), 2)
        else "wrong"
    )


async def fill(record, ctx):
    items = [
        {**item, "price": await _price(item, ctx)} for item in record.get("items") or []
    ]
    return {**record, "items": items}
