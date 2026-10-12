# API Specification – Batch 1 (User, NGO, Animal) & Batch 2A (Rescue Cases)

## Overview
This document defines the REST API contracts for PawConnect. It covers **User profile**, **NGO profile**, and **Animal listing** endpoints (Batch 1), as well as **Rescue Case management** endpoints (Batch 2A). All endpoints use JSON request/response bodies and follow a common response envelope.

### Common Response Envelope
```json
{
  "status": "success" | "error",
  "message": "Human‑readable description (optional on success)",
  "data": { ... }   // present only on success
}
```
* Errors return HTTP status codes appropriate to the situation (see §5).
* **Authentication / authorization errors** (produced by the existing decorators) return only `status` and `message`. They do **not** include a `details` field.
* **Validation errors** (produced by endpoint logic, not yet implemented) will return `status`, `message`, and an optional `details` object with field‑level messages. This is a proposed convention for future endpoint code, not existing behaviour.

### Authentication & Authorization
* `@cognito_required(require_pawconnect_user=True)` validates a Cognito JWT, resolves the PawConnect `User` record, and populates `g.current_user`.
* `@roles_required(RoleName.NGO, ...)` additionally checks the user's role.
* **Missing/invalid/expired token** → **401 Unauthorized** with `{"status":"error","message":"…"}`.
* **Cognito configuration error** → **503 Service Unavailable** with `{"status":"error","message":"…"}`.
* **Valid JWT but no local PawConnect user** → **403 Forbidden** with message *"No registered PawConnect profile found for this authenticated user."*
* **Valid JWT + PawConnect user but wrong role** → **403 Forbidden** with message *"You do not have permission to access this resource."*

---

## 1. User Profile Endpoints

| Method | URL | Auth | Allowed Roles | Description |
|--------|-----|------|--------------|-------------|
| GET | `/api/users/me` | `@cognito_required(require_pawconnect_user=True)` | Any role | Return the authenticated user's own profile. |
| PATCH | `/api/users/me` | `@cognito_required(require_pawconnect_user=True)` | Any role | Update the authenticated user's mutable fields. |

### GET `/api/users/me`

**Success (200):**
```json
{
  "status": "success",
  "data": {
    "user_id": 1,
    "name": "Jane Doe",
    "email": "jane@example.com",
    "phone": "+1234567890",
    "location": "Bangalore",
    "role": "User"
  }
}
```

**Errors:** 401 (no/invalid token), 403 (no PawConnect profile).

### PATCH `/api/users/me`

**Request body** — JSON with at least one mutable field:

| Field | Type | Max Length | Notes |
|-------|------|-----------|-------|
| `name` | string | 100 | Non‑empty when provided. |
| `phone` | string | 20 | |
| `location` | string | 255 | |

**Protected fields** (`user_id`, `email`, `role_id`, `auth_id`, `created_at`) — supplying any of these → **400**.

**Errors:** 400 (validation / unknown fields / empty payload), 401, 403.

---

## 2. NGO Profile Endpoints

| Method | URL | Auth | Allowed Roles | Description |
|--------|-----|------|--------------|-------------|
| GET | `/api/ngos/me` | `@roles_required(RoleName.NGO)` | NGO | Return the authenticated user's NGO profile. |
| POST | `/api/ngos` | `@roles_required(RoleName.NGO)` | NGO | Create an NGO profile for the authenticated user. |
| PATCH | `/api/ngos/me` | `@roles_required(RoleName.NGO)` | NGO | Update the authenticated user's NGO profile. |

### GET `/api/ngos/me`

**Ownership:** The endpoint returns the NGO linked to `g.current_user` (via `User.ngo`). If no linked NGO exists → **404**.

**Success (200):**
```json
{
  "status": "success",
  "data": {
    "ngo_id": 1,
    "name": "Happy Paws Shelter",
    "description": "Animal rescue in Bangalore",
    "location": "Bangalore",
    "contact": "info@happypaws.org",
    "verification_status": "Unverified"
  }
}
```

**Errors:** 401, 403 (no PawConnect profile / wrong role), 404 (no linked NGO).

### POST `/api/ngos`

**Precondition:** The authenticated user must not already have an NGO record. If one exists → **409 Conflict**.

**Request body:**

| Field | Type | Max Length | Required | Notes |
|-------|------|-----------|----------|-------|
| `name` | string | 255 | **Yes** | Model column is `nullable=False`. Non‑empty. |
| `description` | text | 2000 (API limit) | No | Model column is `nullable=True`. DB type is `Text` (unbounded); API enforces a 2 000‑character limit. |
| `location` | string | 255 | No | Model column is `nullable=True`. |
| `contact` | string | 255 | No | Model column is `nullable=True`. |

**Approved decision:** Only `name` is required. `description`, `location`, and `contact` are optional at creation.

**Protected fields** (`ngo_id`, `user_id`, `verification_status`) — supplying any → **400**.

`verification_status` is set to the model's default (`"Unverified"`) and cannot be set or changed through this endpoint.

**Success (201):** Created NGO in `data`.

**Errors:** 400, 401, 403, 409.

### PATCH `/api/ngos/me`

**Request body** — JSON with at least one mutable field:

| Field | Type | Max Length |
|-------|------|-----------|
| `name` | string | 255 |
| `description` | text | 2000 (API limit) |
| `location` | string | 255 |
| `contact` | string | 255 |

**Protected fields** (`ngo_id`, `user_id`, `verification_status`) — supplying any → **400**.

**Errors:** 400 (validation / empty payload), 401, 403, 404 (no linked NGO).

---

## 3. Animal Listing Endpoints

| Method | URL | Auth | Allowed Roles | Description |
|--------|-----|------|--------------|-------------|
| GET | `/api/animals` | None (public) | Any | List animals with status `"Available"`, paginated. |
| GET | `/api/animals/<int:animal_id>` | None (public) | Any | Get a single animal by ID. |
| POST | `/api/animals` | `@roles_required(RoleName.NGO)` | NGO | Create an animal listing. |
| PATCH | `/api/animals/<int:animal_id>` | `@roles_required(RoleName.NGO)` | NGO | Update an animal listing. |
| DELETE | `/api/animals/<int:animal_id>` | `@roles_required(RoleName.NGO)` | NGO | Delete an animal listing (hard delete). |

### GET `/api/animals` (public)

**Visibility filter:** This endpoint returns only animals whose `status` is `"Available"`. Animals with other statuses (`Adopted`, `Under Treatment`, `Foster`) are **not** included in public listings. They remain accessible only to their owning NGO through authenticated endpoints (future batch).

**Query parameters:**

| Param | Type | Default | Max | Notes |
|-------|------|---------|-----|-------|
| `page` | int | 1 | — | Must be ≥ 1. |
| `per_page` | int | 20 | 100 | |

**Success (200):**
```json
{
  "status": "success",
  "data": {
    "items": [ { "animal_id": 1, "name": "Buddy", "species": "Dog", "status": "Available", "..." : "..." } ],
    "page": 1,
    "per_page": 20,
    "total": 42
  }
}
```

**Errors:** 400 (invalid pagination params).

### GET `/api/animals/<int:animal_id>` (public)

Returns a single animal object.

**Errors:** 404 (animal not found).

### POST `/api/animals`

**Ownership:** The `ngo_id` is set to `g.current_user.ngo.ngo_id`. If the user has no linked NGO → **404**.

**Request body:**

| Field | Type | Max Length | Required on POST | Notes |
|-------|------|-----------|-----------------|-------|
| `name` | string | **150** | No | Model `nullable=True` (unnamed/stray animals are realistic). |
| `species` | string | 100 | **Yes** | Model `nullable=False`. |
| `breed` | string | 100 | No | Model `nullable=True`. |
| `age` | integer | — | No | Must be ≥ 0 when provided. Model `nullable=True`. |
| `gender` | string | 20 | No | See §4 Enum table. Model `nullable=True`. |
| `description` | text | 2000 (API limit) | No | DB type is `Text` (unbounded); API enforces 2 000 chars. |
| `location` | string | 255 | No | Model `nullable=True`. |
| `status` | string | 50 | No | Defaults to `"Available"` if omitted. See §4 Enum table. |
| `image_url` | text | 2048 (API limit) | No | Valid absolute URL. DB type is `Text`; API enforces 2 048 chars. |

**Protected fields** (`animal_id`, `ngo_id`, `created_at`) — supplying any → **400**.

**Success (201):** Created animal in `data`.

**Errors:** 400 (validation), 401, 403, 404 (no linked NGO).

### PATCH `/api/animals/<int:animal_id>`

Same mutable fields as POST (all optional, at least one required).

**Ownership:** `animal.ngo_id` must equal `g.current_user.ngo.ngo_id`, otherwise → **403**.

**Errors:** 400, 401, 403, 404 (animal not found).

### DELETE `/api/animals/<int:animal_id>`

**Ownership:** Same as PATCH.

**Success:** **204 No Content** (empty body).

**Errors:** 401, 403, 404.

---

## 4. Rescue Case Endpoints (Batch 2A)

Rescue cases enable authenticated users to report animals in need, and allow verified NGO accounts to review, claim, and advance cases through their rehabilitation lifecycle.

### Endpoint Overview

| Method | URL | Auth & Authorization | Allowed Roles | Description |
|--------|-----|----------------------|--------------|-------------|
| POST | `/api/rescue-cases` | `@cognito_required(require_pawconnect_user=True)` | Any authenticated role (`User`, `NGO`, `Rescuer`, `Volunteer`, `Donor`, `Admin`) | Report a new animal in need. |
| GET | `/api/rescue-cases` | `@cognito_required(require_pawconnect_user=True)` | Role-filtered | List rescue cases with pagination and visibility restrictions. |
| GET | `/api/rescue-cases/<int:case_id>` | `@cognito_required(require_pawconnect_user=True)` | Reporter or Verified NGO | View details of a specific rescue case. |
| PATCH | `/api/rescue-cases/<int:case_id>` | `@cognito_required(require_pawconnect_user=True)` | Reporter (if `Reported`) or Assigned NGO | Update situation details (`animal_type`, `condition`, `location`, `description`, `urgency`, `image_url`). |
| POST | `/api/rescue-cases/<int:case_id>/assign` | `@roles_required(RoleName.NGO)` | `NGO` with linked NGO profile | Claim an unassigned rescue case for the caller's NGO. |
| PATCH | `/api/rescue-cases/<int:case_id>/status` | `@roles_required(RoleName.NGO)` | Assigned NGO only | Update case status following the formal lifecycle transition table. |

> **Authentication & Authorization Decorator Pipeline Note:**
> - `@cognito_required(require_pawconnect_user=True)` validates the Cognito JWT (401 on missing/expired/invalid token, 503 on Cognito config error) and verifies that a local PostgreSQL `User` record exists (403 if unlinked). It populates `g.cognito_claims`, `g.cognito_sub`, and `g.current_user`.
> - `@roles_required(*allowed_roles)` internally executes the exact same authentication and local user checks as `cognito_required`, and additionally verifies that `g.current_user.role.role_name` matches one of the specified roles (403 if wrong role). Therefore, applying `@roles_required` alone is fully sufficient to enforce both authentication and role verification.

---

### 4.1 POST `/api/rescue-cases` (Report Animal in Need)

**Authentication & Role:** `@cognito_required(require_pawconnect_user=True)`. Any authenticated user with a local profile may report a case.

**Server-managed identity:** `reported_by` is set server-side strictly from `g.current_user.user_id`. Clients cannot specify or override this field.

**Initial status & assignment:** `status` is set automatically to `"Reported"`. `assigned_ngo` is set to `null`.

**Request body:**

| Field | Type | Max Length | Required | Notes |
|-------|------|-----------|----------|-------|
| `location` | string | 255 | **Yes** | Non-empty string. Model column is `nullable=False`. |
| `animal_type` | string | 100 | No | General type (e.g., "Dog", "Cat", "Bird", "Cow"). |
| `condition` | text | 2000 (API limit) | No | Observed injuries, physical state. |
| `description` | text | 2000 (API limit) | No | Narrative context or details. |
| `urgency` | string | 50 | No | Allowed values: `"Low"`, `"Medium"`, `"High"`, `"Critical"`. |
| `image_url` | text | 2048 (API limit) | No | Valid absolute HTTP/HTTPS URL. |

**Protected fields:** Supplying any of `case_id`, `reported_by`, `assigned_ngo`, `status`, `created_at`, `updated_at` returns **400 Bad Request** (`"Unknown or protected fields: ..."`).

**Success (201 Created):**
```json
{
  "status": "success",
  "data": {
    "case_id": 1,
    "reported_by": 5,
    "assigned_ngo": null,
    "animal_type": "Dog",
    "condition": "Severe limp, hit by vehicle",
    "location": "Near City Center Bus Stand, MG Road",
    "description": "Limping puppy hiding near shopfront",
    "urgency": "High",
    "image_url": "https://s3.amazonaws.com/pawconnect/cases/c1.jpg",
    "status": "Reported",
    "created_at": "2026-10-11T20:00:00Z",
    "updated_at": "2026-10-11T20:00:00Z"
  }
}
```

**Errors:**
- 400: Validation error, missing required `location`, empty/whitespace `location`, or protected fields supplied.
- 401: Missing, malformed, or expired Cognito token.
- 403: No registered local PawConnect user record.
- 503: Cognito configuration error.

---

### 4.2 GET `/api/rescue-cases` (List Rescue Cases)

**Authentication:** `@cognito_required(require_pawconnect_user=True)`.

**Visibility & Filtering Rules (Server-Enforced):**
- **NGO user (`RoleName.NGO`) with linked NGO profile:** Can view all unassigned cases (`assigned_ngo IS NULL`) plus cases assigned to their own NGO (`assigned_ngo == g.current_user.ngo.ngo_id`).
- **NGO user without linked NGO profile:** Returns **404 Not Found** with `"No NGO profile found for this user."`.
- **All other authenticated users (`User`, `Rescuer`, `Volunteer`, `Donor`, `Admin`):** Can view **only** cases that they personally reported (`reported_by == g.current_user.user_id`).
- **Unauthenticated callers:** Return **401 Unauthorized**.

**Query parameters:**

| Param | Type | Default | Max | Notes |
|-------|------|---------|-----|-------|
| `page` | int | 1 | — | Must be ≥ 1. |
| `per_page` | int | 20 | 100 | Must be between 1 and 100. |
| `status` | string | — | — | Optional filter. Must be an exact canonical status string. |
| `assigned` | string | — | — | Optional filter for NGOs: `"me"` (own assigned cases) or `"unassigned"` (unassigned cases). |

**Success (200 OK):**
```json
{
  "status": "success",
  "data": {
    "items": [
      {
        "case_id": 1,
        "reported_by": 5,
        "assigned_ngo": 2,
        "animal_type": "Dog",
        "condition": "Fractured leg",
        "location": "Koramangala 4th Block",
        "description": "In shelter receiving first aid",
        "urgency": "High",
        "image_url": "https://s3.amazonaws.com/pawconnect/cases/c1.jpg",
        "status": "Under Treatment / Foster",
        "created_at": "2026-10-11T18:00:00Z",
        "updated_at": "2026-10-11T19:30:00Z"
      }
    ],
    "page": 1,
    "per_page": 20,
    "total": 1
  }
}
```

**Errors:** 400 (invalid pagination params or invalid status filter), 401, 403, 404 (NGO user lacking NGO profile), 503.

---

### 4.3 GET `/api/rescue-cases/<int:case_id>` (Get Case Details)

**Authentication:** `@cognito_required(require_pawconnect_user=True)`.

**Visibility & Ownership Check:**
- If the case does not exist in the database → **404 Not Found** (`"Rescue case not found."`).
- A user is permitted to view the case if:
  1. The user is the reporter (`case.reported_by == g.current_user.user_id`), OR
  2. The user has role `NGO`, has a linked NGO profile, and either:
     - The case is unassigned (`case.assigned_ngo IS NULL`), OR
     - The case is assigned to their NGO (`case.assigned_ngo == g.current_user.ngo.ngo_id`).
- In all other cases (e.g. attempting to guess IDs of other users' cases or cases assigned to other NGOs) → **403 Forbidden** (`"You do not have permission to view this rescue case."`).

**Success (200 OK):** Returns single case object in envelope `data`.

**Errors:** 401, 403, 404, 503.

---

### 4.4 PATCH `/api/rescue-cases/<int:case_id>` (Update Case Details)

**Authentication:** `@cognito_required(require_pawconnect_user=True)`.

**Authorization & Scope of Edit:**
- If case not found → **404 Not Found**.
- **Reporter edit condition:** Permitted **only** if `case.reported_by == g.current_user.user_id` AND `case.status == "Reported"`. If status has advanced past `"Reported"` (e.g. under review or claimed by an NGO), the reporter is rejected with **403 Forbidden** (`"Case details can only be edited by the reporter while status is 'Reported'."`).
- **Assigned NGO edit condition:** Permitted if caller has role `NGO`, has a linked NGO profile, and `case.assigned_ngo == g.current_user.ngo.ngo_id`.
- Any other caller → **403 Forbidden** (`"You do not have permission to modify this rescue case."`).

**Request body:** JSON object with at least one mutable field:
`animal_type` (max 100), `condition` (max 2000), `description` (max 2000), `location` (max 255), `urgency` (max 50), `image_url` (max 2048).

**Protected fields:** Supplying any of `case_id`, `reported_by`, `assigned_ngo`, `status`, `created_at`, `updated_at` returns **400 Bad Request**.

**Success (200 OK):** Returns updated case in `data`.

**Errors:** 400 (validation, empty payload, protected fields), 401, 403, 404, 503.

---

### 4.5 POST `/api/rescue-cases/<int:case_id>/assign` (Claim / Assign Case to NGO)

**Authentication & Role:** `@roles_required(RoleName.NGO)`.

**Preconditions & Checks:**
1. Authenticated user must have role `NGO` (enforced by `@roles_required(RoleName.NGO)` → 403 if not).
2. The user must have an active linked NGO profile in PostgreSQL (`g.current_user.ngo`). If missing → **404 Not Found** with `"No NGO profile found for this user."`.
3. The case must exist → **404 Not Found** with `"Rescue case not found."`.
4. The case must currently be unassigned (`case.assigned_ngo IS NULL`).
   - If `case.assigned_ngo` is already set to another NGO → **409 Conflict** with `"Case is already assigned to another NGO."`.
   - If `case.assigned_ngo` is already set to caller's own NGO → **200 OK** (idempotent).
5. When claimed, `case.assigned_ngo` is set to `g.current_user.ngo.ngo_id`, and `case.status` transitions automatically to `"NGO Assigned"`.
6. Client-provided NGO IDs or status values in the request body are strictly rejected (**400 Bad Request** if protected fields supplied). Body should be `{}` or empty.

**Success (200 OK):**
```json
{
  "status": "success",
  "message": "Rescue case successfully assigned to NGO.",
  "data": {
    "case_id": 1,
    "assigned_ngo": 2,
    "status": "NGO Assigned",
    "updated_at": "..."
  }
}
```

**Errors:** 400 (protected fields in payload), 401, 403 (wrong role), 404 (missing NGO profile or case not found), 409 (already assigned to different NGO), 503.

---

### 4.6 PATCH `/api/rescue-cases/<int:case_id>/status` (Update Case Status)

**Authentication & Role:** `@roles_required(RoleName.NGO)`.

*(Note: In Batch 2A, status updates are restricted to the assigned NGO. Rescuers cannot change case status in this batch because the database schema links cases exclusively to NGOs via `assigned_ngo`.)*

**Preconditions & Checks:**
1. User must have role `NGO` (403 if not).
2. User must have a linked NGO profile (`g.current_user.ngo`; 404 if not).
3. Case must exist (404 if not).
4. Ownership check: Case must be assigned to caller's NGO (`case.assigned_ngo == g.current_user.ngo.ngo_id`). If unassigned or assigned to another NGO → **403 Forbidden** (`"You do not have permission to modify status for this rescue case."`).
5. `status` field in request JSON is **required**. Must be one of the exact canonical strings in the vocabulary.
6. The transition must be a valid step according to the Transition Table (§5.2). If invalid → **400 Bad Request** (`"Invalid status transition from '<current>' to '<new>'."`).

**Request body:**
```json
{
  "status": "Rescued"
}
```

**Success (200 OK):** Returns updated case with new `status` and `updated_at`.

**Errors:** 400 (missing status, unknown status string, or invalid transition), 401, 403 (wrong role or case not assigned to caller's NGO), 404 (case or NGO profile not found), 503.

---

## 5. Enum Definitions & Transition Table

### 5.1 Animal `gender`

| Canonical value (stored) | Notes |
|-------------------------|-------|
| `Male` | |
| `Female` | |
| `Other` | |

Input is **case‑sensitive** and must match exactly. The model column is `String(20)`.

### 5.2 Animal `status`

| Canonical value (stored) | Notes |
|-------------------------|-------|
| `Available` | Default when omitted on POST. |
| `Adopted` | |
| `Under Treatment` | |
| `Foster` | |

These values match the model source comment (`animal.py` line 57). Input is **case‑sensitive**. The model column is `String(50)`.

### 5.3 Rescue Case `status` Canonical Vocabulary

Every case status is stored as a single, exact string without slash-separated alternatives:

| # | Exact Canonical Value | Origin & Meaning |
|---|----------------------|------------------|
| 1 | `Reported` | Initial default status set by model on creation. Case is awaiting review. |
| 2 | `Under Review` | NGO is reviewing situation details prior to committing response. |
| 3 | `NGO Assigned` | An NGO has claimed and accepted responsibility for the rescue. |
| 4 | `Rescued` | Animal has been safely secured and extracted from the field. |
| 5 | `Under Treatment / Foster` | Animal is receiving veterinary medical care or temporary foster boarding. |
| 6 | `Adoption Available` | Animal has recovered and is ready to enter the public adoption catalog. |
| 7 | `Adopted / Resolved` | Terminal state: animal adopted, reunited, or case closed. |

> **Distinction note:** The model column is `String(50)` with default `"Reported"`. The model does not enforce these statuses via a database CHECK constraint; enforcement is executed strictly by the API service validation layer.

### 5.4 Rescue Case Status Transition Table

Every permitted lifecycle step is explicitly defined below. Any transition not listed in this table is rejected with **400 Bad Request**.

| Current Status | Requested Status | Authorized Actor | Required Ownership / Precondition | Result |
|---|---|---|---|---|
| `Reported` | `Under Review` | NGO | Case unassigned (`assigned_ngo IS NULL`) or assigned to caller's NGO | **Permitted** (200 OK) |
| `Reported` | `NGO Assigned` | NGO | Via `POST /api/rescue-cases/<id>/assign` | **Permitted** (200 OK, sets `assigned_ngo`) |
| `Under Review` | `NGO Assigned` | NGO | Via `POST /api/rescue-cases/<id>/assign` | **Permitted** (200 OK, sets `assigned_ngo`) |
| `NGO Assigned` | `Rescued` | Assigned NGO | `case.assigned_ngo == current_user.ngo.ngo_id` | **Permitted** (200 OK) |
| `Rescued` | `Under Treatment / Foster` | Assigned NGO | `case.assigned_ngo == current_user.ngo.ngo_id` | **Permitted** (200 OK) |
| `Under Treatment / Foster` | `Adoption Available` | Assigned NGO | `case.assigned_ngo == current_user.ngo.ngo_id` | **Permitted** (200 OK) |
| `Under Treatment / Foster` | `Adopted / Resolved` | Assigned NGO | `case.assigned_ngo == current_user.ngo.ngo_id` (direct resolution e.g. reunited/sanctuary) | **Permitted** (200 OK) |
| `Adoption Available` | `Adopted / Resolved` | Assigned NGO | `case.assigned_ngo == current_user.ngo.ngo_id` | **Permitted** (200 OK) |
| *Any status* | *Same status* | Assigned NGO | `case.assigned_ngo == current_user.ngo.ngo_id` | **Idempotent** (200 OK) |
| *Any status* | *Any other transition* | Any user | Any condition | **Rejected: 400 Bad Request** (`"Invalid status transition"`) |

### 5.5 Rescue Case `urgency`

| Canonical value (stored) | Notes |
|-------------------------|-------|
| `Low` | Minor concern, non-life-threatening. |
| `Medium` | Needs attention soon. |
| `High` | Serious injury or imminent danger. |
| `Critical` | Immediate emergency rescue required. |

Input is case-sensitive. Model column is `String(50)`.

---

## 6. Field Length Reference (from actual models)

| Model | Field | DB Type | Max Length | Notes |
|-------|-------|---------|-----------|-------|
| User | `name` | `String(100)` | 100 | Required, non-empty |
| User | `email` | `String(255)` | 255 | Protected / read-only |
| User | `phone` | `String(20)` | 20 | Optional |
| User | `location` | `String(255)` | 255 | Optional |
| User | `auth_id` | `String(255)` | 255 | Protected / read-only |
| NGO | `name` | `String(255)` | 255 | Required, non-empty |
| NGO | `description` | `Text` | 2000 (API limit) | DB type is unbounded `Text`; API enforces 2,000 chars |
| NGO | `location` | `String(255)` | 255 | Optional |
| NGO | `contact` | `String(255)` | 255 | Optional |
| NGO | `verification_status` | `String(50)` | 50 | Protected / read-only |
| Animal | `name` | `String(150)` | 150 | Optional |
| Animal | `species` | `String(100)` | 100 | Required, non-empty |
| Animal | `breed` | `String(100)` | 100 | Optional |
| Animal | `gender` | `String(20)` | 20 | Enum ("Male", "Female", "Other") |
| Animal | `description` | `Text` | 2000 (API limit) | DB type is unbounded `Text`; API enforces 2,000 chars |
| Animal | `location` | `String(255)` | 255 | Optional |
| Animal | `status` | `String(50)` | 50 | Enum ("Available", "Adopted", "Under Treatment", "Foster") |
| Animal | `image_url` | `Text` | 2048 (API limit) | DB type is unbounded `Text`; API enforces 2,048 chars |
| RescueCase | `location` | `String(255)` | 255 | **Required**, non-empty |
| RescueCase | `animal_type` | `String(100)` | 100 | Optional |
| RescueCase | `condition` | `Text` | 2000 (API limit) | DB type is unbounded `Text`; API enforces 2,000 chars |
| RescueCase | `description` | `Text` | 2000 (API limit) | DB type is unbounded `Text`; API enforces 2,000 chars |
| RescueCase | `urgency` | `String(50)` | 50 | Enum ("Low", "Medium", "High", "Critical") |
| RescueCase | `status` | `String(50)` | 50 | Server-managed lifecycle status |
| RescueCase | `image_url` | `Text` | 2048 (API limit) | DB type is unbounded `Text`; API enforces 2,048 chars |

---

## 7. Validation & Pagination Conventions

* **String length limits**: String columns strictly follow the DB column definitions listed in §6. For unbounded database `Text` columns (`description` on NGO/Animal/RescueCase, `condition` on RescueCase, `image_url` on Animal/RescueCase), the API validates and enforces explicit API-level limits (2,000 characters for text narrative fields, 2,048 characters for `image_url`). Exceeding any limit returns 400 with a validation error.
* **Enums**: Case-sensitive and must match exactly the canonical values defined in §5. Input values not in the allowed canonical lists return 400.
* **Unknown / Protected fields**: Supplying unknown or protected fields (e.g., `user_id`, `ngo_id`, `verification_status`, `case_id`, `reported_by`, `assigned_ngo`, `created_at`, `updated_at`) in request payloads causes 400.
* **Pagination**: `page` ≥ 1 (default 1), `per_page` default 20, maximum 100. Invalid or negative values return 400.
* **Partial updates (PATCH)**: At least one valid mutable field must be provided; empty JSON object `{}` returns 400.

---

## 8. Error Response Details

### Existing decorator errors (no code changes needed)

These are produced by `cognito_required` and `roles_required` as they exist today:

| Condition | HTTP Status | Response body |
|-----------|-------------|---------------|
| Missing `Authorization` header | 401 | `{"status":"error","message":"Authorization header is required."}` |
| Malformed `Authorization` header | 401 | `{"status":"error","message":"Invalid Authorization header format. Expected 'Bearer <token>'."}` |
| Expired token | 401 | `{"status":"error","message":"Authentication token has expired."}` |
| Invalid token | 401 | `{"status":"error","message":"Authentication failed: <reason>"}` |
| Cognito config error | 503 | `{"status":"error","message":"Authentication service configuration error: <reason>"}` |
| Valid JWT, no PawConnect user | 403 | `{"status":"error","message":"No registered PawConnect profile found for this authenticated user."}` |
| Wrong role | 403 | `{"status":"error","message":"You do not have permission to access this resource."}` |

### Proposed endpoint-level errors

| Condition | HTTP Status | Example response |
|-----------|-------------|-----------------|
| Validation failure (bad field value/length) | 400 | `{"status":"error","message":"Validation failed.","details":{"location":"Location is required."}}` |
| Unknown/protected fields supplied | 400 | `{"status":"error","message":"Unknown or protected fields: reported_by, status"}` |
| Empty PATCH payload | 400 | `{"status":"error","message":"At least one mutable field is required."}` |
| Invalid status transition | 400 | `{"status":"error","message":"Invalid status transition from 'Reported' to 'Adopted/Resolved'."}` |
| NGO already exists for user | 409 | `{"status":"error","message":"An NGO profile already exists for this user."}` |
| Case already assigned to another NGO | 409 | `{"status":"error","message":"Case is already assigned to another NGO."}` |
| NGO not linked to user | 404 | `{"status":"error","message":"No NGO profile found for this user."}` |
| Resource not found (animal / rescue case) | 404 | `{"status":"error","message":"Rescue case not found."}` |
| Resource owned/assigned to another entity | 403 | `{"status":"error","message":"You do not have permission to modify this rescue case."}` |

---

## 9. HTTP Status Summary

| Code | Meaning |
|------|---------|
| 200 | Success (GET, PATCH, POST assignment) |
| 201 | Resource created (POST) |
| 204 | Success with no body (DELETE) |
| 400 | Bad request — validation, unknown/protected fields, missing required fields, illegal state transitions |
| 401 | Unauthorized — missing/invalid/expired token |
| 403 | Forbidden — no PawConnect profile, wrong role, or insufficient ownership/permissions |
| 404 | Not found — resource does not exist (animal, NGO profile, rescue case) |
| 409 | Conflict — duplicate resource or already claimed/assigned case |
| 503 | Service unavailable — authentication service configuration error |

---

## 10. Approved Decisions & Scope for Batch 2A

### Confirmed Batch Decisions
1. **Reporting identity**: `reported_by` is strictly set from `g.current_user.user_id` server-side; client cannot specify or spoof the reporter (`400 Bad Request` if passed).
2. **Mandatory location**: `location` is strictly required on case creation (`RescueCase.location` is `nullable=False`).
3. **Initial status**: Cases start with status `"Reported"` and `assigned_ngo=None`.
4. **NGO Assignment & Profile Precondition**:
   - Only authenticated users with role `NGO` having an existing linked `NGO` profile (`g.current_user.ngo`) can claim unassigned cases.
   - If an NGO-role user does not have an NGO profile, the assignment endpoint returns **404 Not Found** with `"No NGO profile found for this user."`.
   - Re-claiming a case assigned to another NGO returns **409 Conflict** (`"Case is already assigned to another NGO."`).
5. **Rescuer role exclusion in Batch 2A**:
   - Because the database foreign key `assigned_ngo` references `ngos.ngo_id` (`db.ForeignKey("ngos.ngo_id")`), there is no database relationship supporting individual rescuer assignment.
   - Individual rescuers cannot claim cases or update case status in this batch.
6. **No reassignment or release**:
   - No unassignment or release endpoint is introduced in this batch.
7. **Reporter edit window**:
   - The original reporter may edit case details **only** while the status is `"Reported"`. Once an NGO claims or reviews the case, reporter edits are locked (`403 Forbidden`).
8. **Assigned NGO status & details management**:
   - An assigned NGO can update details and status **only** for cases assigned to its own NGO profile (`case.assigned_ngo == g.current_user.ngo.ngo_id`).
9. **No Admin override**:
   - No Admin-specific override endpoints or bypasses are added in this batch.
10. **Strict server-managed fields**:
   - `case_id`, `reported_by`, `assigned_ngo`, `status`, `created_at`, `updated_at` are rejected on creation and detail updates (`400 Bad Request`).
11. **Text limits**:
   - `condition` and `description`: max 2,000 characters.
   - `image_url`: max 2,048 characters + HTTP/HTTPS URL validation.

### Decisions Requiring Product Owner Approval
- **None remaining for Batch 2A**: All rules, transitions, error responses, and authorization checks have been defined using approved defaults and existing database schema constraints.

---

*Updated 2026‑10‑11. Batch 1 is implemented and verified; Batch 2A (Rescue Cases) contract specification finalized and audited. No Python code, models, migrations, or tests were changed.*