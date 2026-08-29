# Design Document: FlyRank Embeddable Widget & Lead-Capture Platform

## 1. Problem Statement
Businesses need lightweight, embeddable lead-capture widgets (contact forms, popovers, newsletter signups) installed via a single `<script>` snippet. Because these widgets execute on external websites, the backend API must accept untrusted, cross-origin HTTP submissions from unconstrained browsers while enforcing strict CORS policies, rate limiting, anti-spam validation, and asynchronous geo-enrichment without failing main execution paths.

## 2. Core Non-Goals
* NO complex drag-and-drop frontend form builder (the frontend is minimal vanilla JS; evaluation focuses strictly on backend engineering).
* NO paid CDN or custom domain routing (the customer site is served from a secondary local origin/port).
* NO real third-party email delivery dependency (emails log via local Mailpit / console logger).

## 3. Data Model & Tenant Isolation (PostgreSQL Schema)
* Tenants (Owners) -> 1:N -> Widgets -> 1:N -> Submissions.
* Tenant isolation is strictly enforced at the database query layer (`WHERE widget.tenant_id = :current_tenant_id`).

## 4. API Surface & Architecture Summary
* **Path 1 (Tenant Admin API):** Authenticated CRUD for widgets and aggregate analytics dashboard.
* **Path 2 (Public CDN & Delivery):** Public GET routes for static `widget.js` bundle and short-cached widget JSON configs.
* **Path 3 (Public Ingestion Endpoint):** Hardened, CORS-enabled `POST /api/v1/public/widgets/{id}/submit` endpoint with rate-limiting, honeypot spam checks, and provider fallback geolocation enrichment.
