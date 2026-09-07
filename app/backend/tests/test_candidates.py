from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import select

from app import store
from app.engine import candidates, ontology, resolver, run
from app.engine.ontology import CandidateSpec
from app.engine.report import SyncReport
from app.models import (
    CanonicalMember,
    Entity,
    MergeCandidate,
    MergeCandidateEvidence,
)

ONTO = ontology.load()
PERSON = ONTO.candidates("person")
PHONE = "+14155550101"


def person(source, source_id, order, **values):
    return resolver.Record(
        source=source,
        entity_type="person",
        source_id=source_id,
        order=order,
        identity=values,
    )


def company(source, source_id, order, **values):
    return resolver.Record(
        source=source,
        entity_type="company",
        source_id=source_id,
        order=order,
        identity=values,
    )


def nominate(records):
    resolution = resolver.resolve(records, ONTO, SyncReport())
    return candidates.generate(records, ONTO, resolution["of_record"])


class TestNamesLookAlike:
    def test_an_initial_and_a_prefix_score_the_floor(self):
        assert candidates.name_score("Carlos Ch", "C Chinchilla") == 0.8

    def test_the_same_name_scores_one(self):
        assert candidates.name_score("Carlos Chinchilla", "Carlos Chinchilla") == 1.0

    def test_two_different_people_are_not_alike(self):
        assert candidates.name_score("Carlos Chinchilla", "Maria Lopez") is None

    def test_a_nickname_is_not_alike_yet(self):
        assert candidates.name_score("Bob Chen", "Robert Chen") is None

    def test_case_punctuation_and_spacing_do_not_matter(self):
        assert candidates.name_score("maria   LOPEZ", "M. Lopez") == 0.8

    def test_a_close_spelling_scores_its_ratio(self):
        score = candidates.name_score("Rich Hendricks", "Richard Hendricks")
        assert 0.8 <= score < 1.0

    def test_a_single_token_cannot_use_the_prefix_rule(self):
        assert candidates.name_score("Carlos", "C Chinchilla") is None

    def test_a_prefix_needs_two_letters(self):
        assert candidates.name_score("Carlos C", "C Chinchilla") is None

    def test_an_empty_name_is_never_alike(self):
        assert candidates.name_score("", "Carlos Chinchilla") is None
        assert candidates.name_score(None, None) is None


class TestCorroboration:
    def test_a_shared_phone_nominates_the_pair(self):
        found = nominate(
            [
                person("zendesk", "u_1", 1, name="Carlos Ch", phone=PHONE),
                person("intercom", "con_1", 2, name="C Chinchilla", phone=PHONE),
            ]
        )
        assert len(found) == 1
        found = found[0]
        assert (found.entity_type, found.left, found.right, found.score) == (
            "person",
            "intercom|person|con_1",
            "zendesk|person|u_1",
            0.8,
        )
        assert found.evidence == (
            ("name", "C Chinchilla", "Carlos Ch"),
            ("phone", PHONE, PHONE),
        )

    def test_phone_formatting_does_not_matter(self):
        found = nominate(
            [
                person(
                    "zendesk", "u_1", 1, name="Carlos Ch", phone="+1 (415) 555-0101"
                ),
                person("intercom", "con_1", 2, name="C Chinchilla", phone="4155550101"),
            ]
        )
        assert len(found) == 1

    def test_a_shared_company_domain_nominates_the_pair(self):
        found = nominate(
            [
                person("zendesk", "u_1", 1, name="Maria Lopez", email="maria@acme.io"),
                person("intercom", "con_1", 2, name="M. Lopez", email="ml@acme.io"),
            ]
        )
        assert len(found) == 1
        assert found[0].evidence == (
            ("name", "M. Lopez", "Maria Lopez"),
            ("email_domain", "acme.io", "acme.io"),
        )

    def test_a_free_mail_domain_is_not_evidence(self):
        found = nominate(
            [
                person(
                    "zendesk", "u_1", 1, name="Maria Lopez", email="maria@gmail.com"
                ),
                person("intercom", "con_1", 2, name="M. Lopez", email="ml@gmail.com"),
            ]
        )
        assert found == []

    def test_alike_names_alone_are_not_enough(self):
        found = nominate(
            [
                person("zendesk", "u_1", 1, name="Carlos Ch", phone=PHONE),
                person(
                    "intercom", "con_1", 2, name="C Chinchilla", phone="+14155550199"
                ),
            ]
        )
        assert found == []

    def test_a_shared_phone_with_a_different_name_is_not_enough(self):
        found = nominate(
            [
                person("zendesk", "u_1", 1, name="Jane Smith", phone=PHONE),
                person("intercom", "con_1", 2, name="Carlos Ch", phone=PHONE),
            ]
        )
        assert found == []

    def test_a_pair_already_tied_by_an_identifier_is_not_nominated(self):
        found = nominate(
            [
                person("zendesk", "u_1", 1, name="Carlos Ch", email="c@acme.io"),
                person("intercom", "con_1", 2, name="C Chinchilla", email="c@acme.io"),
            ]
        )
        assert found == []

    def test_two_records_of_one_source_may_pair(self):
        found = nominate(
            [
                person("hubspot", "p_1", 1, name="Carlos Ch", phone=PHONE),
                person("hubspot", "p_2", 2, name="C Chinchilla", phone=PHONE),
            ]
        )
        assert len(found) == 1

    def test_a_shared_phone_finds_a_pair_the_name_block_misses(self):
        found = nominate(
            [
                person("zendesk", "u_1", 1, name="Karlos Chinchilla", phone=PHONE),
                person("intercom", "con_1", 2, name="Carlos Chinchilla", phone=PHONE),
            ]
        )
        assert len(found) == 1
        assert found[0].score > 0.8

    def test_a_record_with_no_name_is_never_nominated(self):
        found = nominate(
            [
                person("zendesk", "u_1", 1, phone=PHONE),
                person("intercom", "con_1", 2, name="C Chinchilla", phone=PHONE),
            ]
        )
        assert found == []

    def test_an_entity_without_a_candidates_block_is_skipped(self):
        found = nominate(
            [
                company("hubspot", "c_1", 1, name="Acme", domain="acme.io"),
                company("stripe", "cus_1", 2, name="Acme Inc", domain="acme-eu.io"),
            ]
        )
        assert found == []

    def test_a_plain_corroborator_agrees_on_equal_text(self):
        spec = CandidateSpec(name="name", corroborate=("title",))
        left = person("zendesk", "u_1", 1, name="Carlos Ch", title="CEO")
        right = person("intercom", "con_1", 2, name="C Chinchilla", title=" ceo ")
        assert candidates.agreements(left, right, spec) == [("title", "CEO", " ceo ")]
        other = person("intercom", "con_2", 3, name="C Chinchilla", title="CTO")
        assert candidates.agreements(left, other, spec) == []

    def test_the_attrs_a_declaration_reads_include_the_base_of_a_virtual_one(self):
        assert candidates.attrs_read(PERSON) == ("name", "phone", "email")


class TestTheCap:
    def test_a_record_with_seven_lookalikes_keeps_five(self):
        hub = person("hubspot", "0", 1, name="Carlos Chinchilla", phone=PHONE)
        others = [
            person("hubspot", str(n), n + 1, name="Carlos Chinchilla", phone=PHONE)
            for n in range(1, 8)
        ]
        found = nominate([hub, *others])
        per_record = Counter(a for c in found for a in (c.left, c.right))
        assert per_record[hub.anchor_key] == 5
        assert max(per_record.values()) <= 5


def _singletons(*specs):
    clusters = [
        resolver.Cluster(
            canonical_id=resolver.canonical_id_for(anchor),
            entity_type="person",
            anchor_key=anchor,
            minted_order=order,
            members={tuple(anchor.split("|", 2)): "singleton"},
            sources={anchor.split("|")[0]},
        )
        for anchor, order in specs
    ]
    return {
        "clusters": clusters,
        "aliases": {},
        "of_record": {k: c.canonical_id for c in clusters for k in c.members},
    }


class TestHumanUnion:
    LATER = "zendesk|person|u_1"
    EARLIER = "intercom|person|con_1"

    def test_the_earlier_record_anchors_the_union(self):
        resolution = _singletons((self.LATER, 5), (self.EARLIER, 2))
        result = resolver.union(resolution, [(7, self.EARLIER, self.LATER)])
        [cluster] = result["clusters"]
        assert cluster.anchor_key == self.EARLIER
        assert cluster.members == {
            tuple(self.EARLIER.split("|")): "singleton",
            tuple(self.LATER.split("|")): "human=7",
        }
        assert cluster.sources == {"intercom", "zendesk"}
        assert result["aliases"] == {
            resolver.canonical_id_for(self.LATER): cluster.canonical_id
        }
        assert set(result["of_record"].values()) == {cluster.canonical_id}

    def test_a_pair_already_in_one_cluster_is_left_alone(self):
        resolution = _singletons((self.EARLIER, 1))
        cluster = resolution["clusters"][0]
        cluster.members[tuple(self.LATER.split("|"))] = "email=c@acme.io"
        resolution["of_record"][tuple(self.LATER.split("|"))] = cluster.canonical_id
        before = dict(cluster.members)
        result = resolver.union(resolution, [(7, self.EARLIER, self.LATER)])
        assert result["clusters"][0].members == before
        assert result["aliases"] == {}

    def test_a_pair_naming_a_missing_record_is_skipped(self):
        resolution = _singletons((self.EARLIER, 1))
        result = resolver.union(resolution, [(7, self.EARLIER, self.LATER)])
        assert len(result["clusters"]) == 1
        assert result["aliases"] == {}

    def test_an_alias_pointing_at_the_loser_follows_it(self):
        third = "hubspot|person|p_9"
        resolution = _singletons((self.LATER, 5), (self.EARLIER, 2), (third, 9))
        old = resolver.canonical_id_for("stripe|person|gone")
        other = resolver.canonical_id_for("stripe|person|elsewhere")
        resolution["aliases"] = {
            old: resolver.canonical_id_for(self.LATER),
            other: resolver.canonical_id_for(third),
        }
        result = resolver.union(resolution, [(7, self.EARLIER, self.LATER)])
        survivor = resolver.canonical_id_for(self.EARLIER)
        assert result["aliases"] == {
            old: survivor,
            other: resolver.canonical_id_for(third),
            resolver.canonical_id_for(self.LATER): survivor,
        }


async def contact(session, source_id, **fields):
    await store.save_raw(
        session,
        source="intercom",
        object_type="contacts",
        source_id=source_id,
        raw_payload={"id": source_id, **fields},
    )


async def user(session, source_id, **fields):
    await store.save_raw(
        session,
        source="zendesk",
        object_type="users",
        source_id=source_id,
        raw_payload={"id": source_id, **fields},
    )


async def queue(session):
    await contact(session, "con_1", name="C Chinchilla", phone=PHONE)
    await user(session, "u_1", name="Carlos Ch", phone=PHONE)
    await session.commit()
    return await run.rebuild(session)


async def rows(session, status=None):
    query = (
        select(MergeCandidate)
        .order_by(MergeCandidate.seq)
        .execution_options(populate_existing=True)
    )
    if status:
        query = query.where(MergeCandidate.status == status)
    return (await session.execute(query)).scalars().all()


async def evidence(session, seq):
    return (
        await session.execute(
            select(
                MergeCandidateEvidence.attr,
                MergeCandidateEvidence.left_value,
                MergeCandidateEvidence.right_value,
            )
            .where(MergeCandidateEvidence.candidate_seq == seq)
            .order_by(MergeCandidateEvidence.seq)
        )
    ).all()


async def membership(session, anchor):
    source, entity_type, source_id = anchor.split("|", 2)
    return (
        await session.execute(
            select(CanonicalMember.canonical_id, CanonicalMember.evidence)
            .join(Entity, Entity.id == CanonicalMember.entity_id)
            .where(
                Entity.source == source,
                Entity.entity_type == entity_type,
                Entity.source_id == source_id,
            )
        )
    ).one_or_none()


async def decide(session, row, status):
    row.status = status
    row.decided_at = datetime(2026, 9, 4, tzinfo=UTC)
    await session.commit()


LEFT = "intercom|person|con_1"
RIGHT = "zendesk|person|u_1"


class TestARebuildQueuesThePair:
    async def test_the_pair_lands_pending_with_its_evidence(self, session):
        await queue(session)
        [row] = await rows(session)
        assert (row.entity_type, row.left_anchor, row.right_anchor) == (
            "person",
            LEFT,
            RIGHT,
        )
        assert (row.score, row.status, row.evidence_holds, row.decided_at) == (
            0.8,
            "pending",
            True,
            None,
        )
        assert await evidence(session, row.seq) == [
            ("name", "C Chinchilla", "Carlos Ch"),
            ("phone", PHONE, PHONE),
        ]

    async def test_a_second_rebuild_replaces_the_row_rather_than_adding_one(
        self, session
    ):
        await queue(session)
        await run.rebuild(session)
        assert len(await rows(session)) == 1
        assert len(await rows(session, "pending")) == 1

    async def test_a_pair_tied_by_an_identifier_is_not_queued(self, session):
        await contact(session, "con_1", name="C Chinchilla", email="c@acme.io")
        await user(session, "u_1", name="Carlos Ch", email="c@acme.io")
        await session.commit()
        await run.rebuild(session)
        assert await rows(session) == []

    async def test_the_report_counts_the_nominations(self, session):
        result = await queue(session)
        assert result["candidates"] == 1
        assert result["report"]["totals"]["candidates"] == 1

    async def test_the_records_stay_apart_until_someone_decides(self, session):
        await queue(session)
        left, right = await membership(session, LEFT), await membership(session, RIGHT)
        assert left.canonical_id != right.canonical_id


class TestADecisionOutlivesTheRebuild:
    async def test_a_confirmed_pair_merges_with_human_evidence(self, session):
        await queue(session)
        [row] = await rows(session)
        await decide(session, row, "confirmed")
        await run.rebuild(session)
        left, right = await membership(session, LEFT), await membership(session, RIGHT)
        assert left.canonical_id == right.canonical_id
        assert left.evidence == "singleton"
        assert right.evidence == f"human={row.seq}"
        [kept] = await rows(session)
        assert (kept.seq, kept.status, kept.evidence_holds) == (
            row.seq,
            "confirmed",
            True,
        )
        assert await rows(session, "pending") == []

    async def test_a_rejected_pair_is_remembered_and_not_requeued(self, session):
        await queue(session)
        [row] = await rows(session)
        await decide(session, row, "rejected")
        await run.rebuild(session)
        [kept] = await rows(session)
        assert (kept.seq, kept.status) == (row.seq, "rejected")
        left, right = await membership(session, LEFT), await membership(session, RIGHT)
        assert left.canonical_id != right.canonical_id

    async def test_evidence_holds_flips_when_the_phone_changes(self, session):
        await queue(session)
        [row] = await rows(session)
        await decide(session, row, "confirmed")
        await run.rebuild(session)
        await contact(session, "con_1", name="C Chinchilla", phone="+14155550199")
        await session.commit()
        await run.rebuild(session)
        [kept] = await rows(session)
        assert (kept.status, kept.evidence_holds) == ("confirmed", False)
        left, right = await membership(session, LEFT), await membership(session, RIGHT)
        assert left.canonical_id == right.canonical_id

    async def test_evidence_holds_is_false_when_a_record_vanishes(self, session):
        await queue(session)
        [row] = await rows(session)
        await decide(session, row, "confirmed")
        await contact(session, "con_1")
        await session.commit()
        await run.rebuild(session)
        [kept] = await rows(session)
        assert (kept.status, kept.evidence_holds) == ("confirmed", False)
        assert await membership(session, LEFT) is None
        assert (await membership(session, RIGHT)).evidence == "singleton"


class TestOneNominationPerClusterPair:
    def test_a_lookalike_of_a_whole_cluster_is_queued_once(self):
        found = nominate(
            [
                person("salesforce", "sf_1", 1, name="Rich Hendricks", phone=PHONE),
                person(
                    "hubspot",
                    "hs_1",
                    2,
                    name="Richard Hendricks",
                    email="richard@piedpiper.com",
                    phone=PHONE,
                ),
                person(
                    "activecampaign",
                    "ac_1",
                    3,
                    name="Richard Hendricks",
                    email="richard@piedpiper.com",
                    phone=PHONE,
                ),
            ]
        )
        assert [(c.left, c.right) for c in found] == [
            ("activecampaign|person|ac_1", "salesforce|person|sf_1")
        ]

    def test_the_best_scoring_record_pair_speaks_for_the_clusters(self):
        found = nominate(
            [
                person("salesforce", "sf_1", 1, name="Rich Hendricks", phone=PHONE),
                person(
                    "activecampaign",
                    "ac_1",
                    2,
                    name="R Hendricks",
                    email="richard@piedpiper.com",
                    phone=PHONE,
                ),
                person(
                    "hubspot",
                    "hs_1",
                    3,
                    name="Richard Hendricks",
                    email="richard@piedpiper.com",
                    phone=PHONE,
                ),
            ]
        )
        assert [(c.left, c.right, c.score > 0.8) for c in found] == [
            ("hubspot|person|hs_1", "salesforce|person|sf_1", True)
        ]
