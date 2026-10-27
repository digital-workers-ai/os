import pytest

from app.custom import access
from app.engine import apps


@pytest.fixture
def receipts():
    return apps.load("receipts")


def test_the_admin_role_is_named_admin():
    assert access.ADMIN == "admin"


def test_the_actor_is_admin_until_sign_in():
    assert access.actor() == "admin"


def test_the_actor_holds_only_the_admin_role():
    assert access.roles() == ("admin",)


def test_admin_opens_an_app_that_does_not_name_admin(receipts):
    assert "admin" not in receipts.roles
    assert access.may_open(receipts, ("admin",)) is True


def test_admin_among_other_roles_still_opens_the_app(receipts):
    assert access.may_open(receipts, ("driver", "admin")) is True


def test_the_actors_own_roles_open_every_shipped_app():
    shipped = apps.apps().values()
    assert shipped
    assert all(access.may_open(app, access.roles()) for app in shipped)


def test_a_role_the_app_names_opens_it(receipts):
    assert access.may_open(receipts, ("finance",)) is True


def test_one_shared_role_among_several_is_enough(receipts):
    assert access.may_open(receipts, ("driver", "staff")) is True


def test_a_role_the_app_does_not_name_is_refused(receipts):
    assert access.may_open(receipts, ("driver",)) is False


def test_several_roles_none_of_them_named_are_refused(receipts):
    assert access.may_open(receipts, ("driver", "dentist")) is False


def test_no_roles_open_nothing(receipts):
    assert access.may_open(receipts, ()) is False
