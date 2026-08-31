# Klaviyo API

## Overview

Klaviyo's API provides access to profiles, flows, campaigns, metrics, lists, segments, and events for email/SMS marketing automation. Uses JSON:API specification for request/response format.

## Base URL

```
https://a.klaviyo.com
```

## Authentication

API key via custom header. Also requires a revision header for API versioning.

```
Authorization: Klaviyo-API-Key {api_key}
revision: 2026-07-15
Content-Type: application/json
Accept: application/json
```

Returns 401 without a valid key:
```json
{
  "errors": [
    {
      "id": "a1b2c3d4-e5f6-7890",
      "status": 401,
      "code": "not_authenticated",
      "title": "Not authenticated.",
      "detail": "Missing or invalid API key.",
      "source": {
        "pointer": "/data"
      }
    }
  ]
}
```

## Rate Limits

Per-account, fixed-window rate limiting with burst and steady windows. Limits vary by endpoint tier:

| Tier | Burst | Steady |
|------|-------|--------|
| XS | 1/s | 15/m |
| S | 3/s | 60/m |
| M | 10/s | 150/m |
| L | 75/s | 700/m |
| XL | 350/s | 3500/m |

- HTTP 429 with `Retry-After` header (seconds) when exceeded
- Success responses include: `RateLimit-Limit`, `RateLimit-Remaining`, `RateLimit-Reset`
- Requests using `additional-fields` or `include` parameters may face stricter limits
- Implement exponential backoff with jitter for retries

---

## Endpoints

### GET /api/profiles

Returns all profiles (contacts). JSON:API format.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page[cursor]` | string | — | Pagination cursor from `links.next` |
| `page[size]` | int | 20 | Results per page (max 100) |
| `filter` | string | — | Filter expression, e.g. `equals(email,"jane@acme.io")` |
| `fields[profile]` | string | — | Sparse fieldset, e.g. `email,first_name,last_name` |
| `sort` | string | — | Sort field, e.g. `created`, `-created` (descending) |
| `include` | string | — | Related resources to include, e.g. `lists,segments` |

**Example Request:**
```bash
curl -H "Authorization: Klaviyo-API-Key kl_mock_apikey_001" \
  -H "revision: 2026-07-15" \
  "https://a.klaviyo.com/api/profiles?page[size]=2"
```

**Example Response:**
```json
{
  "data": [
    {
      "type": "profile",
      "id": "kl_prof_jane_001",
      "attributes": {
        "email": "jane@acme.io",
        "phone_number": "+12125550100",
        "external_id": "ext_jane_001",
        "first_name": "Jane",
        "last_name": "Smith",
        "organization": "Acme Corp",
        "title": "VP Marketing",
        "image": null,
        "created": "2025-03-20T14:30:00+00:00",
        "updated": "2026-07-10T09:00:00+00:00",
        "last_event_date": "2026-07-14T16:22:00+00:00",
        "location": {
          "address1": "123 Main St",
          "address2": null,
          "city": "New York",
          "country": "United States",
          "latitude": 40.7128,
          "longitude": -74.006,
          "region": "NY",
          "zip": "10001",
          "timezone": "America/New_York",
          "ip": null
        },
        "properties": {
          "company_domain": "acme.io",
          "plan": "enterprise",
          "mrr": 4800,
          "signup_source": "website"
        },
        "subscriptions": {
          "email": {
            "marketing": {
              "can_receive_email_marketing": true,
              "consent": "SUBSCRIBED",
              "consent_timestamp": "2025-03-20T14:30:00+00:00"
            }
          },
          "sms": {
            "marketing": {
              "can_receive_sms_marketing": false,
              "consent": "NEVER_SUBSCRIBED"
            }
          }
        },
        "predictive_analytics": {
          "historic_clv": 24500.0,
          "predicted_clv": 36000.0,
          "total_clv": 60500.0,
          "historic_number_of_orders": 12,
          "predicted_number_of_orders": 8,
          "average_days_between_orders": 45.2,
          "average_order_value": 2041.67,
          "churn_probability": 0.15,
          "expected_date_of_next_order": "2026-08-28T00:00:00+00:00"
        }
      },
      "relationships": {
        "lists": {
          "links": {
            "self": "https://a.klaviyo.com/api/profiles/kl_prof_jane_001/relationships/lists/",
            "related": "https://a.klaviyo.com/api/profiles/kl_prof_jane_001/lists/"
          }
        },
        "segments": {
          "links": {
            "self": "https://a.klaviyo.com/api/profiles/kl_prof_jane_001/relationships/segments/",
            "related": "https://a.klaviyo.com/api/profiles/kl_prof_jane_001/segments/"
          }
        }
      },
      "links": {
        "self": "https://a.klaviyo.com/api/profiles/kl_prof_jane_001/"
      }
    },
    {
      "type": "profile",
      "id": "kl_prof_bob_001",
      "attributes": {
        "email": "robert.smith@soylent.co",
        "phone_number": null,
        "external_id": "ext_bob_001",
        "first_name": "Robert",
        "last_name": "Smith",
        "organization": "Soylent Corp",
        "title": "CTO",
        "image": null,
        "created": "2025-06-10T09:00:00+00:00",
        "updated": "2026-06-15T12:00:00+00:00",
        "last_event_date": "2026-07-01T10:00:00+00:00",
        "location": {
          "address1": null,
          "address2": null,
          "city": "San Francisco",
          "country": "United States",
          "latitude": 37.7749,
          "longitude": -122.4194,
          "region": "CA",
          "zip": "94102",
          "timezone": "America/Los_Angeles",
          "ip": null
        },
        "properties": {
          "company_domain": "soylent.co",
          "plan": "growth",
          "mrr": 1200,
          "signup_source": "referral"
        },
        "subscriptions": {
          "email": {
            "marketing": {
              "can_receive_email_marketing": true,
              "consent": "SUBSCRIBED",
              "consent_timestamp": "2025-06-10T09:00:00+00:00"
            }
          },
          "sms": {
            "marketing": {
              "can_receive_sms_marketing": false,
              "consent": "NEVER_SUBSCRIBED"
            }
          }
        },
        "predictive_analytics": {
          "historic_clv": 8400.0,
          "predicted_clv": 12000.0,
          "total_clv": 20400.0,
          "historic_number_of_orders": 7,
          "predicted_number_of_orders": 5,
          "average_days_between_orders": 60.0,
          "average_order_value": 1200.0,
          "churn_probability": 0.35,
          "expected_date_of_next_order": "2026-09-10T00:00:00+00:00"
        }
      },
      "relationships": {
        "lists": {
          "links": {
            "self": "https://a.klaviyo.com/api/profiles/kl_prof_bob_001/relationships/lists/",
            "related": "https://a.klaviyo.com/api/profiles/kl_prof_bob_001/lists/"
          }
        },
        "segments": {
          "links": {
            "self": "https://a.klaviyo.com/api/profiles/kl_prof_bob_001/relationships/segments/",
            "related": "https://a.klaviyo.com/api/profiles/kl_prof_bob_001/segments/"
          }
        }
      },
      "links": {
        "self": "https://a.klaviyo.com/api/profiles/kl_prof_bob_001/"
      }
    }
  ],
  "links": {
    "self": "https://a.klaviyo.com/api/profiles/?page[size]=2",
    "next": "https://a.klaviyo.com/api/profiles/?page[cursor]=bmV4dF9jdXJzb3JfaGVyZQ&page[size]=2",
    "prev": null
  }
}
```

---

### GET /api/flows

Returns all flows (automations).

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page[cursor]` | string | — | Pagination cursor |
| `page[size]` | int | 50 | Results per page |
| `filter` | string | — | e.g. `equals(status,"live")` |
| `fields[flow]` | string | — | Sparse fieldset |
| `sort` | string | — | e.g. `name`, `-created` |

**Example Request:**
```bash
curl -H "Authorization: Klaviyo-API-Key kl_mock_apikey_001" \
  -H "revision: 2026-07-15" \
  "https://a.klaviyo.com/api/flows?page[size]=2"
```

**Example Response:**
```json
{
  "data": [
    {
      "type": "flow",
      "id": "kl_flow_welcome_001",
      "attributes": {
        "name": "Welcome Series",
        "status": "live",
        "archived": false,
        "created": "2025-04-01T10:00:00+00:00",
        "updated": "2026-07-10T09:00:00+00:00",
        "trigger_type": "Added to List"
      },
      "relationships": {
        "flow-actions": {
          "links": {
            "self": "https://a.klaviyo.com/api/flows/kl_flow_welcome_001/relationships/flow-actions/",
            "related": "https://a.klaviyo.com/api/flows/kl_flow_welcome_001/flow-actions/"
          }
        },
        "tags": {
          "links": {
            "self": "https://a.klaviyo.com/api/flows/kl_flow_welcome_001/relationships/tags/",
            "related": "https://a.klaviyo.com/api/flows/kl_flow_welcome_001/tags/"
          }
        }
      },
      "links": {
        "self": "https://a.klaviyo.com/api/flows/kl_flow_welcome_001/"
      }
    },
    {
      "type": "flow",
      "id": "kl_flow_abandon_001",
      "attributes": {
        "name": "Cart Abandonment",
        "status": "live",
        "archived": false,
        "created": "2025-05-15T14:00:00+00:00",
        "updated": "2026-06-20T16:00:00+00:00",
        "trigger_type": "Metric"
      },
      "relationships": {
        "flow-actions": {
          "links": {
            "self": "https://a.klaviyo.com/api/flows/kl_flow_abandon_001/relationships/flow-actions/",
            "related": "https://a.klaviyo.com/api/flows/kl_flow_abandon_001/flow-actions/"
          }
        },
        "tags": {
          "links": {
            "self": "https://a.klaviyo.com/api/flows/kl_flow_abandon_001/relationships/tags/",
            "related": "https://a.klaviyo.com/api/flows/kl_flow_abandon_001/tags/"
          }
        }
      },
      "links": {
        "self": "https://a.klaviyo.com/api/flows/kl_flow_abandon_001/"
      }
    }
  ],
  "links": {
    "self": "https://a.klaviyo.com/api/flows/?page[size]=2",
    "next": "https://a.klaviyo.com/api/flows/?page[cursor]=Zmxvd19uZXh0&page[size]=2",
    "prev": null
  }
}
```

---

### GET /api/campaigns

Returns all campaigns.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page[cursor]` | string | — | Pagination cursor |
| `page[size]` | int | 50 | Results per page |
| `filter` | string | — | e.g. `equals(messages.channel,"email")` |
| `fields[campaign]` | string | — | Sparse fieldset |
| `sort` | string | — | e.g. `-send_time` |

**Example Request:**
```bash
curl -H "Authorization: Klaviyo-API-Key kl_mock_apikey_001" \
  -H "revision: 2026-07-15" \
  "https://a.klaviyo.com/api/campaigns?filter=equals(messages.channel,\"email\")"
```

**Example Response:**
```json
{
  "data": [
    {
      "type": "campaign",
      "id": "kl_camp_newsletter_001",
      "attributes": {
        "name": "July Newsletter",
        "status": "Sent",
        "archived": false,
        "audiences": {
          "included": [
            {"id": "kl_list_newsletter_001"}
          ],
          "excluded": []
        },
        "send_options": {
          "use_smart_sending": true,
          "is_transactional": false
        },
        "tracking_options": {
          "is_add_utm": true,
          "utm_params": [
            {"name": "utm_medium", "value": "email"},
            {"name": "utm_source", "value": "klaviyo"},
            {"name": "utm_campaign", "value": "july-newsletter"}
          ],
          "is_tracking_clicks": true,
          "is_tracking_opens": true
        },
        "send_strategy": {
          "method": "immediate",
          "options_static": null,
          "options_throttled": null,
          "options_sto": null
        },
        "created_at": "2026-07-08T10:00:00+00:00",
        "scheduled_at": "2026-07-10T14:00:00+00:00",
        "updated_at": "2026-07-10T14:05:00+00:00",
        "send_time": "2026-07-10T14:00:00+00:00"
      },
      "relationships": {
        "campaign-messages": {
          "links": {
            "self": "https://a.klaviyo.com/api/campaigns/kl_camp_newsletter_001/relationships/campaign-messages/",
            "related": "https://a.klaviyo.com/api/campaigns/kl_camp_newsletter_001/campaign-messages/"
          }
        },
        "tags": {
          "links": {
            "self": "https://a.klaviyo.com/api/campaigns/kl_camp_newsletter_001/relationships/tags/",
            "related": "https://a.klaviyo.com/api/campaigns/kl_camp_newsletter_001/tags/"
          }
        }
      },
      "links": {
        "self": "https://a.klaviyo.com/api/campaigns/kl_camp_newsletter_001/"
      }
    }
  ],
  "links": {
    "self": "https://a.klaviyo.com/api/campaigns/",
    "next": null,
    "prev": null
  }
}
```

---

### GET /api/metrics

Returns all metrics (event types) tracked.

**Example Request:**
```bash
curl -H "Authorization: Klaviyo-API-Key kl_mock_apikey_001" \
  -H "revision: 2026-07-15" \
  "https://a.klaviyo.com/api/metrics?page[size]=5"
```

**Example Response:**
```json
{
  "data": [
    {
      "type": "metric",
      "id": "kl_metric_opened_001",
      "attributes": {
        "name": "Opened Email",
        "created": "2025-03-20T14:30:00+00:00",
        "updated": "2026-07-14T16:22:00+00:00",
        "integration": {
          "object": "integration",
          "id": "kl_int_001",
          "name": "Klaviyo",
          "category": "Internal"
        }
      },
      "links": {
        "self": "https://a.klaviyo.com/api/metrics/kl_metric_opened_001/"
      }
    },
    {
      "type": "metric",
      "id": "kl_metric_clicked_001",
      "attributes": {
        "name": "Clicked Email",
        "created": "2025-03-20T14:30:00+00:00",
        "updated": "2026-07-14T16:22:00+00:00",
        "integration": {
          "object": "integration",
          "id": "kl_int_001",
          "name": "Klaviyo",
          "category": "Internal"
        }
      },
      "links": {
        "self": "https://a.klaviyo.com/api/metrics/kl_metric_clicked_001/"
      }
    },
    {
      "type": "metric",
      "id": "kl_metric_placed_order_001",
      "attributes": {
        "name": "Placed Order",
        "created": "2025-04-01T10:00:00+00:00",
        "updated": "2026-07-13T08:00:00+00:00",
        "integration": {
          "object": "integration",
          "id": "kl_int_shopify_001",
          "name": "Shopify",
          "category": "eCommerce"
        }
      },
      "links": {
        "self": "https://a.klaviyo.com/api/metrics/kl_metric_placed_order_001/"
      }
    }
  ],
  "links": {
    "self": "https://a.klaviyo.com/api/metrics/?page[size]=5",
    "next": null,
    "prev": null
  }
}
```

---

## Pagination

Cursor-based via `page[cursor]` query parameter. The cursor is found in `links.next`.

```json
{
  "data": [...],
  "links": {
    "self": "https://a.klaviyo.com/api/profiles/?page[size]=20",
    "next": "https://a.klaviyo.com/api/profiles/?page[cursor]=bmV4dF9jdXJzb3I&page[size]=20",
    "prev": null
  }
}
```

- Extract the full `links.next` URL and follow it for the next page
- Or extract the `page[cursor]` value from the URL and pass it as a query param
- `page[size]` controls results per page (default varies by endpoint, max 100 for profiles)
- When `links.next` is `null`, there are no more results

## Error Responses

JSON:API error format:

```json
{
  "errors": [
    {
      "id": "unique-error-id",
      "status": 404,
      "code": "not_found",
      "title": "Not found.",
      "detail": "Profile with id 'invalid' not found.",
      "source": {
        "pointer": "/data/id"
      }
    }
  ]
}
```

| HTTP Status | Code | Meaning |
|-------------|------|---------|
| 400 | invalid | Invalid request / malformed filter |
| 401 | not_authenticated | Invalid or missing API key |
| 403 | not_authorized | Insufficient scope or permissions |
| 404 | not_found | Resource doesn't exist |
| 409 | conflict | Duplicate profile (email already exists) |
| 429 | throttled | Rate limit exceeded |
| 500 | internal_error | Server error |

## Notes

- **JSON:API format** — all responses follow the JSON:API spec with `type`, `id`, `attributes`, `relationships`, `links`
- **Revision header** is required — `revision: 2026-07-15` (or latest). Without it, you get older response shapes
- **Filter syntax** uses Klaviyo's filter language: `equals(field,"value")`, `greater-than(created,"2026-01-01")`, `any(list_id,["id1","id2"])`
- **Sparse fieldsets** via `fields[resource_type]` — reduces response payload
- **Relationships** are lazy-loaded — use `include` param to sideload related resources
- Profile `properties` is a freeform object — any key/value pairs set via API or integrations
- `predictive_analytics` only populated for profiles with enough event history
- Campaign `status` values: `Draft`, `Scheduled`, `Sending`, `Sent`, `Cancelled`
- Flow `status` values: `draft`, `manual`, `live`
- Flow `trigger_type` values: `Added to List`, `Metric`, `Date Based`, `Unconfigured`, `Price Drop`, `Segment`
- Revision deprecation policy: 2 years (1 year stable, 1 year deprecated, then retired)
- OAuth also supported: `Authorization: Bearer {access_token}` with same revision header

## Reference

- [API Overview](https://developers.klaviyo.com/en/reference/api_overview)
- [Authenticate API Requests](https://developers.klaviyo.com/en/docs/authenticate_)
- [Rate Limits and Error Handling](https://developers.klaviyo.com/en/docs/rate_limits_and_error_handling)
- [API Versioning and Deprecation Policy](https://developers.klaviyo.com/en/docs/api_versioning_and_deprecation_policy)
- [Profiles API](https://developers.klaviyo.com/en/reference/profiles_api_overview)
- [Campaigns API](https://developers.klaviyo.com/en/reference/campaigns_api_overview)
- [Flows API](https://developers.klaviyo.com/en/reference/flows_api_overview)
- [Metrics API](https://developers.klaviyo.com/en/reference/metrics_api_overview)
- [Reporting API](https://developers.klaviyo.com/en/reference/reporting_api_overview)
