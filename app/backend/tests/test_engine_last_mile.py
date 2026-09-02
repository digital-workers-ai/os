import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app import store
from app.engine import (
    links,
    mappings,
    metrics,
    ontology,
    pipeline,
    resolver,
    run,
    survivorship,
)
from app.engine.pipeline import ProjectedEntity, ProjectedFact
from app.engine.report import SyncReport
from app.models import (
    CanonicalAlias,
    CanonicalLink,
    CanonicalMember,
    Entity,
    EntityCanonical,
    EntityFact,
    FactCurrent,
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


class TestARebuildWritesTheEdges:
    async def test_a_subscription_link_lands_in_canonical_link(self, session):
        await store.save_raw(
            session,
            source="stripe",
            object_type="customers",
            source_id="cus_1",
            raw_payload={"id": "cus_1", "email": "billing@acme.io", "name": "Acme"},
        )
        await store.save_raw(
            session,
            source="stripe",
            object_type="subscriptions",
            source_id="sub_1",
            raw_payload={
                "id": "sub_1",
                "customer": "cus_1",
                "status": "active",
                "currency": "usd",
                "items": {
                    "data": [
                        {
                            "quantity": 1,
                            "price": {
                                "unit_amount": 1000,
                                "recurring": {"interval": "month"},
                            },
                        }
                    ]
                },
            },
        )
        await session.commit()
        result = await run.rebuild(session)

        assert result["links"] == 1
        link = (await session.execute(select(CanonicalLink))).scalar_one()
        assert link.rel == "belongs_to"
        assert link.grounding == "via:customer_ref"


class TestACampaignFedByTwoObjectTypes:
    async def _seed(self, session):
        await store.save_raw(
            session,
            source="meta",
            object_type="campaigns",
            source_id="camp_1",
            raw_payload={"id": "camp_1", "name": "Brand", "status": "ACTIVE"},
        )
        await store.save_raw(
            session,
            source="meta",
            object_type="insights",
            source_id="camp_1",
            raw_payload={
                "campaign_id": "camp_1",
                "account_id": "act_1",
                "spend": "10.00",
                "impressions": "5",
            },
        )
        await session.commit()

    async def test_a_rebuild_lands_one_canonical_campaign(self, session):
        await self._seed(session)
        result = await run.rebuild(session)

        assert result["report"]["counts"]["multi_object_entity/meta/campaign"] == 1
        canonicals = (
            (
                await session.execute(
                    select(EntityCanonical).where(
                        EntityCanonical.entity_type == "campaign"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(canonicals) == 1

    async def test_the_canonical_facts_come_from_both_object_types(self, session):
        await self._seed(session)
        await run.rebuild(session)

        canonical_id = (
            (
                await session.execute(
                    select(EntityCanonical.canonical_id).where(
                        EntityCanonical.entity_type == "campaign"
                    )
                )
            )
            .scalars()
            .one()
        )
        attrs = set(
            (
                await session.execute(
                    select(FactCurrent.attr).where(
                        FactCurrent.canonical_id == canonical_id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert {"name", "spend"} <= attrs


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
        folded = survivorship.fold([cluster], {}, onto, report)
        assert folded == []


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
            folded=[],
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
            folded=[],
            report=report,
        )
        assert len(edges) == 1


class TestAveragesOverEmptyPopulations:
    async def test_an_average_where_no_member_carries_the_attr_is_none(
        self, session, canonical
    ):
        from app.engine import metrics

        for _ in range(2):
            await canonical("deal", {"status": "open"})
        result = (
            await metrics.evaluate_definitions(
                session, {"avg_deal": {"entity": "deal", "expression": "AVG(amount)"}}
            )
        )["avg_deal"]
        assert result["value"] is None
        assert result["entities"] == 2

    async def test_a_sum_over_the_same_population_is_zero(self, session, canonical):
        from app.engine import metrics

        for _ in range(2):
            await canonical("deal", {"status": "open"})
        result = (
            await metrics.evaluate_definitions(
                session, {"total": {"entity": "deal", "expression": "SUM(amount)"}}
            )
        )["total"]
        assert result["value"] == 0

    async def test_the_payload_says_how_many_members_carried_the_attr(
        self, session, canonical
    ):
        from app.engine import metrics

        await canonical("deal", {"amount": "100"})
        await canonical("deal", {"status": "open"})
        result = (
            await metrics.evaluate_definitions(
                session, {"avg_deal": {"entity": "deal", "expression": "AVG(amount)"}}
            )
        )["avg_deal"]
        assert result["entities_without_attr"] == 1


class TestMetricsFileThatRaisesDuringChecks:
    def test_a_metrics_file_the_loader_rejects_is_reported_by_the_build(self, tmp_path):
        import shutil
        from pathlib import Path

        from app import caches
        from app.engine import checks

        for name in (
            "mappings.yaml",
            "ontology.yaml",
            "transforms.yaml",
            "metrics.yaml",
            "rules.yaml",
            "goals.yaml",
        ):
            shutil.copy(Path(caches.BACKEND_DIR) / name, tmp_path / name)
        (tmp_path / "metrics.yaml").write_text("- not\n- a\n- mapping\n")

        problems = checks.run(
            mapping_paths=[tmp_path / "mappings.yaml"],
            ontology_path=tmp_path / "ontology.yaml",
            transforms_path=tmp_path / "transforms.yaml",
            metrics_path=tmp_path / "metrics.yaml",
            rules_path=tmp_path / "rules.yaml",
            goals_path=tmp_path / "goals.yaml",
        )
        assert any(p.startswith("metrics:") for p in problems)
        assert len(problems) > 1


class TestEnrichedMetricSpecs:
    def _spec(self, **overrides):
        spec = {
            "entity": "meeting",
            "source": "enriched",
            "inferred": True,
            "reading": "sales_call",
            "expression": "COUNT(entity)",
        }
        spec.update(overrides)
        return spec

    def test_a_field_the_reading_does_not_declare_is_refused(self):
        with pytest.raises(metrics.MetricSpecError, match="is not a field of reading"):
            metrics.parse_spec(self._spec(expression="COUNT(never_declared)"))

    def test_summing_a_label_is_refused_as_a_category_error(self):
        with pytest.raises(metrics.MetricSpecError, match="category error"):
            metrics.parse_spec(self._spec(expression="SUM(pain_points)"))

    def test_an_unknown_population_is_refused(self):
        with pytest.raises(metrics.MetricSpecError):
            metrics.parse_spec(self._spec(population="everyone"))

    @pytest.mark.parametrize("population", ["read", "all"])
    def test_the_two_declared_populations_are_accepted(self, population):
        assert metrics.parse_spec(self._spec(population=population))

    def test_a_reading_that_does_not_exist_is_refused(self):
        with pytest.raises(metrics.MetricSpecError, match="not declared in enrichment"):
            metrics.parse_spec(self._spec(reading="tea_leaves"))

    def test_a_window_on_an_inferred_metric_is_refused(self):
        with pytest.raises(metrics.MetricSpecError, match="never ran"):
            metrics.parse_spec(self._spec(window_days=30))
