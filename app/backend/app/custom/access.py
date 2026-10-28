ADMIN = "admin"


def actor() -> str:
    return ADMIN


def roles() -> tuple[str, ...]:
    return (ADMIN,)


def may_open(app, roles) -> bool:
    return ADMIN in roles or not set(roles).isdisjoint(app.roles)
