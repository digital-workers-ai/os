# ActiveCampaign API

## Overview

ActiveCampaign API v3 provides access to contacts, automations, deals (CRM), campaigns, lists, tags, and custom fields for email marketing and sales automation.

## Base URL

```
https://{account}.api-us1.com/api/3/
```

`{account}` is your ActiveCampaign account name (subdomain). E.g., account `acme` → `https://acme.api-us1.com/api/3/`. Note: `api-us1.com` is not guaranteed for all accounts; the actual base URL is found in your account under Settings > Developer tab.

## Authentication

API key via custom header.

```
Api-Token: {api_key}
Content-Type: application/json
```

Returns 403 without a valid key:
```json
{
  "message": "Forbidden"
}
```

The header name is the whole of it. Sending the same key as
`Authorization: Bearer {api_key}` answers 403 as well — the key is not the
problem, the scheme is.

## Rate Limits

- **5 requests/second** per account (uniform across all endpoints)
- HTTP 429 when exceeded
- `Retry-After` header indicates wait time in seconds
- Additional headers: `RateLimit-Limit` (max requests), `RateLimit-Remaining` (requests left in window)

---

## Endpoints

### GET /api/3/contacts

Returns all contacts.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 20 | Results per page (max 100) |
| `offset` | int | 0 | Starting position |
| `search` | string | — | Search by email or name |
| `email` | string | — | Filter by exact email |
| `listid` | int | — | Filter by list membership |
| `tagid` | int | — | Filter by tag |
| `status` | int | — | -1=any, 0=unconfirmed, 1=active, 2=unsubscribed, 3=bounced |
| `orders[email]` | string | — | Sort by email `ASC` or `DESC` |
| `orders[cdate]` | string | — | Sort by creation date |
| `orders[name]` | string | — | Sort by name |

**Example Request:**
```bash
curl -H "Api-Token: ac_mock_apikey_001" \
  "https://acme.api-us1.com/api/3/contacts?limit=1&offset=0"
```

**Example Response:**
```json
{
  "scoreValues": [],
  "contacts": [
    {
      "id": "1",
      "email": "jane@acme.io",
      "email_local": "jane",
      "email_domain": "acme.io",
      "firstName": "Jane",
      "lastName": "Smith",
      "phone": "+12125550100",
      "orgid": "1",
      "orgname": "Acme Corp",
      "organization": null,
      "segmentio_id": "",
      "hash": "9d5ed678fe57bcca610140957afab571",
      "ip": "0",
      "ua": null,
      "gravatar": "0",
      "deleted": "0",
      "anonymized": "0",
      "mpp_tracking": "0",
      "sentcnt": "0",
      "bounced_hard": "0",
      "bounced_soft": "0",
      "bounced_date": null,
      "adate": null,
      "edate": null,
      "cdate": "2025-03-20T14:30:00-05:00",
      "udate": "2026-07-10T09:00:00-05:00",
      "deleted_at": null,
      "created_by": null,
      "updated_by": null,
      "created_timestamp": "2025-03-20 14:30:00",
      "created_utc_timestamp": "2025-03-20 19:30:00",
      "updated_timestamp": "2026-07-10 09:00:00",
      "updated_utc_timestamp": "2026-07-10 14:00:00",
      "rating_tstamp": null,
      "socialdata_lastcheck": null,
      "best_send_hour": null,
      "last_click_date": null,
      "last_open_date": null,
      "last_mpp_open_date": null,
      "sms_consent": null,
      "sms_consent_updated_at": null,
      "whatsapp_id": null,
      "whatsapp_username": null,
      "accountContacts": [],
      "scoreValues": [],
      "links": {
        "accountContacts": "https://acme.api-us1.com/api/3/contacts/1/accountContacts",
        "automationEntryCounts": "https://acme.api-us1.com/api/3/contacts/1/automationEntryCounts",
        "bounceLogs": "https://acme.api-us1.com/api/3/contacts/1/bounceLogs",
        "contactAutomations": "https://acme.api-us1.com/api/3/contacts/1/contactAutomations",
        "contactData": "https://acme.api-us1.com/api/3/contacts/1/contactData",
        "contactDeals": "https://acme.api-us1.com/api/3/contacts/1/contactDeals",
        "contactGoals": "https://acme.api-us1.com/api/3/contacts/1/contactGoals",
        "contactLists": "https://acme.api-us1.com/api/3/contacts/1/contactLists",
        "contactLogs": "https://acme.api-us1.com/api/3/contacts/1/contactLogs",
        "contactTags": "https://acme.api-us1.com/api/3/contacts/1/contactTags",
        "deals": "https://acme.api-us1.com/api/3/contacts/1/deals",
        "fieldValues": "https://acme.api-us1.com/api/3/contacts/1/fieldValues",
        "geoIps": "https://acme.api-us1.com/api/3/contacts/1/geoIps",
        "notes": "https://acme.api-us1.com/api/3/contacts/1/notes",
        "organization": "https://acme.api-us1.com/api/3/contacts/1/organization",
        "plusAppend": "https://acme.api-us1.com/api/3/contacts/1/plusAppend",
        "scoreValues": "https://acme.api-us1.com/api/3/contacts/1/scoreValues",
        "trackingLogs": "https://acme.api-us1.com/api/3/contacts/1/trackingLogs"
      }
    }
  ],
  "meta": {
    "total": "2450",
    "sortable": true,
    "page_input": {
      "segmentid": null,
      "formid": 0,
      "listid": 0,
      "tagid": 0,
      "limit": 20,
      "offset": 0,
      "search": null,
      "sort": null,
      "seriesid": 0,
      "waitid": 0,
      "status": -1,
      "forceQuery": 0,
      "cacheid": "26f0b45d57322d46adb71f3c2bc3cd72"
    }
  }
}
```

The response carries three top-level keys, not two: `contacts`, `meta`, and
`scoreValues`. `scoreValues` is a sibling of `contacts`, and each contact
carries its own `scoreValues` list as well. A reader that expects exactly two
keys, or that reads the list by position, will break here.

Every unset date comes back as `null`, never as an empty string: `adate`,
`edate`, `bounced_date`, `rating_tstamp`, `socialdata_lastcheck`, `deleted_at`,
`best_send_hour`, `last_click_date`, `last_open_date`, `last_mpp_open_date`,
`sms_consent_updated_at`. Unset *strings* do come back as `""` — `firstName`,
`lastName`, `phone`, `orgname`, `email_local`, `segmentio_id` were all empty on
the account this was captured from.

`meta.total` is a string nested under `meta`, so an offset walk cannot read it
as a top-level count; it ends on a page shorter than the requested `limit`.

---

### GET /api/3/automations

Returns all automations.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 20 | Results per page (max 100) |
| `offset` | int | 0 | Starting position |
| `orders[name]` | string | — | Sort `ASC` or `DESC` |

**Example Request:**
```bash
curl -H "Api-Token: ac_mock_apikey_001" \
  "https://acme.api-us1.com/api/3/automations?limit=2"
```

**Example Response:**
```json
{
  "automations": [
    {
      "name": "Welcome Series",
      "cdate": "2025-04-01T10:00:00-05:00",
      "mdate": "2026-07-10T09:00:00-05:00",
      "userid": "1",
      "status": "1",
      "entered": "3250",
      "exited": "2890",
      "hidden": "0",
      "defaultscreenshot": "https://acme.api-us1.com/images/automation_screenshot.png",
      "screenshot": "https://acme.api-us1.com/images/automation_screenshot.png",
      "links": {
        "campaigns": "https://acme.api-us1.com/api/3/automations/1/campaigns",
        "contactGoals": "https://acme.api-us1.com/api/3/automations/1/contactGoals",
        "contactAutomations": "https://acme.api-us1.com/api/3/automations/1/contactAutomations"
      },
      "id": "1"
    },
    {
      "name": "Re-engagement Campaign",
      "cdate": "2025-08-15T14:00:00-05:00",
      "mdate": "2026-06-20T16:00:00-05:00",
      "userid": "1",
      "status": "1",
      "entered": "1520",
      "exited": "1480",
      "hidden": "0",
      "defaultscreenshot": "https://acme.api-us1.com/images/automation_screenshot2.png",
      "screenshot": "https://acme.api-us1.com/images/automation_screenshot2.png",
      "links": {
        "campaigns": "https://acme.api-us1.com/api/3/automations/2/campaigns",
        "contactGoals": "https://acme.api-us1.com/api/3/automations/2/contactGoals",
        "contactAutomations": "https://acme.api-us1.com/api/3/automations/2/contactAutomations"
      },
      "id": "2"
    }
  ],
  "meta": {
    "total": "8"
  }
}
```

---

### GET /api/3/deals

Returns all deals (CRM pipeline).

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 20 | Results per page (max 100) |
| `offset` | int | 0 | Starting position |
| `filters[search]` | string | — | Search by title |
| `filters[stage]` | int | — | Filter by stage ID |
| `filters[status]` | int | — | 0=open, 1=won, 2=lost |
| `orders[value]` | string | — | Sort by value `ASC` or `DESC` |

**Example Request:**
```bash
curl -H "Api-Token: ac_mock_apikey_001" \
  "https://acme.api-us1.com/api/3/deals?limit=2&filters[status]=0"
```

**Example Response:**
```json
{
  "deals": [
    {
      "hash": "deal_hash_001",
      "owner": "1",
      "contact": "1",
      "organization": "ac_org_acme_001",
      "group": "1",
      "stage": "3",
      "title": "Acme Corp Enterprise Upgrade",
      "description": "Upgrading from Growth to Enterprise plan",
      "percent": "60",
      "cdate": "2026-06-01T10:00:00-05:00",
      "mdate": "2026-07-12T14:00:00-05:00",
      "nextdate": "2026-07-20T10:00:00-05:00",
      "nexttaskid": "5",
      "value": "5760000",
      "currency": "usd",
      "winProbability": 60,
      "winProbabilityMdate": "2026-07-12T14:00:00-05:00",
      "status": "0",
      "activitycount": "12",
      "nextdealid": "0",
      "edate": null,
      "links": {
        "dealActivities": "https://acme.api-us1.com/api/3/deals/1/dealActivities",
        "contact": "https://acme.api-us1.com/api/3/deals/1/contact",
        "contactDeals": "https://acme.api-us1.com/api/3/deals/1/contactDeals",
        "group": "https://acme.api-us1.com/api/3/deals/1/group",
        "nextTask": "https://acme.api-us1.com/api/3/deals/1/nextTask",
        "notes": "https://acme.api-us1.com/api/3/deals/1/notes",
        "organization": "https://acme.api-us1.com/api/3/deals/1/organization",
        "owner": "https://acme.api-us1.com/api/3/deals/1/owner",
        "scoreValues": "https://acme.api-us1.com/api/3/deals/1/scoreValues",
        "stage": "https://acme.api-us1.com/api/3/deals/1/stage",
        "dealCustomFieldData": "https://acme.api-us1.com/api/3/deals/1/dealCustomFieldData"
      },
      "id": "1",
      "isDisabled": false
    }
  ],
  "meta": {
    "total": "15",
    "currencies": [
      {"currency": "usd", "total": "28800000"}
    ]
  }
}
```

---

### GET /api/3/campaigns

Returns all email campaigns.

**Example Request:**
```bash
curl -H "Api-Token: ac_mock_apikey_001" \
  "https://acme.api-us1.com/api/3/campaigns?limit=1"
```

**Example Response:**
```json
{
  "campaigns": [
    {
      "type": "single",
      "userid": "1",
      "segmentid": "0",
      "bounceid": "-1",
      "realcid": "0",
      "sendid": "0",
      "threadid": "0",
      "seriesid": "0",
      "formid": "0",
      "basetemplateid": "0",
      "basemessageid": "0",
      "addressid": "1",
      "source": "web",
      "name": "July Product Update",
      "cdate": "2026-07-05T10:00:00-05:00",
      "mdate": "2026-07-10T14:05:00-05:00",
      "sdate": "2026-07-10T14:00:00-05:00",
      "ldate": "2026-07-14T22:15:00-05:00",
      "send_amt": "1250",
      "total_amt": "1250",
      "opens": "456",
      "uniqueopens": "380",
      "linkclicks": "142",
      "uniquelinkclicks": "118",
      "subscriberclicks": "118",
      "forwards": "5",
      "uniqueforwards": "4",
      "hardbounces": "3",
      "softbounces": "12",
      "unsubscribes": "8",
      "unsubreasons": [],
      "updates": "0",
      "socialshares": "0",
      "replies": "2",
      "uniquereplies": "2",
      "status": "5",
      "public": "1",
      "mail_transfer": "1",
      "mail_send": "1",
      "mail_cleanup": "1",
      "mailer_log_file": "",
      "tracklinks": "all",
      "tracklinksaliases": "all",
      "trackreads": "1",
      "trackreadsaliases": "1",
      "analytics_campaign_name": "july-product-update",
      "tweet": "0",
      "facebook": "0",
      "survey": "",
      "embed_images": "0",
      "htmlunsub": "0",
      "textunsub": "0",
      "htmlunsubdata": null,
      "textunsubdata": null,
      "recurring": "day1",
      "willrecur": "0",
      "split_id": "0",
      "split_type": "",
      "split_content": "0",
      "split_winner_awaiting": "0",
      "split_winner_messageid": "0",
      "links": {
        "automation": "https://acme.api-us1.com/api/3/campaigns/1/automation",
        "campaignMessage": "https://acme.api-us1.com/api/3/campaigns/1/campaignMessage",
        "campaignMessages": "https://acme.api-us1.com/api/3/campaigns/1/campaignMessages",
        "links": "https://acme.api-us1.com/api/3/campaigns/1/links"
      },
      "id": "1"
    }
  ],
  "meta": {
    "total": "45"
  }
}
```

The example above is a campaign that has been sent. A campaign awaiting send
answers `"sdate": null` and `"ldate": null` — not an empty string. `cdate` and
`mdate` are always present, so `mdate` is the field to observe a campaign by.

---

## Pagination

Offset-based using `offset` and `limit` parameters.

```
GET /api/3/contacts?limit=20&offset=0     → items 0-19
GET /api/3/contacts?limit=20&offset=20    → items 20-39
GET /api/3/contacts?limit=20&offset=40    → items 40-59
```

- `limit`: items per page (default 20, max 100)
- `offset`: zero-based starting index
- `meta.total` in response gives the total count
- Done when `offset + limit >= meta.total`

## Error Responses

```json
{
  "message": "No Result found for Subscriber with id 99999"
}
```

Or for validation errors:
```json
{
  "errors": [
    {
      "title": "The contact email already exists in the system",
      "detail": "",
      "code": "duplicate",
      "source": {
        "pointer": "/data/attributes/email"
      }
    }
  ]
}
```

| HTTP Status | Meaning |
|-------------|---------|
| 400 | Bad request / validation error |
| 403 | Forbidden — invalid API key |
| 404 | Resource not found |
| 422 | Unprocessable entity — validation failed |
| 429 | Rate limit exceeded |
| 500 | Server error |

## Notes

- IDs are **string numbers** (e.g., `"id": "1"`), not UUIDs
- `status` on automations: `"0"` = inactive, `"1"` = active
- `status` on campaigns: `"0"` = draft, `"1"` = scheduled, `"2"` = sending, `"3"` = paused, `"4"` = stopped, `"5"` = completed
- `status` on deals: `"0"` = open, `"1"` = won, `"2"` = lost
- Deal `value` is in **cents** (5760000 = $57,600.00)
- Dates use account timezone offset (e.g., `-05:00` for US/Eastern)
- `links` on each entity provide absolute URLs on the account host, not paths
- `meta.total` is a string, and on contacts it is nested under `meta`
- Unset dates are `null`; unset strings are `""`. The two are not interchangeable
- The contacts response has a third top-level key, `scoreValues`, beside `contacts` and `meta`
- Custom fields are accessed via `/api/3/contacts/{id}/fieldValues` endpoint
- The `{account}` in the base URL must match your ActiveCampaign account subdomain
- For bulk contacts pagination, use `id_greater` param with `orders[id]=ASC` for better performance than offset
- `filters` query parameter uses array format: `filters[field]=value` (matching behavior varies by endpoint)
- Version 1 API remains available with no sunset announced; a GraphQL API is also available

## What this was checked against

The contacts shape above was captured from a live account on 2026-09-14: one
contact, 200 OK, every field and link name as listed. The campaigns endpoint on
that account answers 200 with zero campaigns, so the campaign shape here comes
from the vendor reference below and has not been seen on the wire.

## Reference

- [ActiveCampaign API Home](https://developers.activecampaign.com/)
- [Overview](https://developers.activecampaign.com/reference/overview)
- [Authentication](https://developers.activecampaign.com/reference/authentication)
- [Base URL](https://developers.activecampaign.com/reference/url)
- [Rate Limits](https://developers.activecampaign.com/reference/rate-limits)
- [Pagination, Ordering, and Filtering](https://developers.activecampaign.com/reference/pagination)
- [List All Contacts](https://developers.activecampaign.com/reference/list-all-contacts)
