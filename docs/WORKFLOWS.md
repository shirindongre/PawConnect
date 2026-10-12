
---

# 6. `WORKFLOWS.md`

```md
# PawConnect - Application Workflows

## 1. Purpose

This document describes how major actions move through the PawConnect system.

Workflows connect:

```text
User Action
    ↓
Frontend
    ↓
API
    ↓
Backend Logic
    ↓
Database / Cloud Service
    ↓
Response
    ↓
Frontend

2. User Registration and Authentication
User
  ↓
Registration / Login
  ↓
Amazon Cognito
  ↓
Authentication
  ↓
Token
  ↓
Frontend
  ↓
Protected API Requests
3. Browse Animals
User
  ↓
Animal Listing Page
  ↓
GET /api/animals
  ↓
Flask Backend
  ↓
PostgreSQL
  ↓
Animal Data
  ↓
Frontend
4. Add Animal
NGO
  ↓
Animal Form
  ↓
Frontend
  ↓
POST /api/animals
  ↓
Flask
  ↓
Validate Data
  ↓
Upload Image to S3
  ↓
Store Animal + Image Reference
  ↓
PostgreSQL
5. Report Animal in Need
User
  ↓
Report Animal Form
  ↓
Photo + Location + Condition + Description + Urgency
  ↓
Flask API
  ↓
Validate Request
  ↓
Upload Image to S3
  ↓
Create Rescue Case
  ↓
PostgreSQL
  ↓
NGO / Rescuer Dashboard
6. Rescue Case Management
Reported
   ↓
Under Review
   ↓
NGO Assigned
   ↓
Rescued
   ↓
Under Treatment / Foster
   ↓
Adoption Available
   ↓
Adopted / Resolved

Authorization & Endpoints:
- Case reported via `POST /api/rescue-cases` (any authenticated user; status begins as 'Reported').
- Case reviewed and assigned to NGO via `POST /api/rescue-cases/<id>/assign` (NGO role).
- Case status transitions updated via `PATCH /api/rescue-cases/<id>/status` (Assigned NGO / Rescuer only).
- Non-authorized users cannot modify status or assign cases.

7. Adoption Workflow
User
  ↓
Browse Animals
  ↓
View Animal
  ↓
Apply for Adoption
  ↓
POST /api/adoptions
  ↓
Database
  ↓
NGO Reviews Application
  ↓
Approved / Rejected / Pending
  ↓
Animal Status Updated
8. Image Upload Workflow
User
  ↓
Select Image
  ↓
Frontend
  ↓
Backend
  ↓
Validate File
  ↓
Amazon S3
  ↓
Object Key / URL
  ↓
PostgreSQL
9. Admin Workflow
Administrator
     ↓
Admin Dashboard
     ↓
Authenticated API
     ↓
Role Verification
     ↓
Manage Users / NGOs / Animals / Cases
     ↓
Database
10. Error Workflow
User Request
     ↓
Backend Validation
     |
     +---- Invalid
     |       ↓
     |    Error Response
     |
     +---- Valid
             ↓
        Business Logic
             ↓
        Database / Service
             ↓
          Response