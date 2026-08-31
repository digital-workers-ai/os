import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app import store
from app.engine import links, mappings, ontology, pipeline, resolver, run, survivorship
from app.engine.pipeline import ProjectedEntity, ProjectedFact
from app.engine.report import SyncReport
from app.models import (
    CanonicalAlias,
    CanonicalMember,
    Entity,
    EntityCanonical,
    EntityFact,
)

INGESTED = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


class TestAccountCurrencyFallback:
    def test_a_connector_declaring_a_nonsense_currency_is_refused_and_counted(self):
        module = type(
            "M", (), {"SOURCE": "hubspot", "ACCOUNT_CURRENCY": "not a currency code"}
        )
        report = SyncReport()
        pipeline.project_payload(
            source="hubspot",
            object_type="deals",
            source_id="d1",
            payload={"properties": {"dealname": "Acme deal", "amount": "100"}},
            raw_event_id=None,
            ingested_at=INGESTED,
            seq=1,
            onto=ontology.load(),
            line_index=mappings.by_object(mappings.load()),
            transform_map={"amount": "normalize_money"},
            report=report,
            connector_module=module,
        )
        skips = str(report.as_dict())
        assert "account_level" in skips


class TestARebuildWritesTheProjection:
    async def test_entities_and_facts_land_with_deterministic_ids(self, session):
        await store.save_raw(
            session,
            source="hubspot",
            object_type="companies",
            source_id="c1",
            raw_payload={"properties": {"domain": "acme.io", "name": "Acme"}},
        )
        result = await run.rebuild(session)
        assert (result["entities"], result["facts"]) == (1, 2)
        entity = (await session.execute(select(Entity))).scalar_one()
        assert entity.id == uuid.uuid5(run.NAMESPACE, "entity|hubspot|company|c1")
        assert entity.first_seq == 1
        attrs = sorted((await session.execute(select(EntityFact.attr))).scalars().all())
        assert attrs == ["domain", "name"]


class TestTwoRebuildsCannotCollide:
    async def test_a_second_rebuild_is_refused_while_one_holds_the_lock(
        self, session, sessionmaker_for_test
    ):
        async with sessionmaker_for_test() as holder:
            await holder.execute(
                select(func.pg_try_advisory_xact_lock(run._REBUILD_LOCK_ID))
            )
            with pytest.raises(run.RebuildInProgress):
                await run.rebuild(session)

    async def test_an_uncontended_rebuild_runs(self, session):
        assert (await run.rebuild(session))["ok"] is True

    async def test_the_lock_is_released_for_the_next_rebuild(self, session):
        await run.rebuild(session)
        assert (await run.rebuild(session))["ok"] is True


class TestTheCanonicalAnchorDoesNotMoveWhenAMemberIsEdited:
    async def _seed(self, session):
        await store.save_raw(
            session,
            source="hubspot",
            object_type="companies",
            source_id="c1",
            raw_payload={
                "id": "c1",
                "properties": {"domain": "acme.io", "name": "Acme"},
            },
        )
        await store.save_raw(
            session,
            source="stripe",
            object_type="customers",
            source_id="cus_1",
            raw_payload={"id": "cus_1", "email": "billing@acme.io", "name": "Acme"},
        )
        await session.commit()

    async def _edit_anchor(self, session, name):
        await store.save_raw(
            session,
            source="hubspot",
            object_type="companies",
            source_id="c1",
            raw_payload={"id": "c1", "properties": {"domain": "acme.io", "name": name}},
        )
        await session.commit()

    async def _canonical_id(self, session):
        return (
            (
                await session.execute(
                    select(EntityCanonical.canonical_id).where(
                        EntityCanonical.entity_type == "company"
                    )
                )
            )
            .scalars()
            .one()
        )

    async def test_editing_the_anchor_member_keeps_the_canonical_id(self, session):
        await self._seed(session)
        await run.rebuild(session)
        before = await self._canonical_id(session)

        await self._edit_anchor(session, "Acme Corp")
        await run.rebuild(session)

        assert await self._canonical_id(session) == before

    async def test_the_anchor_key_itself_is_unchanged(self, session):
        await self._seed(session)
        await run.rebuild(session)

        await self._edit_anchor(session, "Renamed")
        await run.rebuild(session)

        anchor = (
            (
                await session.execute(
                    select(EntityCanonical.anchor_key).where(
                        EntityCanonical.entity_type == "company"
                    )
                )
            )
            .scalars()
            .one()
        )
        assert anchor == "hubspot|company|c1"


class TestMemberCountMatchesTheMembersItLists:
    async def test_a_healthy_cluster_counts_every_member(self, session):
        await store.save_raw(
            session,
            source="hubspot",
            object_type="companies",
            source_id="c1",
            raw_payload={
                "id": "c1",
                "properties": {"domain": "acme.io", "name": "Acme"},
            },
        )
        await store.save_raw(
            session,
            source="stripe",
            object_type="customers",
            source_id="cus_1",
            raw_payload={"id": "cus_1", "email": "billing@acme.io", "name": "Acme"},
        )
        await session.commit()
        await run.rebuild(session)

        row = (
            (
                await session.execute(
                    select(EntityCanonical).where(
                        EntityCanonical.entity_type == "company"
                    )
                )
            )
            .scalars()
            .one()
        )
        listed = (
            await session.execute(
                select(func.count())
                .select_from(CanonicalMember)
                .where(CanonicalMember.canonical_id == row.canonical_id)
            )
        ).scalar_one()
        assert row.member_count == listed
        assert row.member_count == 2


class TestAnIdThatStopsExistingLeavesATrace:
    async def _company(self, session, source_id, properties):
        await store.save_raw(
            session,
            source="hubspot",
            object_type="companies",
            source_id=source_id,
            raw_payload={"id": source_id, "properties": properties},
        )

    async def _customer(self, session, source_id, email):
        await store.save_raw(
            session,
            source="stripe",
            object_type="customers",
            source_id=source_id,
            raw_payload={"id": source_id, "email": email, "name": "Globex"},
        )

    async def test_a_cluster_whose_values_were_all_cleared_is_retired(self, session):
        await self._company(session, "c1", {"domain": "acme.io", "name": "Acme"})
        await session.commit()
        await run.rebuild(session)
        before = (
            (
                await session.execute(
                    select(EntityCanonical.canonical_id).where(
                        EntityCanonical.entity_type == "company"
                    )
                )
            )
            .scalars()
            .one()
        )

        await self._company(session, "c1", {"domain": None, "name": None})
        await session.commit()
        await run.rebuild(session)

        assert (
            await session.execute(
                select(func.count())
                .select_from(EntityCanonical)
                .where(EntityCanonical.entity_type == "company")
            )
        ).scalar_one() == 0
        alias = await session.get(CanonicalAlias, before)
        assert alias is not None
        assert alias.reason == "retired"

    async def test_an_id_absorbed_into_an_older_cluster_points_at_it(self, session):
        await self._company(session, "c1", {"domain": "acme.io", "name": "Acme"})
        await self._customer(session, "cus_1", "billing@globex.com")
        await session.commit()
        await run.rebuild(session)
        before = dict(
            (
                await session.execute(
                    select(
                        EntityCanonical.anchor_key, EntityCanonical.canonical_id
                    ).where(EntityCanonical.entity_type == "company")
                )
            ).all()
        )
        assert len(before) == 2

        await self._customer(session, "cus_1", "billing@acme.io")
        await session.commit()
        await run.rebuild(session)

        survivor = (
            (
                await session.execute(
                    select(EntityCanonical.canonical_id).where(
                        EntityCanonical.entity_type == "company"
                    )
                )
            )
            .scalars()
            .one()
        )
        assert survivor == before["hubspot|company|c1"]
        alias = await session.get(CanonicalAlias, before["stripe|company|cus_1"])
        assert alias is not None
        assert alias.canonical_id == survivor
        assert alias.reason != "retired"

    async def test_a_surviving_cluster_writes_no_spurious_alias(self, session):
        await self._company(session, "c1", {"domain": "acme.io", "name": "Acme"})
        await session.commit()
        await run.rebuild(session)
        await run.rebuild(session)

        assert (
            await session.execute(select(func.count()).select_from(CanonicalAlias))
        ).scalar_one() == 0


class TestSurvivorshipSkipsAbsentMembers:
    def test_a_cluster_member_with_no_projected_record_is_skipped(self):
        onto = ontology.load()
        report = SyncReport()
        cluster = resolver.Cluster(
            canonical_id=uuid.uuid4(),
            entity_type="company",
            anchor_key="hubspot|company|c1",
            minted_order=1,
        )
        cluster.members[("hubspot", "company", "c1")] = "domain=acme.io"
        folded, retired = survivorship.fold([cluster], {}, onto, report)
        assert (folded, retired) == ([], [])


class TestSelfReferentialEdges:
    def _onto(self):
        company = ontology.EntitySpec(
            name="company",
            attrs={"domain": "string", "parent_ref": "string"},
            identity=("domain",),
        )
        rel = ontology.Relationship(
            rel="parent_of",
            from_type="company",
            to_type="company",
            cardinality="many_to_one",
            via="parent_ref",
        )
        return ontology.Ontology(
            entities={"company": company},
            relationships=(rel,),
            source_priority=(),
        )

    def _entity(self, source_id, parent_ref):
        return ProjectedEntity(
            source="hubspot",
            entity_type="company",
            source_id=source_id,
            object_type="companies",
            first_seq=1,
            facts={
                "parent_ref": ProjectedFact(
                    attr="parent_ref",
                    value=parent_ref,
                    value_num=None,
                    raw_event_id=None,
                    observed_at=INGESTED,
                    observed_at_source="ingested",
                    seq=1,
                )
            },
        )

    def test_a_record_pointing_at_its_own_cluster_produces_no_edge(self):
        report = SyncReport()
        key = ("hubspot", "company", "c1")
        edges = links.build(
            self._onto(),
            projected={key: self._entity("c1", "c1")},
            of_record={key: "canonical-1"},
            report=report,
        )
        assert edges == []

    def test_a_record_pointing_at_a_different_cluster_produces_one_edge(self):
        report = SyncReport()
        child = ("hubspot", "company", "c1")
        parent = ("hubspot", "company", "c2")
        edges = links.build(
            self._onto(),
            projected={
                child: self._entity("c1", "c2"),
                parent: self._entity("c2", ""),
            },
            of_record={child: "canonical-1", parent: "canonical-2"},
            report=report,
        )
        assert len(edges) == 1
