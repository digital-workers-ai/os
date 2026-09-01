"""Adversarial ER world: an extension of `world.py` built to FAIL precision.

`world.py` cannot fail a precision test. Its 10 companies have 10 distinct
names and 10 distinct domains; its 22 people have 22 distinct mailboxes and
one repeated surname. Any rule set scores precision 1.000 on it by
construction, so every precision number measured there proves nothing.

This module keeps that world (it is the easy, clean core that carries recall)
and layers on the collision structures that occur constantly in real business
data and that make a *false merge* — the expensive error — possible:

  G1  shared domain, NOT the same company .... holding + subsidiaries on one domain
  G2  near-miss legal names ................... "Acme Corp" vs "Acme Corp Ltd"
  G3  agency domain ........................... one agency's domain on its clients
  G4  same name, different company ............ "Summit Partners" VC vs roofing
  G5  shared address .......................... registered agent + coworking space
  G6  shared phone ............................ company main line, call-centre DID
  G7  recycled identifier ..................... vendor id reused after churn
  P1  common surnames at volume ............... 20 Smiths, 15 Zhangs, 12 Patels
  P2  shared mailboxes ........................ family mail, assistant, AP desk
  P3  shared phone on people .................. 30 staff on one main line
  P4  chain bait .............................. A-B on phone, B-C on mail, A?C

Ground truth is exact and declared, never inferred: every source record carries
the canonical id of the real-world thing it describes, and every deliberate
collision is registered in `COLLISIONS` with the reason it is NOT a match.

Nothing here is random at read time — `_RNG` is seeded once, so the corpus is
byte-identical on every import.
"""

import random
from dataclasses import dataclass, field

from seeds.world import COMPANIES, PEOPLE

SOURCES = ("hubspot", "salesforce", "stripe", "zendesk", "intercom", "netsuite")

# --- shared identifiers that are NOT identifiers -----------------------------

ACME_MAIN_LINE = "+14155550100"      # one PBX, three legal entities, 30 staff
CALL_CENTRE_DID = "+18005550199"     # outsourced support line, 60+ records
AGENCY_LINE = "+13125550400"         # Brightwave's line, on its clients' records
REG_AGENT_ADDR = "251 Little Falls Drive, Wilmington, DE 19808"
COWORK_ADDR = "One Broadway, Cambridge, MA 02142"
WEWORK_ADDR = "115 Broadway, New York, NY 10006"


@dataclass
class AdvCompany:
    id: str                       # canonical ground-truth id
    name: str                     # canonical legal name
    domain: str | None = None
    phone: str | None = None
    address: str | None = None
    vendor_id: str | None = None
    country: str = "US"
    industry: str | None = None
    group: str = "clean"          # collision family
    note: str = ""
    crm_domain: str | None = None  # what the CRM sources hold instead (agency)
    crm_sources: tuple = ("hubspot", "salesforce", "stripe")


@dataclass
class AdvPerson:
    id: str
    first_name: str
    last_name: str
    email: str | None = None
    phone: str | None = None
    company: str | None = None    # AdvCompany.id
    title: str | None = None
    alt_email: str | None = None  # personal address a minority of sources hold
    nickname: str | None = None   # first name as some sources render it
    group: str = "clean"
    note: str = ""


@dataclass
class AdvRecord:
    """One source system's view of one real-world thing."""
    source: str
    type: str                     # 'company' | 'person'
    ext_id: str
    truth: str                    # AdvCompany.id / AdvPerson.id
    name: str
    facts: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.source}:{self.ext_id}"


@dataclass
class Collision:
    """A deliberate NON-match: two real things that share an identifier."""
    group: str
    attr: str                     # the attribute they collide on
    value: str
    members: tuple                # canonical ids that share it
    reason: str                   # why they are nevertheless different things


COMPANY_LIST: list[AdvCompany] = []
PERSON_LIST: list[AdvPerson] = []
COLLISIONS: list[Collision] = []


def _co(*a, **kw):
    c = AdvCompany(*a, **kw)
    COMPANY_LIST.append(c)
    return c


def _pe(*a, **kw):
    p = AdvPerson(*a, **kw)
    PERSON_LIST.append(p)
    return p


def _clash(group, attr, value, members, reason):
    COLLISIONS.append(Collision(group, attr, value, tuple(members), reason))


# =============================================================================
# The clean core: world.py, carried over verbatim. This is what makes recall
# measurable — 10 companies and 22 people that genuinely do resolve.
# =============================================================================

for _c in COMPANIES:
    # No `address`: world.py records a city, not a street address, and a city
    # is a category. Emitting it as `address` would manufacture collisions the
    # corpus never intended (Hooli and Pied Piper are both "Palo Alto, CA").
    _co(f"w_{_c.id}", _c.name, _c.domain,
        phone=None, address=None,
        vendor_id=None, country=_c.country, industry=_c.industry,
        group="seed", note="world.py canonical company")

for _p in PEOPLE:
    _pe(f"w_{_p.id}", _p.first_name, _p.last_name, _p.email, _p.phone,
        company=f"w_{_p.company_id}", title=_p.role,
        group="seed", note="world.py canonical person")

# world.py's own declared ER variations, kept so this corpus is a superset.
NICKNAMES = {"w_p21": "Robert", "w_p15": "Rich"}
ALT_EMAILS = {"w_p15": "r.hendricks@gmail.com"}
for _p in PERSON_LIST:
    if _p.id in NICKNAMES:
        _p.nickname = NICKNAMES[_p.id]
    if _p.id in ALT_EMAILS:
        _p.alt_email = ALT_EMAILS[_p.id]


# =============================================================================
# G1 — shared domain, NOT the same company. Holding structure.
# =============================================================================

# The operating company is world.py's own Acme Corp (w_c1) — reusing it rather
# than minting a second "Acme Corp" keeps one real thing on one canonical id.
# It gains the switchboard and the street address the holding structure needs.
ACME_OPCO = "w_c1"
COMPANIES_BY_ID_SEED = {c.id: c for c in COMPANY_LIST}
COMPANIES_BY_ID_SEED[ACME_OPCO].phone = ACME_MAIN_LINE
COMPANIES_BY_ID_SEED[ACME_OPCO].address = "500 Howard St, San Francisco, CA 94105"
COMPANIES_BY_ID_SEED[ACME_OPCO].vendor_id = "V-20001"
COMPANIES_BY_ID_SEED[ACME_OPCO].group = "G1_holding"
COMPANIES_BY_ID_SEED[ACME_OPCO].note = (
    "world.py's Acme Corp, now the operating company of a holding structure")

_co("g1_acme_labs", "Acme Labs", "acme.io", ACME_MAIN_LINE,
    "500 Howard St, San Francisco, CA 94105", "V-20002", industry="Research",
    group="G1_holding", note="R&D subsidiary; own P&L, own contract, own vendor id")
_co("g1_acme_hold", "Acme Holdings LLC", "acme.io", ACME_MAIN_LINE,
    REG_AGENT_ADDR, "V-20003", industry="Holding",
    group="G1_holding", note="parent holdco; never transacts, must not absorb the opcos")

_clash("G1_holding", "domain", "acme.io",
       [ACME_OPCO, "g1_acme_labs", "g1_acme_hold"],
       "one registered domain serves a holdco and two subsidiaries with "
       "separate contracts, separate invoices and separate revenue")
_clash("G1_holding", "phone", ACME_MAIN_LINE,
       [ACME_OPCO, "g1_acme_labs", "g1_acme_hold"],
       "one PBX in one building; the switchboard is not an identity")
_clash("G1_holding", "address", "500 Howard St, San Francisco, CA 94105",
       [ACME_OPCO, "g1_acme_labs"],
       "co-located subsidiaries")

# A second, smaller holding family so G1 is not a single anecdote.
_co("g1_orbit_media", "Orbit Media Group", "orbitmedia.co", "+12065550300",
    "1201 3rd Ave, Seattle, WA 98101", "V-20010", industry="Media",
    group="G1_holding", note="parent")
_co("g1_orbit_print", "Orbit Print Services", "orbitmedia.co", "+12065550300",
    "1201 3rd Ave, Seattle, WA 98101", "V-20011", industry="Printing",
    group="G1_holding", note="subsidiary on the parent's domain")
_clash("G1_holding", "domain", "orbitmedia.co",
       ["g1_orbit_media", "g1_orbit_print"],
       "subsidiary was never given its own domain")
_clash("G1_holding", "phone", "+12065550300",
       ["g1_orbit_media", "g1_orbit_print"], "one switchboard, two entities")
_clash("G1_holding", "address", "1201 3rd Ave, Seattle, WA 98101",
       ["g1_orbit_media", "g1_orbit_print"], "co-located parent and subsidiary")


# =============================================================================
# G2 — near-miss legal names that normalize to the SAME key.
# `normalize_name` strips corp/ltd/llc/inc/plc, so these collapse together.
# =============================================================================

_co("g2_acme_uk", "Acme Corp Ltd", "acme.co.uk", "+442075550100",
    "30 St Mary Axe, London EC3A 8BF", "V-20004", country="GB",
    industry="Software", group="G2_nearmiss",
    note="UK entity, separate incorporation, separate VAT — not Acme Corp (US)")
_co("g2_vertex_inc", "Vertex Group Inc", "vertexgroup.com", "+16125550110",
    "80 S 8th St, Minneapolis, MN 55402", "V-20005", industry="Consulting",
    group="G2_nearmiss", note="unrelated to Vertex Group LLC; different owners")
_co("g2_vertex_llc", "Vertex Group LLC", "vertex-group.net", "+19195550111",
    "150 Fayetteville St, Raleigh, NC 27601", "V-20006", industry="Logistics",
    group="G2_nearmiss", note="unrelated to Vertex Group Inc")
_co("g2_northwind_co", "Northwind Trading Co", "northwind-trading.com",
    "+16045550112", "1055 W Georgia St, Vancouver BC", "V-20007",
    country="CA", industry="Import/Export", group="G2_nearmiss",
    note="Canadian trader")
_co("g2_northwind_company", "Northwind Trading Company", "northwindtrading.sg",
    "+6565550113", "1 Raffles Place, Singapore 048616", "V-20008",
    country="SG", industry="Import/Export", group="G2_nearmiss",
    note="Singapore reseller, no ownership link to the Canadian trader")
_co("g2_riverstone_corp", "Riverstone Capital Corp", "riverstonecap.com",
    "+12125550114", "9 W 57th St, New York, NY 10019", "V-20009",
    industry="Finance", group="G2_nearmiss", note="US fund")
_co("g2_riverstone_plc", "Riverstone Capital PLC", "riverstonecapital.co.uk",
    "+442075550115", "1 Poultry, London EC2R 8EJ", "V-20012", country="GB",
    industry="Finance", group="G2_nearmiss", note="unrelated UK fund, same brand word")

_clash("G2_nearmiss", "name", "acme", [ACME_OPCO, "g2_acme_uk"],
       "'Acme Corp' and 'Acme Corp Ltd' both normalize to 'acme'; they are "
       "separately incorporated in different countries")
_clash("G2_nearmiss", "name", "vertex group", ["g2_vertex_inc", "g2_vertex_llc"],
       "Inc and LLC are stripped by name normalization; unrelated businesses")
_clash("G2_nearmiss", "name", "northwind trading",
       ["g2_northwind_co", "g2_northwind_company"],
       "'Co' and 'Company' are both stripped as legal suffixes")
_clash("G2_nearmiss", "name", "riverstone capital",
       ["g2_riverstone_corp", "g2_riverstone_plc"],
       "'Corp' and 'PLC' are both stripped; unrelated funds")


# =============================================================================
# G3 — an agency's domain and phone on every client it onboarded.
# =============================================================================

_co("g3_brightwave", "Brightwave Agency", "brightwave.agency", AGENCY_LINE,
    "203 N LaSalle St, Chicago, IL 60601", "V-20020", industry="Marketing",
    group="G3_agency", note="the agency itself")
_AGENCY_CLIENTS = [
    ("g3_nordic", "Nordic Foods AB", "nordicfoods.se", "SE", "Food"),
    ("g3_larkspur", "Larkspur Dental", "larkspurdental.com", "US", "Healthcare"),
    ("g3_vela", "Vela Motors", "velamotors.com", "US", "Automotive"),
    ("g3_quarry", "Quarry Coffee Roasters", "quarrycoffee.com", "US", "Food"),
    ("g3_tidepool", "Tidepool Swimwear", "tidepool.store", "US", "Retail"),
]
for _id, _name, _dom, _cc, _ind in _AGENCY_CLIENTS:
    _co(_id, _name, _dom, AGENCY_LINE, "203 N LaSalle St, Chicago, IL 60601",
        None, country=_cc, industry=_ind, group="G3_agency",
        note="onboarded by Brightwave; CRM sources carry the AGENCY domain/phone",
        crm_domain="brightwave.agency")

_clash("G3_agency", "domain", "brightwave.agency",
       ["g3_brightwave"] + [c[0] for c in _AGENCY_CLIENTS],
       "the agency's own domain was entered as the contact domain on every "
       "client record it created; six different businesses")
_clash("G3_agency", "phone", AGENCY_LINE,
       ["g3_brightwave"] + [c[0] for c in _AGENCY_CLIENTS],
       "the agency's switchboard is the listed number on all its clients")
_clash("G3_agency", "address", "203 N LaSalle St, Chicago, IL 60601",
       ["g3_brightwave"] + [c[0] for c in _AGENCY_CLIENTS],
       "the agency's office is the mailing address on its clients' records")


# =============================================================================
# G4 — same company name, genuinely different companies.
# =============================================================================

_SAME_NAME = [
    ("g4_summit_vc", "Summit Partners", "summit-partners.com", "+16175550200",
     "222 Berkeley St, Boston, MA 02116", "Venture Capital"),
    ("g4_summit_roof", "Summit Partners", "summitroofing.net", "+19185550201",
     "4100 S Peoria Ave, Tulsa, OK 74105", "Construction"),
    ("g4_apex_tx", "Apex Solutions", "apexsolutions-tx.com", "+15125550202",
     "600 Congress Ave, Austin, TX 78701", "IT Services"),
    ("g4_apex_ny", "Apex Solutions", "apexsolutionsny.com", "+15855550203",
     "100 State St, Rochester, NY 14614", "Staffing"),
    ("g4_apex_uk", "Apex Solutions Ltd", "apex-solutions.co.uk", "+441135550204",
     "1 City Square, Leeds LS1 2AL", "Facilities"),
    ("g4_pioneer_co", "Pioneer Systems", "pioneersystems.io", "+13035550205",
     "1600 Broadway, Denver, CO 80202", "Software"),
    ("g4_pioneer_fl", "Pioneer Systems", "pioneer-sys.com", "+18135550206",
     "100 N Tampa St, Tampa, FL 33602", "HVAC"),
    ("g4_meridian_a", "Meridian Health", "meridianhealth.org", "+17325550207",
     "1350 Campus Pkwy, Neptune, NJ 07753", "Healthcare"),
    ("g4_meridian_b", "Meridian Health Inc", "meridian-health.co", "+16025550208",
     "2 N Central Ave, Phoenix, AZ 85004", "Insurance"),
]
for _id, _name, _dom, _ph, _addr, _ind in _SAME_NAME:
    _co(_id, _name, _dom, _ph, _addr, None, industry=_ind, group="G4_samename",
        note="shares a normalized name with an unrelated company")

_clash("G4_samename", "name", "summit partners", ["g4_summit_vc", "g4_summit_roof"],
       "a Boston VC firm and a Tulsa roofing contractor")
_clash("G4_samename", "name", "apex solutions",
       ["g4_apex_tx", "g4_apex_ny", "g4_apex_uk"],
       "three unrelated businesses in TX, NY and the UK")
_clash("G4_samename", "name", "pioneer systems", ["g4_pioneer_co", "g4_pioneer_fl"],
       "a Denver software vendor and a Tampa HVAC installer")
_clash("G4_samename", "name", "meridian health", ["g4_meridian_a", "g4_meridian_b"],
       "a New Jersey hospital network and an Arizona insurer")


# =============================================================================
# G5 — shared address: registered agent, coworking, virtual office.
# =============================================================================

_REG_AGENT = [
    ("g5_ra_alder", "Alder Point Ventures", "alderpoint.vc", "Finance"),
    ("g5_ra_basalt", "Basalt Mining Corp", "basaltmining.com", "Mining"),
    ("g5_ra_cedar", "Cedar Grove Media", "cedargrove.tv", "Media"),
    ("g5_ra_dunes", "Dunes Logistics", "duneslogistics.com", "Logistics"),
    ("g5_ra_ember", "Ember Analytics", "emberanalytics.io", "Software"),
    ("g5_ra_flint", "Flint & Roe LLP", "flintroe.law", "Legal"),
    ("g5_ra_gale", "Gale Wind Energy", "galewind.energy", "Energy"),
    ("g5_ra_harbor", "Harbor Point Capital", "harborpointcap.com", "Finance"),
]
for _i, (_id, _name, _dom, _ind) in enumerate(_REG_AGENT):
    _co(_id, _name, _dom, f"+1302555{4000 + _i:04d}", REG_AGENT_ADDR,
        None, industry=_ind, group="G5_address",
        note="Delaware registered-agent address")
_clash("G5_address", "address", REG_AGENT_ADDR,
       [c[0] for c in _REG_AGENT] + ["g1_acme_hold"],
       "CSC's Wilmington office is the registered address of ~300k companies, "
       "including the Acme holdco")

_COWORK = [
    ("g5_cw_iris", "Iris Robotics", "irisrobotics.ai", "Robotics"),
    ("g5_cw_juniper", "Juniper Bio", "juniperbio.com", "Biotech"),
    ("g5_cw_kelp", "Kelp Forest Labs", "kelpforest.io", "Software"),
    ("g5_cw_lantern", "Lantern Learning", "lanternlearning.com", "EdTech"),
    ("g5_cw_moss", "Moss & Co Design", "mossco.design", "Design"),
    ("g5_cw_nimbus", "Nimbus Weather", "nimbusweather.app", "Software"),
]
for _i, (_id, _name, _dom, _ind) in enumerate(_COWORK):
    _co(_id, _name, _dom, f"+1617555{4100 + _i:04d}", COWORK_ADDR,
        None, industry=_ind, group="G5_address",
        note="coworking space in Kendall Square")
_clash("G5_address", "address", COWORK_ADDR, [c[0] for c in _COWORK],
       "six startups renting desks in the same building")

_VIRTUAL = [
    ("g5_vo_opal", "Opal Trading", "opaltrading.com", "Finance"),
    ("g5_vo_pyrite", "Pyrite Games", "pyritegames.com", "Gaming"),
    ("g5_vo_quartz", "Quartz Legal", "quartzlegal.com", "Legal"),
    ("g5_vo_ridge", "Ridge Outfitters", "ridgeoutfitters.co", "Retail"),
]
for _i, (_id, _name, _dom, _ind) in enumerate(_VIRTUAL):
    _co(_id, _name, _dom, f"+1212555{4200 + _i:04d}", WEWORK_ADDR,
        None, industry=_ind, group="G5_address", note="virtual office")
_clash("G5_address", "address", WEWORK_ADDR, [c[0] for c in _VIRTUAL],
       "virtual-office mail drop")


# =============================================================================
# G6 — the outsourced call centre: one DID on many companies (above the cap).
# =============================================================================

_CALL_CENTRE = [
    ("g6_cc_%02d" % i, name, dom, ind) for i, (name, dom, ind) in enumerate([
        ("Silverbrook Foods", "silverbrook.com", "Food"),
        ("Tallow Candle Co", "tallowcandle.com", "Retail"),
        ("Umber Interiors", "umberinteriors.com", "Design"),
        ("Verdigris Paint", "verdigrispaint.com", "Manufacturing"),
        ("Wicker Home", "wickerhome.com", "Retail"),
        ("Xanthe Textiles", "xanthetextiles.com", "Textiles"),
        ("Yarrow Farms", "yarrowfarms.ag", "Agriculture"),
        ("Zinc Fabrication", "zincfab.com", "Manufacturing"),
        ("Anvil Tools", "anviltools.com", "Manufacturing"),
        ("Birch Bookbinding", "birchbind.com", "Printing"),
        ("Clove Spice Imports", "clovespice.com", "Food"),
        ("Dowel Furniture", "dowelfurniture.com", "Retail"),
    ])
]
for _i, (_id, _name, _dom, _ind) in enumerate(_CALL_CENTRE):
    _co(_id, _name, _dom, CALL_CENTRE_DID,
        f"{100 + _i} Market St, Louisville, KY 40202", None,
        industry=_ind, group="G6_phone",
        note="all support routed through one outsourced call centre DID")
_clash("G6_phone", "phone", CALL_CENTRE_DID, [c[0] for c in _CALL_CENTRE],
       "an outsourced support vendor's single inbound number")


# =============================================================================
# G7 — recycled vendor identifiers.
# =============================================================================

_co("g7_cyan", "Cyan Freight", "cyanfreight.com", "+17135550700",
    "2200 Post Oak Blvd, Houston, TX 77056", "V-10428", industry="Logistics",
    group="G7_recycled", note="churned 2024-11; vendor id released back to the pool")
_co("g7_petal", "Petal Studio", "petalstudio.co", "+15035550701",
    "1000 SW Broadway, Portland, OR 97205", "V-10428", industry="Design",
    group="G7_recycled", note="onboarded 2025-03; reassigned the freed vendor id")
_co("g7_juno", "Juno Instruments", "junoinstruments.com", "+16175550702",
    "10 Milk St, Boston, MA 02108", "V-10731", industry="Hardware",
    group="G7_recycled", note="churned 2025-01")
_co("g7_kestrel", "Kestrel Aviation", "kestrelaviation.com", "+13055550703",
    "1 Biscayne Blvd, Miami, FL 33132", "V-10731", industry="Aviation",
    group="G7_recycled", note="reassigned the freed vendor id")

_clash("G7_recycled", "vendor_id", "V-10428", ["g7_cyan", "g7_petal"],
       "the ERP reissues vendor numbers after a customer churns")
_clash("G7_recycled", "vendor_id", "V-10731", ["g7_juno", "g7_kestrel"],
       "same recycling policy, second occurrence")


# =============================================================================
# G8 — ordinary companies. No collisions. These carry company recall.
# =============================================================================

_CLEAN = [
    ("Aurora Freight", "aurorafreight.com", "Logistics"),
    ("Belltower Books", "belltowerbooks.com", "Retail"),
    ("Cinder Brewing", "cinderbrewing.com", "Food"),
    ("Delta Marsh Realty", "deltamarsh.realty", "Real Estate"),
    ("Everglade Solar", "everglade.solar", "Energy"),
    ("Fernway Pharma", "fernwaypharma.com", "Pharma"),
    ("Granite Peak Gear", "granitepeakgear.com", "Retail"),
    ("Hollow Tree Cider", "hollowtreecider.com", "Food"),
    ("Ironvale Steel", "ironvale.com", "Manufacturing"),
    ("Jetstream Air Cargo", "jetstreamcargo.com", "Logistics"),
    ("Kingfisher Optics", "kingfisheroptics.com", "Hardware"),
    ("Lumen Dental Group", "lumendental.com", "Healthcare"),
    ("Marrow Bone Broth", "marrowbroth.com", "Food"),
    ("Nettle Gardens", "nettlegardens.com", "Agriculture"),
    ("Obsidian Security", "obsidiansec.io", "Software"),
    ("Palisade Wines", "palisadewines.com", "Food"),
    ("Quill Publishing", "quillpublishing.com", "Media"),
    ("Rookery Films", "rookeryfilms.com", "Media"),
    ("Sable Chemicals", "sablechem.com", "Chemicals"),
    ("Thistle Knitwear", "thistleknitwear.com", "Textiles"),
    ("Undertow Surf", "undertowsurf.com", "Retail"),
    ("Vellum Paper Co", "vellumpaper.com", "Manufacturing"),
    ("Willow Creek Vets", "willowcreekvets.com", "Healthcare"),
    ("Yardarm Marine", "yardarmmarine.com", "Marine"),
    ("Zephyr Cycles", "zephyrcycles.com", "Retail"),
]
for _i, (_name, _dom, _ind) in enumerate(_CLEAN):
    _co(f"g8_clean_{_i:02d}", _name, _dom, f"+1415555{5000 + _i:04d}",
        f"{200 + _i} Main St, Springfield, IL 62701", f"V-30{_i:03d}",
        industry=_ind, group="G8_clean", note="ordinary company, no collisions")


COMPANIES_BY_ID = {c.id: c for c in COMPANY_LIST}


# =============================================================================
# PEOPLE
# =============================================================================

_ANY_CO = [c.id for c in COMPANY_LIST if c.group in ("G8_clean", "G5_address")]

# --- P1: common surnames at volume -------------------------------------------
# 20 Smiths, 15 Zhangs, 12 Patels. Nearly all distinct people. A handful share
# a full normalized name with someone else, which is the point.

_SMITH_FIRST = ["John", "Sarah", "Michael", "Emily", "David", "Jessica",
                "Daniel", "Ashley", "James", "Amanda", "Robert", "Laura",
                "Thomas", "Rachel", "William", "Megan", "Joseph", "Nicole",
                "John", "Sarah"]           # two deliberate full-name repeats
_ZHANG_FIRST = ["Wei", "Li", "Yan", "Ming", "Jing", "Hui", "Feng", "Xin",
                "Lei", "Na", "Bo", "Qi", "Wei", "Li", "Hao"]   # two repeats
_PATEL_FIRST = ["Anil", "Meera", "Raj", "Priya", "Kunal", "Nisha", "Amit",
                "Divya", "Sanjay", "Kavita", "Anil", "Rohit"]  # one repeat

_RNG = random.Random(20260727)


def _surname_block(surname, firsts, tag, domains):
    """N people with one surname, each at a different company."""
    out = []
    for i, first in enumerate(firsts):
        dom = domains[i % len(domains)]
        # Distinct mailbox per person: two John Smiths at different companies
        # do not share an inbox. The collision is on NAME, not on email.
        local = f"{first.lower()}.{surname.lower()}{i}"
        pid = f"p1_{tag}_{i:02d}"
        out.append(_pe(pid, first, surname,
                       email=f"{local}@{dom}",
                       phone=f"+1{_RNG.randint(2000000000, 9899999999)}",
                       company=_RNG.choice(_ANY_CO),
                       title=_RNG.choice(["Analyst", "Manager", "Director",
                                          "Engineer", "Coordinator", "VP"]),
                       group="P1_surname",
                       note=f"one of {len(firsts)} {surname}s; distinct person"))
    return out


_SMITHS = _surname_block("Smith", _SMITH_FIRST, "smith",
                         [c.domain for c in COMPANY_LIST[-25:] if c.domain])
_ZHANGS = _surname_block("Zhang", _ZHANG_FIRST, "zhang",
                         [c.domain for c in COMPANY_LIST[-25:] if c.domain])
_PATELS = _surname_block("Patel", _PATEL_FIRST, "patel",
                         [c.domain for c in COMPANY_LIST[-25:] if c.domain])

for _block, _firsts, _label in ((_SMITHS, _SMITH_FIRST, "Smith"),
                                (_ZHANGS, _ZHANG_FIRST, "Zhang"),
                                (_PATELS, _PATEL_FIRST, "Patel")):
    _seen: dict = {}
    for _p in _block:
        _seen.setdefault(_p.first_name, []).append(_p.id)
    for _first, _ids in _seen.items():
        if len(_ids) > 1:
            _clash("P1_surname", "name", f"{_first} {_label}".lower(), _ids,
                   f"two different people both called {_first} {_label}, at "
                   f"different companies")
    _clash("P1_surname", "last_name", _label.lower(), [p.id for p in _block],
           f"{len(_block)} unrelated people share the surname {_label}")


# --- P2: shared mailboxes ----------------------------------------------------

_pe("p2_anil_patel_h", "Anil", "Patel", "thepatels@gmail.com", "+16505551001",
    company="g8_clean_00", title="Owner", group="P2_mailbox",
    note="shares a household mailbox with his spouse")
_pe("p2_meera_patel_h", "Meera", "Patel", "thepatels@gmail.com", "+16505551002",
    company="g8_clean_01", title="Owner", group="P2_mailbox",
    note="spouse; separate customer, same household mailbox")
_clash("P2_mailbox", "email", "thepatels@gmail.com",
       ["p2_anil_patel_h", "p2_meera_patel_h"],
       "a shared household mailbox held by two separate customers")

_pe("p2_greg_smith_f", "Greg", "Smith", "smithfamily@gmail.com", "+13125551003",
    company="g8_clean_02", title="Member", group="P2_mailbox", note="family mailbox")
_pe("p2_dana_smith_f", "Dana", "Smith", "smithfamily@gmail.com", "+13125551004",
    company="g8_clean_03", title="Member", group="P2_mailbox", note="family mailbox")
_clash("P2_mailbox", "email", "smithfamily@gmail.com",
       ["p2_greg_smith_f", "p2_dana_smith_f"], "shared family mailbox")

_pe("p2_bruce_exec", "Bruce", "Calloway", "ea.office@harborpointcap.com",
    "+12125551005", company="g5_ra_harbor", title="Managing Partner",
    group="P2_mailbox", note="his assistant's mailbox is on his CRM record")
_pe("p2_lucius_exec", "Lucius", "Ferrand", "ea.office@harborpointcap.com",
    "+12125551006", company="g5_ra_harbor", title="CIO",
    group="P2_mailbox", note="same assistant, same mailbox on his record")
_clash("P2_mailbox", "email", "ea.office@harborpointcap.com",
       ["p2_bruce_exec", "p2_lucius_exec"],
       "one executive assistant's mailbox listed on two executives' records")

_pe("p2_ap_clerk_a", "Ingrid", "Halvorsen", "ap@nordicfoods.se", "+46855551007",
    company="g3_nordic", title="AP Clerk", group="P2_mailbox",
    note="accounts-payable role mailbox, two clerks behind it")
_pe("p2_ap_clerk_b", "Sofia", "Lindqvist", "ap@nordicfoods.se", "+46855551008",
    company="g3_nordic", title="AP Clerk", group="P2_mailbox",
    note="second clerk on the same role mailbox")
_clash("P2_mailbox", "email", "ap@nordicfoods.se",
       ["p2_ap_clerk_a", "p2_ap_clerk_b"],
       "a role mailbox staffed by two named people")

# Role mailboxes on the SHARED acme.io domain: two separate helpdesks, and the
# CRM records for them are separate contact records at separate legal entities.
_pe("p2_acme_corp_support", "Acme Corp", "Support Desk", "support@acme.io",
    ACME_MAIN_LINE, company=ACME_OPCO, title="Support",
    group="P2_mailbox", note="Acme Corp's support contact record")
_pe("p2_acme_labs_support", "Acme Labs", "Helpdesk", "support@acme.io",
    ACME_MAIN_LINE, company="g1_acme_labs", title="Support",
    group="P2_mailbox", note="Acme Labs' support contact record, same mailbox")
_clash("P2_mailbox", "email", "support@acme.io",
       ["p2_acme_corp_support", "p2_acme_labs_support"],
       "a role mailbox shared by two legal entities on one domain")

# info@/billing@ at ordinary companies — same string shape, different domains,
# so they must NOT collide. Present to prove the email rule is not the problem.
for _i, _cid in enumerate(["g8_clean_04", "g8_clean_05", "g8_clean_06",
                           "g8_clean_07", "g8_clean_08", "g8_clean_09",
                           "g8_clean_10", "g8_clean_11"]):
    _dom = COMPANIES_BY_ID[_cid].domain
    for _role in ("info", "billing"):
        _pe(f"p2_{_role}_{_i:02d}", _role.capitalize(), "Desk",
            f"{_role}@{_dom}", COMPANIES_BY_ID[_cid].phone, company=_cid,
            title="Role mailbox", group="P2_role",
            note="role mailbox scoped to its own domain — a true singleton")


# --- P3: the company main line on 30 staff records ---------------------------
_MAIN_LINE_STAFF = [
    ("Priya", "Raman", "priya.raman", ACME_OPCO),
    ("Ken", "Whitlock", "ken.whitlock", "g1_acme_labs"),
    ("Marta", "Oliveira", "marta.oliveira", "g1_acme_hold"),
    ("Tobias", "Fenn", "tobias.fenn", ACME_OPCO),
    ("Yuki", "Nakamura", "yuki.nakamura", "g1_acme_labs"),
    ("Grace", "Odeyemi", "grace.odeyemi", ACME_OPCO),
    ("Hector", "Salaz", "hector.salaz", "g1_acme_labs"),
    ("Ines", "Moreau", "ines.moreau", "g1_acme_hold"),
    ("Jonas", "Berg", "jonas.berg", ACME_OPCO),
    ("Keisha", "Boyd", "keisha.boyd", "g1_acme_labs"),
    ("Liam", "O'Shea", "liam.oshea", ACME_OPCO),
    ("Mina", "Kovac", "mina.kovac", "g1_acme_labs"),
    ("Noor", "Haddad", "noor.haddad", ACME_OPCO),
    ("Owen", "Tran", "owen.tran", "g1_acme_labs"),
    ("Paulina", "Wisniewski", "paulina.wisniewski", "g1_acme_hold"),
    ("Quentin", "Roy", "quentin.roy", ACME_OPCO),
    ("Rosa", "Iglesias", "rosa.iglesias", "g1_acme_labs"),
    ("Samir", "Chowdhury", "samir.chowdhury", ACME_OPCO),
    ("Tara", "Nilsson", "tara.nilsson", "g1_acme_labs"),
    ("Umar", "Farouk", "umar.farouk", ACME_OPCO),
    ("Vera", "Lindgren", "vera.lindgren", "g1_acme_labs"),
    ("Wesley", "Adeyemi", "wesley.adeyemi", ACME_OPCO),
    ("Xiu", "Lam", "xiu.lam", "g1_acme_labs"),
    ("Yara", "Sabbagh", "yara.sabbagh", ACME_OPCO),
    ("Zane", "Kovacs", "zane.kovacs", "g1_acme_labs"),
    ("Ada", "Kimura", "ada.kimura", "g1_acme_hold"),
    ("Bruno", "Costa", "bruno.costa", ACME_OPCO),
    ("Cleo", "Marchetti", "cleo.marchetti", "g1_acme_labs"),
    ("Dmitri", "Sokolov", "dmitri.sokolov", ACME_OPCO),
    ("Elsa", "Bjornsson", "elsa.bjornsson", "g1_acme_labs"),
]
for _i, (_f, _l, _local, _cid) in enumerate(_MAIN_LINE_STAFF):
    _pe(f"p3_main_{_i:02d}", _f, _l, f"{_local}@acme.io", ACME_MAIN_LINE,
        company=_cid, title="Staff", group="P3_phone",
        note="reachable on the company main line; the switchboard is not their identity")
_clash("P3_phone", "phone", ACME_MAIN_LINE,
       [f"p3_main_{i:02d}" for i in range(len(_MAIN_LINE_STAFF))]
       + ["p2_acme_corp_support", "p2_acme_labs_support"],
       "32 distinct employees answer on one switchboard number — deliberately "
       "sized just under ER_BUCKET_CAP=50 so the cap does not rescue the rule")

# 60 records on one call-centre DID: ABOVE the cap, so the cap should fire.
_CC_AGENTS = [(f"Agent{chr(65 + i // 26)}{chr(65 + i % 26)}", f"Handler{i:02d}")
              for i in range(60)]
for _i, (_f, _l) in enumerate(_CC_AGENTS):
    _pe(f"p3_cc_{_i:02d}", _f, _l, f"agent{_i:02d}@callhub.support", CALL_CENTRE_DID,
        company=_CALL_CENTRE[_i % len(_CALL_CENTRE)][0], title="Support Agent",
        group="P3_phone_capped",
        note="outsourced agent; 60 of them share one inbound DID")
_clash("P3_phone_capped", "phone", CALL_CENTRE_DID,
       [f"p3_cc_{i:02d}" for i in range(60)],
       "60 agents on one DID — above ER_BUCKET_CAP=50, so the cap should "
       "suppress this bucket entirely")


# --- P4: the hand-built chain (A-B on phone, B-C on mail, A?C on nothing) ----
_pe("p4_chain_a", "Dana", "Reid", "dana.reid@orbitmedia.co", "+12065550300",
    company="g1_orbit_media", title="Producer", group="P4_chain",
    note="A: shares the Orbit main line with B, shares nothing with C")
_pe("p4_chain_b", "Errol", "Vance", "orbit.desk@orbitmedia.co", "+12065550300",
    company="g1_orbit_media", title="Coordinator", group="P4_chain",
    note="B: shares the phone with A AND the shared desk mailbox with C")
_pe("p4_chain_c", "Fay", "Osei", "orbit.desk@orbitmedia.co", "+12065559999",
    company="g1_orbit_print", title="Press Operator", group="P4_chain",
    note="C: shares only the desk mailbox with B; nothing at all with A")
_clash("P4_chain", "phone", "+12065550300", ["p4_chain_a", "p4_chain_b"],
       "main line")
_clash("P4_chain", "email", "orbit.desk@orbitmedia.co",
       ["p4_chain_b", "p4_chain_c"], "shared desk mailbox")
_clash("P4_chain", "transitive", "-", ["p4_chain_a", "p4_chain_c"],
       "A and C share NO identifier at all; only naive transitive closure "
       "over A-B and B-C can merge them")


# --- P5: ordinary people who genuinely do resolve across sources -------------
_CLEAN_PEOPLE = [
    ("Alice", "Nguyen", "Ali"), ("Benjamin", "Okafor", "Ben"),
    ("Carmen", "Delgado", None), ("Dmitry", "Ivanov", "Dima"),
    ("Elena", "Rossi", None), ("Felix", "Baumann", None),
    ("Gabriela", "Souza", "Gabi"), ("Hiroshi", "Sato", None),
    ("Isabelle", "Laurent", "Izzy"), ("Jamal", "Rashid", None),
    ("Katherine", "O'Brien", "Kate"), ("Lars", "Eriksen", None),
    ("Maya", "Goldstein", None), ("Nikolai", "Petrov", "Nik"),
    ("Olivia", "Fitzgerald", "Liv"), ("Pablo", "Herrera", None),
    ("Quinn", "Sullivan", None), ("Rania", "Aziz", None),
    ("Stefan", "Novak", "Steve"), ("Tanvi", "Iyer", None),
    ("Ulrich", "Weber", "Uli"), ("Valentina", "Castro", "Val"),
    ("Wesley", "Thornton", "Wes"), ("Ximena", "Vargas", None),
    ("Yosef", "Ben-Ami", "Yossi"), ("Zoe", "Kalogeropoulos", None),
    ("Aaron", "Whitfield", None), ("Beatrix", "Hoffman", "Trixie"),
    ("Cyrus", "Mehta", None), ("Delphine", "Moreau", None),
    ("Ezra", "Lindholm", None), ("Farida", "Sow", None),
    ("Gideon", "Marsh", None), ("Halina", "Nowak", None),
    ("Ivan", "Horvat", None), ("Josephine", "Adeyemi", "Josie"),
    ("Kwame", "Boateng", None), ("Lucia", "Ferrari", None),
    ("Mateo", "Silva", None), ("Nadia", "Petrova", None),
]
for _i, (_f, _l, _nick) in enumerate(_CLEAN_PEOPLE):
    _cid = _ANY_CO[_i % len(_ANY_CO)]
    _dom = COMPANIES_BY_ID[_cid].domain
    _pe(f"p5_clean_{_i:02d}", _f, _l,
        f"{_f.lower()}.{_l.lower().replace(chr(39), '')}@{_dom}",
        f"+1206555{6000 + _i:04d}", company=_cid,
        title=_RNG.choice(["CEO", "CFO", "Head of Ops", "Engineer",
                           "Designer", "Sales Lead", "Analyst"]),
        alt_email=(f"{_f.lower()}{_i}@gmail.com" if _i % 4 == 0 else None),
        nickname=_nick, group="P5_clean",
        note="ordinary person; resolves cleanly across sources")

PEOPLE_BY_ID = {p.id: p for p in PERSON_LIST}


# --- registry sweep ----------------------------------------------------------
# Every entity above was declared distinct BY HAND. This sweep does not decide
# anything; it walks the finished list and registers the identifiers those
# hand-declared-distinct people happen to share, so that `experiments/advprec/
# audit.py` can assert that no collision in the rendered corpus is an accident.
# Collisions already registered above are not duplicated.

def _register_incidental(attr, getter, reason):
    """Register, or WIDEN, the collision entry for each shared value.

    Widening matters: a hand-written entry that named two of the three people
    on a value would otherwise leave the third looking undeclared, and the
    audit would report a corpus bug that is really a stale hand-written list.
    """
    existing = {(c.attr, str(c.value).lower()): c for c in COLLISIONS}
    groups: dict = {}
    for p in PERSON_LIST:
        for v in getter(p):
            if v:
                groups.setdefault(str(v).lower(), []).append(p.id)
    for value, ids in sorted(groups.items()):
        ids = sorted(set(ids))
        if len(ids) < 2:
            continue
        prior = existing.get((attr, value))
        if prior is None:
            _clash("R_sweep", attr, value, ids, reason)
        else:
            prior.members = tuple(sorted(set(prior.members) | set(ids)))


_register_incidental(
    "name",
    lambda p: [f"{p.first_name} {p.last_name}"]
    + ([f"{p.nickname} {p.last_name}"] if p.nickname else []),
    "two hand-declared-distinct people whose rendered names normalize identically")
_register_incidental(
    "email", lambda p: [p.email, p.alt_email],
    "two hand-declared-distinct people on one mailbox")
_register_incidental(
    "phone", lambda p: [p.phone],
    "two hand-declared-distinct people on one telephone number")


# =============================================================================
# Rendering: how each source sees each thing.
# =============================================================================

_SUFFIX_SWAP = {"Corp": "Corporation", "Inc": "Incorporated", "LLC": "L.L.C.",
                "Ltd": "Limited", "Co": "Company", "PLC": "plc"}


def _render_company_name(name: str, style: int) -> str:
    """A source-specific rendering of the SAME company name."""
    if style == 0:
        return name
    if style == 1:
        return name.upper()
    if style == 2:
        for short, long in _SUFFIX_SWAP.items():
            if name.endswith(" " + short):
                return name[: -len(short)] + long
        return name + ", Inc."
    if style == 3:
        for short in _SUFFIX_SWAP:
            if name.endswith(" " + short):
                return name[: -(len(short) + 1)]
        return name
    if style == 4:
        return name.lower()
    return name + "."


def _render_domain(domain: str | None, style: int) -> str | None:
    if not domain:
        return None
    return {0: domain, 1: f"www.{domain}", 2: f"https://{domain}/",
            3: domain.upper(), 4: f"http://www.{domain}/contact",
            5: domain}[style % 6]


# Numbers that arrived by bulk import or PBX provisioning and are therefore
# stored byte-identically everywhere. Keeping these unvaried matters: format
# drift would split one 60-record bucket into three 20-record buckets and
# quietly hide the very bucket ER_BUCKET_CAP exists to catch.
_UNVARIED_PHONES = {ACME_MAIN_LINE, CALL_CENTRE_DID, AGENCY_LINE, "+12065550300"}


def _render_phone(phone: str | None, style: int) -> str | None:
    """Most CRMs store E.164; a minority keep the typed-in format."""
    if not phone or not phone.startswith("+1") or len(phone) != 12:
        return phone
    if phone in _UNVARIED_PHONES:
        return phone
    if style % 5 == 3:
        return f"({phone[2:5]}) {phone[5:8]}-{phone[8:]}"
    if style % 5 == 4:
        return f"{phone[2:5]}-{phone[5:8]}-{phone[8:]}"
    return phone


def _render_email(email: str | None, style: int) -> str | None:
    if not email:
        return None
    local, _, dom = email.partition("@")
    return {0: email, 1: email.upper(), 2: f"{local}+crm@{dom}",
            3: email, 4: f"{local}+{style}@{dom}", 5: email}[style % 6]


def _sources_for(idx: int, n_min: int = 2, n_max: int = 4,
                 require: tuple = ()) -> list[str]:
    """Deterministic 2-4 source subset; always includes at least two.

    `require` forces a source into the subset — used for the agency clients,
    whose whole point is that a CRM source holds the agency's domain. Leaving
    that to chance would silently drop the collision from the corpus.
    """
    rng = random.Random(1000 + idx)
    n = rng.randint(n_min, n_max)
    picked = set(rng.sample(SOURCES, n))
    for r in require:
        picked.add(r)
    return sorted(picked, key=SOURCES.index)


def build_company_records() -> list[AdvRecord]:
    out = []
    for idx, c in enumerate(COMPANY_LIST):
        require = ("hubspot",) if c.crm_domain else ()
        for si, source in enumerate(_sources_for(idx, require=require)):
            style = (idx + si) % 6
            facts = {"name": _render_company_name(c.name, style)}
            raw_domain = (c.crm_domain if (c.crm_domain and source in c.crm_sources)
                          else c.domain)
            dom = _render_domain(raw_domain, style)
            if dom:
                facts["domain"] = dom
            ph = _render_phone(c.phone, style + si)
            if ph:
                facts["phone"] = ph
            if c.address:
                facts["address"] = c.address
            if c.vendor_id and source in ("netsuite", "stripe"):
                facts["vendor_id"] = c.vendor_id
            if c.industry:
                facts["industry"] = c.industry
            facts["country"] = c.country
            out.append(AdvRecord(source, "company",
                                 f"{source}_co_{c.id}", c.id,
                                 facts["name"], facts))
    return out


def build_person_records() -> list[AdvRecord]:
    out = []
    for idx, p in enumerate(PERSON_LIST):
        # Capped-bucket agents only need to exist once each; rendering them in
        # four sources would quadruple the corpus for no extra signal.
        n_max = 2 if p.group == "P3_phone_capped" else 4
        for si, source in enumerate(_sources_for(10_000 + idx, 2, n_max)):
            style = (idx + si) % 6
            first = p.nickname if (p.nickname and si == 1) else p.first_name
            full = f"{first} {p.last_name}".strip()
            facts = {"name": full, "first_name": first, "last_name": p.last_name}
            # A minority of sources hold only the personal address: the email
            # rule cannot reach these, which is a recall cost, not a bug.
            email = (p.alt_email if (p.alt_email and si == 2) else p.email)
            em = _render_email(email, style)
            if em:
                facts["email"] = em
            ph = _render_phone(p.phone, style + si)
            if ph:
                facts["phone"] = ph
            if p.company and p.company in COMPANIES_BY_ID:
                co = COMPANIES_BY_ID[p.company]
                facts["company_name"] = co.name
                if co.domain:
                    facts["company_domain"] = co.domain
            if p.title:
                facts["title"] = p.title
            out.append(AdvRecord(source, "person",
                                 f"{source}_pe_{p.id}", p.id, full, facts))
    return out


def build_records() -> list[AdvRecord]:
    recs = build_company_records() + build_person_records()
    return sorted(recs, key=lambda r: (r.type, r.truth, r.source, r.ext_id))


def summary() -> dict:
    recs = build_records()
    co = [r for r in recs if r.type == "company"]
    pe = [r for r in recs if r.type == "person"]
    groups: dict = {}
    for c in COMPANY_LIST:
        groups.setdefault("company/" + c.group, 0)
        groups["company/" + c.group] += 1
    for p in PERSON_LIST:
        groups.setdefault("person/" + p.group, 0)
        groups["person/" + p.group] += 1
    return {
        "sources": list(SOURCES),
        "companies": len(COMPANY_LIST), "company_records": len(co),
        "people": len(PERSON_LIST), "person_records": len(pe),
        "collisions": len(COLLISIONS),
        "groups": dict(sorted(groups.items())),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(summary(), indent=2))
