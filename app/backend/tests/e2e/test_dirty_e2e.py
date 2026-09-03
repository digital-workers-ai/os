import pytest
import pytest_asyncio
from sqlalchemy import func, select, text

from app.engine import run
from app.models import Base, CanonicalLink, EntityCanonical
from app.store import save_raw

pytestmark = pytest.mark.e2e


def hs_company(cid, domain, industry="Software", name="Acme"):
    return {
        "id": cid,
        "properties": {
            "domain": domain,
            "industry": industry,
            "name": name,
            "hs_lastmodifieddate": "2026-07-01T10:00:00.000Z",
        },
    }


def hs_contact(cid, email, first="Jane", last="Smith"):
    return {
        "id": cid,
        "properties": {
            "email": email,
            "firstname": first,
            "lastname": last,
            "lastmodifieddate": "2026-07-01T10:00:00.000Z",
        },
    }


def stripe_sub(sid, customer, items=True):
    payload = {
        "id": sid,
        "customer": customer,
        "status": "active",
        "currency": "usd",
        "start_date": 1719400000,
        "created": 1719400000,
    }
    payload["items"] = (
        {
            "data": [
                {
                    "quantity": 1,
                    "price": {
                        "unit_amount": 4900,
                        "recurring": {"interval": "month"},
                    },
                }
            ]
        }
        if items
        else {"data": []}
    )
    return payload


def cio_activity(did, email):
    return {
        "delivery_id": did,
        "type": "email_sent",
        "customer_id": email,
        "timestamp": 1720500000,
    }


@pytest_asyncio.fixture(scope="module")
async def dirty(db_engine, sessionmaker_for_test):
    tables = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
    async with db_engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))

    async with sessionmaker_for_test() as session:

        async def raw(source, object_type, source_id, payload):
            await save_raw(
                session,
                source=source,
                object_type=object_type,
                source_id=source_id,
                raw_payload=payload,
            )

        await raw(
            "hubspot",
            "companies",
            "hs_bad",
            hs_company("hs_bad", "not a domain", name="Broken Co"),
        )
        await raw(
            "hubspot",
            "companies",
            "hs_clear",
            hs_company("hs_clear", "clearco.io", industry=None, name="Clear Co"),
        )
        await raw(
            "stripe",
            "customers",
            "cus_free",
            {
                "id": "cus_free",
                "name": "Bootstrapped Ltd",
                "email": "founder@gmail.com",
                "created": 1719400000,
            },
        )
        await raw(
            "hubspot",
            "companies",
            "hs_hold",
            hs_company("hs_hold", "group.io", name="Holdings"),
        )
        await raw(
            "hubspot",
            "companies",
            "hs_sub",
            hs_company("hs_sub", "group.io", name="Subsidiary"),
        )
        for i in range(6):
            await raw(
                "hubspot",
                "contacts",
                f"hs_ap_{i}",
                hs_contact(f"hs_ap_{i}", "ap@shared.io", first=f"AP{i}"),
            )
        await raw(
            "hubspot", "contacts", "hs_dup_a", hs_contact("hs_dup_a", "dup@acme.io")
        )
        await raw(
            "hubspot", "contacts", "hs_dup_b", hs_contact("hs_dup_b", "dup@acme.io")
        )
        await raw(
            "customerio",
            "activities",
            "del_dup",
            cio_activity("del_dup", "dup@acme.io"),
        )
        await raw(
            "stripe",
            "subscriptions",
            "sub_orphan",
            stripe_sub("sub_orphan", "cus_ghost"),
        )
        await raw(
            "stripe",
            "subscriptions",
            "sub_noitems",
            stripe_sub("sub_noitems", "cus_free", items=False),
        )
        await raw(
            "google_ads",
            "campaigns",
            "camp_bad",
            {
                "campaign": {"id": "camp_bad"},
                "metrics": {"costMicros": "n/a", "conversions": "n/a"},
            },
        )
        await session.commit()

    async with sessionmaker_for_test() as session:
        return await run.rebuild(session)


@pytest_asyncio.fixture(scope="module")
async def dirty_report(dirty):
    return dirty["report"]


@pytest_asyncio.fixture
async def session(sessionmaker_for_test, dirty):
    async with sessionmaker_for_test() as s:
        yield s


class TestSkips:
    def test_a_refused_value_is_counted_by_label_source_and_reason(self, dirty_report):
        assert dirty_report["skips"]["domain/hubspot/not_a_domain"] == 1

    def test_a_hook_skip_lands_against_its_label(self, dirty_report):
        assert dirty_report["skips"]["mrr/stripe/no_subscription_items"] == 1

    def test_the_records_other_facts_still_landed(self, dirty_report):
        assert dirty_report["counts"]["records/hubspot/company"] == 4

    def test_a_record_with_no_usable_fact_is_counted(self, dirty_report):
        assert (
            dirty_report["records_skipped"]["google_ads/campaigns/no_facts/campaign"]
            == 1
        )


class TestClears:
    def test_a_present_null_is_a_clear_not_a_skip(self, dirty_report):
        assert dirty_report["clears"]["industry/hubspot"] == 1
        assert "industry/hubspot" not in dirty_report["skips"]

    def test_the_cleared_value_is_absent_from_the_canonical_layer(self, dirty_report):
        assert dirty_report["counts"]["cleared_canonical/company/industry"] == 1


class TestGuards:
    def test_a_mailbox_shared_inside_one_source_is_quarantined_whole(
        self, dirty_report
    ):
        buckets = [
            o
            for o in dirty_report["oversized"]
            if o["kind"] == "shared_across_records"
            and o["attr"] == "email"
            and "ap@" in o["value"]
        ]
        assert len(buckets) == 1
        assert buckets[0]["records"] == 6
        assert buckets[0]["sources"] == 1

    def test_two_records_from_one_source_never_share_a_cluster(self, dirty_report):
        shared = [
            o
            for o in dirty_report["oversized"]
            if o["kind"] == "shared_across_records" and "group.io" in o["value"]
        ]
        assert shared
        assert shared[0]["sources"] == 1

    def test_a_blocklisted_identity_value_leaves_the_record_orphaned_and_counted(
        self, dirty_report
    ):
        assert dirty_report["identity_less"]["company/stripe"] == 1
        assert (
            dirty_report["counts"]["identity_blocked/company/domain/free_mail_domain"]
            == 1
        )


class TestEdges:
    def test_a_ref_matching_no_target_is_counted_as_dangling(self, dirty_report):
        assert dirty_report["dangling_refs"]["subscription belongs_to company"] >= 1

    def test_a_record_matching_more_targets_than_declared_gets_no_link(
        self, dirty_report
    ):
        quarantines = dirty_report["quarantines"]
        assert quarantines
        assert any("expected 1" in q["detail"] for q in quarantines)

    async def test_the_quarantined_event_has_no_edge_at_all(self, session):
        links = (
            await session.execute(
                select(func.count())
                .select_from(CanonicalLink)
                .where(CanonicalLink.rel == "performed_by")
            )
        ).scalar_one()
        assert links == 0


class TestDeadPaths:
    def test_a_mapping_line_with_zero_hits_is_reported(self, dirty_report):
        dead = dirty_report["dead_paths"]
        assert "deal:hubspot.deals.properties.amount" in dead
        assert "campaign:google_ads.campaigns.campaign.name" in dead

    def test_only_present_sources_declare_paths(self, dirty_report):
        assert not any(":salesforce." in path for path in dirty_report["dead_paths"])

    def test_the_report_does_not_claim_to_be_clean(self, dirty_report):
        totals = dirty_report["totals"]
        assert totals["skips"] and totals["clears"]
        assert totals["quarantines"] and totals["oversized"]
        assert totals["dead_paths"] and totals["identity_less"]
        assert totals["records_skipped"] and totals["dangling_refs"]


class TestStillProducesAnswers:
    async def test_the_pipeline_did_not_stop_at_the_first_problem(self, session):
        canonical = (
            await session.execute(select(func.count()).select_from(EntityCanonical))
        ).scalar_one()
        assert canonical > 5
