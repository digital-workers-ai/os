# Salesforce REST API v67.0

## Overview

Salesforce CRM REST API for querying and managing sales objects (Account, Contact, Lead, Opportunity, Case, Campaign). Uses SOQL (Salesforce Object Query Language) for data retrieval. Currently at API version v67.0 (Summer '26).

## Base URL

```
https://{MyDomainName}.my.salesforce.com/services/data/v67.0/
```

The instance domain is org-specific (e.g., `acme.my.salesforce.com`).

Mock server prefix: `/salesforce/services/data/v67.0`

## Authentication

OAuth 2.0 Bearer token. Multiple grant types supported.

```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**Token endpoint:** `https://login.salesforce.com/services/oauth2/token`

**Grant types:**
- Authorization code (web server flow)
- Client credentials
- JWT bearer token
- Refresh token
- Session ID from SOAP login (also valid as Bearer token)

## Endpoints

### GET /query/?q={SOQL}

Execute a SOQL query.

**Query parameters:**
- `q` — URL-encoded SOQL query string

**Example request — Accounts:**

```
GET /salesforce/services/data/v67.0/query/?q=SELECT+Id,Name,Industry,Website,AnnualRevenue,NumberOfEmployees,BillingCity,BillingState,BillingCountry,CreatedDate+FROM+Account+ORDER+BY+CreatedDate+DESC+LIMIT+100
```

**Response:**

```json
{
  "totalSize": 3,
  "done": true,
  "records": [
    {
      "attributes": {
        "type": "Account",
        "url": "/services/data/v67.0/sobjects/Account/001xx000003DGbYAAW"
      },
      "Id": "001xx000003DGbYAAW",
      "Name": "Acme Corp",
      "Industry": "Technology",
      "Website": "https://acme.io",
      "AnnualRevenue": 5400000.00,
      "NumberOfEmployees": 120,
      "BillingCity": "San Francisco",
      "BillingState": "CA",
      "BillingCountry": "United States",
      "CreatedDate": "2025-03-15T10:30:00.000+0000"
    },
    {
      "attributes": {
        "type": "Account",
        "url": "/services/data/v67.0/sobjects/Account/001xx000003DGbZAAW"
      },
      "Id": "001xx000003DGbZAAW",
      "Name": "Globex Inc",
      "Industry": "Manufacturing",
      "Website": "https://globex.com",
      "AnnualRevenue": 2800000.00,
      "NumberOfEmployees": 85,
      "BillingCity": "Chicago",
      "BillingState": "IL",
      "BillingCountry": "United States",
      "CreatedDate": "2025-06-20T14:15:00.000+0000"
    },
    {
      "attributes": {
        "type": "Account",
        "url": "/services/data/v67.0/sobjects/Account/001xx000003DGbaAAG"
      },
      "Id": "001xx000003DGbaAAG",
      "Name": "Initech LLC",
      "Industry": "Software",
      "Website": "https://initech.io",
      "AnnualRevenue": 1200000.00,
      "NumberOfEmployees": 45,
      "BillingCity": "Austin",
      "BillingState": "TX",
      "BillingCountry": "United States",
      "CreatedDate": "2025-09-01T08:00:00.000+0000"
    }
  ]
}
```

**Example request — Contacts:**

```
GET /salesforce/services/data/v67.0/query/?q=SELECT+Id,FirstName,LastName,Email,Phone,Title,AccountId,Account.Name,CreatedDate+FROM+Contact+WHERE+AccountId!=null+ORDER+BY+CreatedDate+DESC
```

**Response:**

```json
{
  "totalSize": 2,
  "done": true,
  "records": [
    {
      "attributes": {
        "type": "Contact",
        "url": "/services/data/v67.0/sobjects/Contact/003xx000004TmfQAAS"
      },
      "Id": "003xx000004TmfQAAS",
      "FirstName": "Jane",
      "LastName": "Smith",
      "Email": "jane.smith@acme.io",
      "Phone": "+1-415-555-0101",
      "Title": "VP of Engineering",
      "AccountId": "001xx000003DGbYAAW",
      "Account": {
        "attributes": {
          "type": "Account",
          "url": "/services/data/v67.0/sobjects/Account/001xx000003DGbYAAW"
        },
        "Name": "Acme Corp"
      },
      "CreatedDate": "2025-04-01T09:00:00.000+0000"
    },
    {
      "attributes": {
        "type": "Contact",
        "url": "/services/data/v67.0/sobjects/Contact/003xx000004TmfRAAS"
      },
      "Id": "003xx000004TmfRAAS",
      "FirstName": "Bob",
      "LastName": "Johnson",
      "Email": "bob@globex.com",
      "Phone": "+1-312-555-0202",
      "Title": "CTO",
      "AccountId": "001xx000003DGbZAAW",
      "Account": {
        "attributes": {
          "type": "Account",
          "url": "/services/data/v67.0/sobjects/Account/001xx000003DGbZAAW"
        },
        "Name": "Globex Inc"
      },
      "CreatedDate": "2025-07-15T11:30:00.000+0000"
    }
  ]
}
```

**Example request — Opportunities:**

```
GET /salesforce/services/data/v67.0/query/?q=SELECT+Id,Name,StageName,Amount,CloseDate,Probability,AccountId,Account.Name+FROM+Opportunity+WHERE+IsClosed=false+ORDER+BY+CloseDate+ASC
```

**Response:**

```json
{
  "totalSize": 2,
  "done": true,
  "records": [
    {
      "attributes": {
        "type": "Opportunity",
        "url": "/services/data/v67.0/sobjects/Opportunity/006xx000005IxrFAAS"
      },
      "Id": "006xx000005IxrFAAS",
      "Name": "Acme Corp - Enterprise Upgrade",
      "StageName": "Negotiation/Review",
      "Amount": 120000.00,
      "CloseDate": "2026-08-15",
      "Probability": 75,
      "AccountId": "001xx000003DGbYAAW",
      "Account": {
        "attributes": {
          "type": "Account",
          "url": "/services/data/v67.0/sobjects/Account/001xx000003DGbYAAW"
        },
        "Name": "Acme Corp"
      }
    },
    {
      "attributes": {
        "type": "Opportunity",
        "url": "/services/data/v67.0/sobjects/Opportunity/006xx000005IxrGAAS"
      },
      "Id": "006xx000005IxrGAAS",
      "Name": "Globex - New Business",
      "StageName": "Proposal/Price Quote",
      "Amount": 45000.00,
      "CloseDate": "2026-07-30",
      "Probability": 50,
      "AccountId": "001xx000003DGbZAAW",
      "Account": {
        "attributes": {
          "type": "Account",
          "url": "/services/data/v67.0/sobjects/Account/001xx000003DGbZAAW"
        },
        "Name": "Globex Inc"
      }
    }
  ]
}
```

**Paginated response (large result set):**

```json
{
  "totalSize": 5000,
  "done": false,
  "nextRecordsUrl": "/services/data/v67.0/query/01gxx00000XXXXXXAAQ-2000",
  "records": [...]
}
```

### GET /query/{query_locator}

Fetch next page of a paginated SOQL query. The `query_locator` is extracted from `nextRecordsUrl`.

**Example request:**

```
GET /salesforce/services/data/v67.0/query/01gxx00000XXXXXXAAQ-2000
```

**Response:** Same shape as initial query response, with `done: true` on the last page.

### GET /sobjects/{ObjectName}/

Describe an object or list recent items.

**Example request:**

```
GET /salesforce/services/data/v67.0/sobjects/Account/
```

**Response:**

```json
{
  "objectDescribe": {
    "name": "Account",
    "label": "Account",
    "labelPlural": "Accounts",
    "keyPrefix": "001",
    "custom": false,
    "urls": {
      "sobject": "/services/data/v67.0/sobjects/Account",
      "describe": "/services/data/v67.0/sobjects/Account/describe",
      "rowTemplate": "/services/data/v67.0/sobjects/Account/{ID}"
    }
  },
  "recentItems": [
    {
      "attributes": {
        "type": "Account",
        "url": "/services/data/v67.0/sobjects/Account/001xx000003DGbYAAW"
      },
      "Id": "001xx000003DGbYAAW",
      "Name": "Acme Corp"
    }
  ]
}
```

### GET /limits/

Get org API usage limits.

**Response:**

```json
{
  "DailyApiRequests": {
    "Max": 100000,
    "Remaining": 94523
  },
  "DailyBulkApiRequests": {
    "Max": 15000,
    "Remaining": 15000
  },
  "DailyBulkV2QueryJobs": {
    "Max": 10000,
    "Remaining": 10000
  },
  "ConcurrentAsyncGetReportInstances": {
    "Max": 200,
    "Remaining": 200
  },
  "ConcurrentSyncReportRuns": {
    "Max": 20,
    "Remaining": 20
  },
  "DataStorageMB": {
    "Max": 1024,
    "Remaining": 780
  },
  "FileStorageMB": {
    "Max": 1024,
    "Remaining": 950
  },
  "HourlyDashboardRefreshes": {
    "Max": 200,
    "Remaining": 200
  },
  "MassEmail": {
    "Max": 5000,
    "Remaining": 5000
  },
  "SingleEmail": {
    "Max": 5000,
    "Remaining": 4980
  },
  "StreamingApiConcurrentClients": {
    "Max": 2000,
    "Remaining": 2000
  }
}
```

## Pagination

- **Mechanism:** Cursor chain via `nextRecordsUrl`
- **Default page size:** 2,000 records per page (configurable via `Sforce-Query-Options: batchSize=N` header; range 200-2,000; not guaranteed at runtime)
- **To get next page:** `GET {nextRecordsUrl}` (path is relative to instance base)
- **Done when:** `done: true` in response
- **`nextRecordsUrl` absent** when `done: true`

```
Page 1: GET /query/?q=SELECT...
         → done: false, nextRecordsUrl: "/services/data/v67.0/query/01g...-2000"
Page 2: GET /query/01g...-2000
         → done: false, nextRecordsUrl: "/services/data/v67.0/query/01g...-4000"
Page 3: GET /query/01g...-4000
         → done: true  (no nextRecordsUrl)
```

## Rate Limits

Per-org 24-hour rolling window:

| Edition | Daily Limit | Concurrent (>20s) |
|---------|-------------|-------------------|
| Developer | 15,000 | 5 |
| Enterprise/Professional | 100,000 + 1,000/license | 25 |
| Unlimited | 100,000 + 5,000/license | 25 |

Check via `GET /limits/` → `DailyApiRequests.Remaining`.

## Error Responses

**401 Unauthorized:**
```json
[
  {
    "message": "Session expired or invalid",
    "errorCode": "INVALID_SESSION_ID"
  }
]
```

**400 Bad SOQL:**
```json
[
  {
    "message": "unexpected token: 'SELEC'",
    "errorCode": "MALFORMED_QUERY"
  }
]
```

**403 Forbidden:**
```json
[
  {
    "message": "sObject type 'CustomObj__c' is not supported",
    "errorCode": "INVALID_TYPE"
  }
]
```

**503 Rate limited:**
```json
[
  {
    "message": "Request limit exceeded",
    "errorCode": "REQUEST_LIMIT_EXCEEDED"
  }
]
```

Note: Salesforce errors are returned as JSON arrays (not objects).

## Notes

- SOQL is SQL-like but not SQL: no `JOIN` keyword, uses relationship traversal instead (e.g., `Account.Name` from Contact)
- Date format: ISO 8601 with timezone offset (`2025-03-15T10:30:00.000+0000`)
- Date-only fields use `YYYY-MM-DD` format (e.g., `CloseDate`)
- Each record has an `attributes` object with `type` and `url` — these are metadata, not user fields
- Currency values are plain floats (e.g., `120000.00`), not in cents
- Standard objects: Account, Contact, Lead, Opportunity, Case, Campaign, Task, Event
- ID format: 15 or 18 character alphanumeric string (e.g., `001xx000003DGbYAAW`)
- Supports both JSON and XML responses (JSON is default and recommended)

## Reference

- [Query endpoint](https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_query.htm) -- GET /query/ resource reference
- [Execute a SOQL Query](https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/dome_query.htm) -- Query execution examples
- [Query More Results](https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_query_more_results.htm) -- Pagination via nextRecordsUrl
- [Query Options Header](https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/headers_queryoptions.htm) -- Sforce-Query-Options batch size header
- [API Versions](https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_versions.htm) -- Version numbers by release (v67.0 = Summer '26)
- [REST API Reference](https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_list.htm) -- Full REST API resource listing
