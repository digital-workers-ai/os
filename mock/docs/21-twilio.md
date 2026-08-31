# Twilio REST API

## Overview

Twilio's REST API provides programmatic access to messaging (SMS/MMS), voice calls, phone numbers, and account management. Resources are organized under Account SIDs.

## Base URL

```
https://api.twilio.com
```

## Authentication

HTTP Basic Auth with Account SID as username and Auth Token as password. For production, Twilio recommends using API keys (API key SID as username, API key secret as password) instead of the Account Auth Token.

```
Authorization: Basic {base64(ACCOUNT_SID:AUTH_TOKEN)}
Content-Type: application/x-www-form-urlencoded  (for POST)
Accept: application/json
```

```bash
curl -u "AC_mock_sid_001:mock_auth_token_001" \
  https://api.twilio.com/2010-04-01/Accounts/AC_mock_sid_001/Messages.json
```

Returns 401 without valid credentials:
```json
{
  "code": 20003,
  "message": "Authenticate",
  "more_info": "https://www.twilio.com/docs/errors/20003",
  "status": 401
}
```

## Rate Limits

- **API requests:** Concurrent request limit per account (monitor via `Twilio-Concurrent-Requests` response header)
- **SMS:** 1 message/second per phone number (US long codes); higher for short codes and toll-free
- **Calls:** 1 call/second per phone number
- HTTP 429 (error code 20429) when concurrency limit exceeded; implement exponential backoff for retries
- Response includes `Twilio-Concurrent-Requests` and `Twilio-Request-Duration` headers

---

## Endpoints

### GET /2010-04-01/Accounts/{AccountSid}/Messages.json

Returns SMS/MMS messages.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `PageSize` | int | 50 | Results per page (max 1000) |
| `Page` | int | 0 | Page number (zero-based) |
| `PageToken` | string | — | Token for next/prev page |
| `To` | string | — | Filter by recipient phone number |
| `From` | string | — | Filter by sender phone number |
| `DateSent` | string | — | Filter by date (YYYY-MM-DD), supports `>`, `<`, `>=`, `<=` prefixes |
| `Status` | string | — | Filter by status |

**Example Request:**
```bash
curl -u "AC_mock_sid_001:mock_auth_token_001" \
  "https://api.twilio.com/2010-04-01/Accounts/AC_mock_sid_001/Messages.json?PageSize=2"
```

**Example Response:**
```json
{
  "first_page_uri": "/2010-04-01/Accounts/AC_mock_sid_001/Messages.json?PageSize=2&Page=0",
  "end": 1,
  "previous_page_uri": null,
  "messages": [
    {
      "account_sid": "AC_mock_sid_001",
      "api_version": "2010-04-01",
      "body": "Hi Jane, your Acme Corp subscription has been renewed. View your invoice at https://acme.io/invoices/inv_001",
      "date_created": "Wed, 10 Jul 2026 14:00:00 +0000",
      "date_updated": "Wed, 10 Jul 2026 14:00:02 +0000",
      "date_sent": "Wed, 10 Jul 2026 14:00:01 +0000",
      "direction": "outbound-api",
      "error_code": null,
      "error_message": null,
      "from": "+15551234567",
      "messaging_service_sid": "MG_mock_svc_001",
      "num_media": "0",
      "num_segments": "1",
      "price": "-0.0075",
      "price_unit": "USD",
      "sid": "SM_acme_msg_001",
      "status": "delivered",
      "subresource_uris": {
        "media": "/2010-04-01/Accounts/AC_mock_sid_001/Messages/SM_acme_msg_001/Media.json",
        "feedback": "/2010-04-01/Accounts/AC_mock_sid_001/Messages/SM_acme_msg_001/Feedback.json"
      },
      "to": "+12125550100",
      "uri": "/2010-04-01/Accounts/AC_mock_sid_001/Messages/SM_acme_msg_001.json"
    },
    {
      "account_sid": "AC_mock_sid_001",
      "api_version": "2010-04-01",
      "body": "Your verification code is 847291. It expires in 10 minutes.",
      "date_created": "Wed, 10 Jul 2026 13:45:00 +0000",
      "date_updated": "Wed, 10 Jul 2026 13:45:03 +0000",
      "date_sent": "Wed, 10 Jul 2026 13:45:01 +0000",
      "direction": "outbound-api",
      "error_code": null,
      "error_message": null,
      "from": "+15551234567",
      "messaging_service_sid": "MG_mock_svc_001",
      "num_media": "0",
      "num_segments": "1",
      "price": "-0.0075",
      "price_unit": "USD",
      "sid": "SM_acme_msg_002",
      "status": "delivered",
      "subresource_uris": {
        "media": "/2010-04-01/Accounts/AC_mock_sid_001/Messages/SM_acme_msg_002/Media.json",
        "feedback": "/2010-04-01/Accounts/AC_mock_sid_001/Messages/SM_acme_msg_002/Feedback.json"
      },
      "to": "+12125550100",
      "uri": "/2010-04-01/Accounts/AC_mock_sid_001/Messages/SM_acme_msg_002.json"
    }
  ],
  "next_page_uri": "/2010-04-01/Accounts/AC_mock_sid_001/Messages.json?PageSize=2&Page=1&PageToken=PASMacme003",
  "page": 0,
  "page_size": 2,
  "start": 0,
  "uri": "/2010-04-01/Accounts/AC_mock_sid_001/Messages.json?PageSize=2&Page=0"
}
```

---

### GET /2010-04-01/Accounts/{AccountSid}/Calls.json

Returns voice calls.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `PageSize` | int | 50 | Results per page (max 1000) |
| `Page` | int | 0 | Page number |
| `PageToken` | string | — | Token for next/prev page |
| `To` | string | — | Filter by recipient |
| `From` | string | — | Filter by caller |
| `Status` | string | — | Filter by status |
| `StartTime` | string | — | Filter by start time (YYYY-MM-DD, supports `>`, `<` prefixes) |

**Example Request:**
```bash
curl -u "AC_mock_sid_001:mock_auth_token_001" \
  "https://api.twilio.com/2010-04-01/Accounts/AC_mock_sid_001/Calls.json?PageSize=2"
```

**Example Response:**
```json
{
  "first_page_uri": "/2010-04-01/Accounts/AC_mock_sid_001/Calls.json?PageSize=2&Page=0",
  "end": 1,
  "previous_page_uri": null,
  "calls": [
    {
      "account_sid": "AC_mock_sid_001",
      "annotation": null,
      "answered_by": "human",
      "api_version": "2010-04-01",
      "caller_name": "ACME CORP",
      "date_created": "Mon, 14 Jul 2026 10:00:00 +0000",
      "date_updated": "Mon, 14 Jul 2026 10:05:30 +0000",
      "direction": "outbound-api",
      "duration": "330",
      "end_time": "Mon, 14 Jul 2026 10:05:30 +0000",
      "forwarded_from": null,
      "from": "+15551234567",
      "from_formatted": "(555) 123-4567",
      "group_sid": null,
      "parent_call_sid": null,
      "phone_number_sid": "PN_mock_001",
      "price": "-0.0130",
      "price_unit": "USD",
      "queue_time": "0",
      "sid": "CA_acme_call_001",
      "start_time": "Mon, 14 Jul 2026 10:00:00 +0000",
      "status": "completed",
      "subresource_uris": {
        "notifications": "/2010-04-01/Accounts/AC_mock_sid_001/Calls/CA_acme_call_001/Notifications.json",
        "recordings": "/2010-04-01/Accounts/AC_mock_sid_001/Calls/CA_acme_call_001/Recordings.json",
        "events": "/2010-04-01/Accounts/AC_mock_sid_001/Calls/CA_acme_call_001/Events.json",
        "feedback": "/2010-04-01/Accounts/AC_mock_sid_001/Calls/CA_acme_call_001/Feedback.json",
        "feedback_summaries": "/2010-04-01/Accounts/AC_mock_sid_001/Calls/FeedbackSummary.json",
        "payments": "/2010-04-01/Accounts/AC_mock_sid_001/Calls/CA_acme_call_001/Payments.json",
        "siprec": "/2010-04-01/Accounts/AC_mock_sid_001/Calls/CA_acme_call_001/Siprec.json",
        "streams": "/2010-04-01/Accounts/AC_mock_sid_001/Calls/CA_acme_call_001/Streams.json",
        "user_defined_message_subscriptions": "/2010-04-01/Accounts/AC_mock_sid_001/Calls/CA_acme_call_001/UserDefinedMessageSubscriptions.json",
        "user_defined_messages": "/2010-04-01/Accounts/AC_mock_sid_001/Calls/CA_acme_call_001/UserDefinedMessages.json",
        "transcriptions": "/2010-04-01/Accounts/AC_mock_sid_001/Calls/CA_acme_call_001/Transcriptions.json"
      },
      "to": "+12125550100",
      "to_formatted": "(212) 555-0100",
      "trunk_sid": null,
      "uri": "/2010-04-01/Accounts/AC_mock_sid_001/Calls/CA_acme_call_001.json"
    }
  ],
  "next_page_uri": "/2010-04-01/Accounts/AC_mock_sid_001/Calls.json?PageSize=2&Page=1&PageToken=PACAacme002",
  "page": 0,
  "page_size": 2,
  "start": 0,
  "uri": "/2010-04-01/Accounts/AC_mock_sid_001/Calls.json?PageSize=2&Page=0"
}
```

---

### GET /2010-04-01/Accounts/{AccountSid}.json

Returns account info.

**Example Request:**
```bash
curl -u "AC_mock_sid_001:mock_auth_token_001" \
  "https://api.twilio.com/2010-04-01/Accounts/AC_mock_sid_001.json"
```

**Example Response:**
```json
{
  "auth_token": "mock_auth_token_001",
  "date_created": "Fri, 10 Jan 2025 08:00:00 +0000",
  "date_updated": "Mon, 14 Jul 2026 12:00:00 +0000",
  "friendly_name": "Acme Corp",
  "owner_account_sid": "AC_mock_sid_001",
  "sid": "AC_mock_sid_001",
  "status": "active",
  "subresource_uris": {
    "available_phone_numbers": "/2010-04-01/Accounts/AC_mock_sid_001/AvailablePhoneNumbers.json",
    "calls": "/2010-04-01/Accounts/AC_mock_sid_001/Calls.json",
    "conferences": "/2010-04-01/Accounts/AC_mock_sid_001/Conferences.json",
    "incoming_phone_numbers": "/2010-04-01/Accounts/AC_mock_sid_001/IncomingPhoneNumbers.json",
    "messages": "/2010-04-01/Accounts/AC_mock_sid_001/Messages.json",
    "notifications": "/2010-04-01/Accounts/AC_mock_sid_001/Notifications.json",
    "outgoing_caller_ids": "/2010-04-01/Accounts/AC_mock_sid_001/OutgoingCallerIds.json",
    "recordings": "/2010-04-01/Accounts/AC_mock_sid_001/Recordings.json",
    "usage": "/2010-04-01/Accounts/AC_mock_sid_001/Usage.json"
  },
  "type": "Full",
  "uri": "/2010-04-01/Accounts/AC_mock_sid_001.json"
}
```

---

## Pagination

Page-based with `PageToken` for navigation.

```json
{
  "messages": [...],
  "first_page_uri": "/...Messages.json?PageSize=50&Page=0",
  "next_page_uri": "/...Messages.json?PageSize=50&Page=1&PageToken=PASMxxx",
  "previous_page_uri": null,
  "page": 0,
  "page_size": 50,
  "start": 0,
  "end": 49,
  "uri": "/...Messages.json?PageSize=50&Page=0"
}
```

- `PageSize`: items per page (default 50, max 1000)
- `Page`: zero-based page number
- `PageToken`: opaque token for next/prev page navigation — follow `next_page_uri` for reliability
- Done when `next_page_uri` is `null` or empty string `""`
- `start` and `end` give the item index range for the current page

## Error Responses

```json
{
  "code": 20404,
  "message": "The requested resource /2010-04-01/Accounts/AC_mock_sid_001/Messages/SM_invalid.json was not found",
  "more_info": "https://www.twilio.com/docs/errors/20404",
  "status": 404
}
```

| HTTP Status | Code | Meaning |
|-------------|------|---------|
| 400 | 21211 | Invalid 'To' phone number |
| 401 | 20003 | Authentication failed |
| 403 | 20006 | Access denied |
| 404 | 20404 | Resource not found |
| 429 | 20429 | Too many requests |
| 500 | 20500 | Internal server error |

## Notes

- **SID prefixes** identify resource types: `AC` = Account, `SM` = Message, `CA` = Call, `MG` = Messaging Service, `PN` = Phone Number
- `price` is a **negative string** representing cost to you (e.g., `"-0.0075"`)
- `duration` on calls is a **string** in seconds
- Dates are **RFC 2822** format (e.g., `"Wed, 10 Jul 2026 14:00:00 +0000"`), not ISO 8601
- Message `status` lifecycle: `queued` → `sending` → `sent` → `delivered` (or `failed`/`undelivered`)
- Call `status` lifecycle: `queued` → `ringing` → `in-progress` → `completed` (or `busy`/`failed`/`no-answer`/`canceled`)
- `direction` values: `inbound`, `outbound-api`, `outbound-dial`, `trunking-terminating`, `trunking-originating`
- All resources include `subresource_uris` for discovering related endpoints
- POST requests use `application/x-www-form-urlencoded`, not JSON
- The `2010-04-01` in the URL is the API version date, not a historical date -- it's the current and only version
- 2010 APIs support XML (default), JSON (`.json` extension), and CSV (`.csv` extension) response formats; use `.json` suffix on resource URIs for JSON
- Phone numbers use E.164 format (e.g., `+14155554345`)
- Subaccounts have independent concurrency limits from the parent account
- Error response fields: `status` (HTTP code), `message` (explanation), `code` (Twilio error code, optional), `more_info` (docs URL, optional)

## Reference

- [Twilio API Overview](https://www.twilio.com/docs/usage/api)
- [Twilio API Responses (Pagination, Errors, Formats)](https://www.twilio.com/docs/usage/twilios-response)
- [API Best Practices (Rate Limits, Auth)](https://www.twilio.com/docs/usage/rest-api-best-practices)
- [IAM / Authentication](https://www.twilio.com/docs/iam/api)
- [Message Resource](https://www.twilio.com/docs/messaging/api/message-resource)
- [Call Resource](https://www.twilio.com/docs/voice/api/call-resource)
