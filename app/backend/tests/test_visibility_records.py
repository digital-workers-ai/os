from app.sources.visibility import check_records, distinct

TODAY = "2026-09-04"
QUERY = "best crm for small business"
SLUG = "best-crm-for-small-business"
PAYLOAD = {"request": {"query": QUERY}, "response": {"id": "gen-1"}}


def _mention(engine, domain, name, role, rank):
    return {
        "_source_id": f"{engine}|{SLUG}|{TODAY}|{domain}",
        "_mention_engine": engine,
        "_mention_query": QUERY,
        "_mention_checked_at": TODAY,
        "_company": name,
        "_role": role,
        "_rank": rank,
    }


class TestTheCheckRecord:
    def test_the_check_carries_the_payload_and_its_identity(self):
        check = check_records("chatgpt", QUERY, TODAY, PAYLOAD, text="Nothing.")[0]
        assert check["request"] == PAYLOAD["request"]
        assert check["response"] == PAYLOAD["response"]
        assert check["_source_id"] == f"chatgpt|{SLUG}|{TODAY}"
        assert check["_engine"] == "chatgpt"
        assert check["_query"] == QUERY
        assert check["_checked_at"] == TODAY

    def test_the_answer_is_the_text_and_the_sources_count_the_links(self):
        links = ["https://www.g2.com/crm", "https://www.capterra.com/crm"]
        check = check_records("chatgpt", QUERY, TODAY, {}, text="Nothing.", links=links)[0]
        assert check["_answer"] == "Nothing."
        assert check["_sources"] == 2

    def test_no_text_means_no_answer_key(self):
        check = check_records("google", QUERY, TODAY, {}, links=["https://g2.com"])[0]
        assert "_answer" not in check
        assert check["_sources"] == 1

    def test_an_empty_text_is_still_an_answer(self):
        check = check_records("chatgpt", QUERY, TODAY, {}, text="")[0]
        assert check["_answer"] == ""
        assert check["_sources"] == 0

    def test_results_count_as_sources_and_rank_by_position(self):
        results = [
            {"position": 1, "link": "https://www.zoho.com/crm/"},
            {"position": 2, "link": "https://www.g2.com/categories/crm"},
            {"position": 3, "link": "https://www.pipedrive.com/en/features"},
        ]
        check, *found = check_records("google", QUERY, TODAY, {}, results=results)
        assert check["_sources"] == 3
        assert check["_brand_rank"] == 3
        assert "_answer" not in check
        assert found == [
            _mention("google", "zoho.com", "Zoho CRM", "competitor", 1),
            _mention("google", "pipedrive.com", "Pipedrive", "brand", 3),
        ]

    def test_results_win_over_links_when_both_are_given(self):
        results = [{"position": 4, "link": "https://www.hubspot.com/"}]
        links = ["https://www.pipedrive.com/", "https://www.zoho.com/"]
        check, *found = check_records(
            "google", QUERY, TODAY, {}, links=links, results=results
        )
        assert check["_sources"] == 1
        assert [m["_company"] for m in found] == ["HubSpot"]

    def test_the_brand_rank_follows_the_brand_mention(self):
        text = "HubSpot and Pipedrive lead the shortlist."
        check = check_records("chatgpt", QUERY, TODAY, {}, text=text)[0]
        assert check["_brand_rank"] == 2

    def test_the_brand_rank_is_absent_when_the_brand_is_not_found(self):
        text = "HubSpot leads."
        links = ["https://www.hubspot.com/products/crm"]
        check, *found = check_records("chatgpt", QUERY, TODAY, {}, text=text, links=links)
        assert "_brand_rank" not in check
        assert [m["_role"] for m in found] == ["competitor"]

    def test_the_stored_payload_is_not_mutated(self):
        payload = {"request": {"query": QUERY}}
        check_records("chatgpt", QUERY, TODAY, payload, text="Pipedrive.")
        assert payload == {"request": {"query": QUERY}}


class TestTheMentionRecords:
    def test_named_companies_rank_before_cited_ones(self):
        text = "Zoho CRM is the cheap one, Pipedrive the visual one."
        links = [
            "https://www.g2.com/categories/crm",
            "https://www.freshworks.com/crm/sales/",
            "https://www.hubspot.com/",
        ]
        _check, *found = check_records(
            "perplexity", QUERY, TODAY, PAYLOAD, text=text, links=links
        )
        assert found == [
            _mention("perplexity", "zoho.com", "Zoho CRM", "competitor", 1),
            _mention("perplexity", "pipedrive.com", "Pipedrive", "brand", 2),
            _mention("perplexity", "freshworks.com", "Freshsales", "competitor", 3),
            _mention("perplexity", "hubspot.com", "HubSpot", "competitor", 4),
        ]

    def test_mentions_do_not_carry_the_payload(self):
        _check, first = check_records(
            "gemini", QUERY, TODAY, PAYLOAD, text="Pipedrive."
        )
        assert "request" not in first
        assert "response" not in first

    def test_links_may_arrive_as_any_iterable(self):
        links = (link for link in ["https://www.zoho.com/", "https://www.zoho.com/"])
        check, *found = check_records("claude", QUERY, TODAY, {}, text="", links=links)
        assert check["_sources"] == 2
        assert [m["_company"] for m in found] == ["Zoho CRM"]

    def test_no_text_and_no_links_is_a_bare_check(self):
        assert check_records("chatgpt", "", "", {}) == [
            {
                "_source_id": "chatgpt||",
                "_engine": "chatgpt",
                "_query": "",
                "_checked_at": "",
                "_sources": 0,
            }
        ]


class TestDistinct:
    def test_order_is_kept_and_repeats_drop(self):
        assert distinct(["b", "a", "b", "c", "a"]) == ["b", "a", "c"]

    def test_empties_and_non_strings_drop(self):
        assert distinct(["", "  ", None, 5, "x", ["y"]]) == ["x"]

    def test_nothing_in_gives_nothing_out(self):
        assert distinct([]) == []
        assert distinct(link for link in ()) == []
