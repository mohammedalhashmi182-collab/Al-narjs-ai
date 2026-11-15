"""Public OpenAPI document for /openapi.json, /docs, and /redoc.

The document is an allow-list. Admin, owner, webhook, payment-test, and
other internal routes are not added here, and ``build_spec`` refuses a path
that matches the denylist. No credential values are embedded.
"""

from __future__ import annotations

from typing import Any

from src.version import __version__

# Substrings that must never appear in a published path.
DENIED_PARTS = (
    "/api/owner",
    "/webhooks",
    "/health/deep",
    "/payment/",
    "moyasar-live-test",
    "/api/email",
    "/api/acquisition",
    "/api/company",
    "/api/governance",
    "/api/queue",
    "/api/schedules",
    "/api/executions",
    "/api/workflows",
    "/api/tasks",
    "/api/opportunities",
    "/api/decisions",
    "/api/experiments",
    "/api/ceo/run",
    "/api/agents/{slug}/run",
    "/api/events",
    "/api/pulse",
)


def _op(
    *,
    tag: str,
    summary: str,
    description: str,
    security: list[dict[str, list[str]]] | None = None,
    parameters: list[dict[str, Any]] | None = None,
    body: dict[str, Any] | None = None,
    example: dict[str, Any] | None = None,
    responses: dict[str, Any] | None = None,
) -> dict[str, Any]:
    operation: dict[str, Any] = {
        "tags": [tag],
        "summary": summary,
        "description": description,
        "responses": responses or {
            "200": {"description": "Success."},
        },
    }
    if security is not None:
        operation["security"] = security
    if parameters:
        operation["parameters"] = parameters
    if body is not None:
        operation["requestBody"] = {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {"type": "object"},
                    "example": body,
                }
            },
        }
    if example is not None:
        operation["responses"]["200"] = {
            "description": operation["responses"]["200"]["description"],
            "content": {"application/json": {"example": example}},
        }
    return operation


_SESSION: list[dict[str, list[str]]] = [{"portalSession": []}]


def build_spec() -> dict[str, Any]:
    """Return the public customer API document."""
    paths: dict[str, Any] = {
        "/health": {
            "get": _op(
                tag="Status",
                summary="Process liveness",
                description=(
                    "Cheap liveness check used by the host. A healthy process "
                    "returns status and the public version. This response does "
                    "not include database or provider detail."
                ),
                example={"status": "healthy", "version": __version__},
            ),
        },
        "/api/status": {
            "get": _op(
                tag="Status",
                summary="Public component status",
                description=(
                    "Cached roll-up of the site, /health, the customer portal, "
                    "and the agent registry. Status words are operational, "
                    "degraded, or outage. No credentials, hostnames, or error text."
                ),
                example={
                    "status": "operational",
                    "version": __version__,
                    "checked_at": "2026-11-12T00:00:00+00:00",
                    "components": {
                        "site": {"status": "operational"},
                        "health": {"status": "operational"},
                        "portal": {"status": "operational"},
                        "agents": {"status": "operational", "count": 39},
                    },
                },
            ),
        },
        "/api/agents": {
            "get": _op(
                tag="Catalog",
                summary="Public agent roster",
                description=(
                    "Names, categories, and public introductions for the roster. "
                    "Model identifiers and owner-only fields are omitted unless "
                    "the caller is the owner, and those fields are not part of "
                    "this public contract."
                ),
                parameters=[{
                    "name": "category",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "string"},
                    "description": "Optional category filter, such as support or content.",
                }],
                example={
                    "agents": [{
                        "slug": "customer_service",
                        "name": "Customer service",
                        "category": "support",
                        "title_ar": "خدمة العملاء",
                        "title_en": "Customer service",
                    }],
                },
            ),
        },
        "/api/portal/packages": {
            "get": _op(
                tag="Catalog",
                summary="Subscription plans",
                description=(
                    "The three public plans. price is SAR per month before VAT. "
                    "amount is the same price in halalas. VAT is not charged "
                    "while the operator is not VAT-registered."
                ),
                example={
                    "packages": [{
                        "key": "bidaya",
                        "name": "البداية",
                        "name_en": "Starter",
                        "price": "790",
                        "amount": 79000,
                    }],
                },
            ),
        },
        "/api/portal/packages/{package_key}/demo": {
            "get": _op(
                tag="Catalog",
                summary="Illustrative plan demo",
                description=(
                    "Sample content for a plan key: bidaya, numuw, or sharikat. "
                    "The sample is an illustration, not a customer result."
                ),
                parameters=[{
                    "name": "package_key",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "enum": ["bidaya", "numuw", "sharikat"]},
                }],
                responses={
                    "200": {"description": "Demo content for the plan."},
                    "404": {"description": "Unknown plan key."},
                },
            ),
        },
        "/api/portal/projects": {
            "post": _op(
                tag="Portal",
                summary="Open a customer project",
                description=(
                    "Creates a pending project and sets the portal session cookie. "
                    "package is bidaya, numuw, or sharikat. This is the signup call "
                    "the portal form uses."
                ),
                body={
                    "client_name": "Example Studio",
                    "phone": "0550000000",
                    "email": "owner@example.com",
                    "package": "bidaya",
                    "addons": 0,
                },
                example={
                    "project_id": "00000000-0000-4000-8000-000000000001",
                    "package": "bidaya",
                    "status": "pending",
                    "requires_payment": True,
                },
                responses={
                    "200": {"description": "Project created. The session cookie is set."},
                    "400": {"description": "Unknown package."},
                },
            ),
        },
        "/api/portal/login/request": {
            "post": _op(
                tag="Portal",
                summary="Request a sign-in code",
                description=(
                    "Sends a one-time code when the email or phone matches a project. "
                    "The response is the same when it does not, so the call cannot "
                    "be used to discover accounts. The code itself is never returned."
                ),
                body={"identifier": "owner@example.com"},
                example={"sent": True, "channel": "email", "expires_in": 600},
            ),
        },
        "/api/portal/login/verify": {
            "post": _op(
                tag="Portal",
                summary="Verify a sign-in code",
                description=(
                    "Checks the code and sets the portal session cookie. "
                    "A wrong or expired code is rejected and the code is not echoed."
                ),
                body={"identifier": "owner@example.com", "code": "000000"},
                example={"project_id": "00000000-0000-4000-8000-000000000001"},
                responses={
                    "200": {"description": "Signed in. The session cookie is set."},
                    "401": {"description": "The code is invalid or expired."},
                },
            ),
        },
        "/api/portal/session": {
            "get": _op(
                tag="Portal",
                summary="Current portal session",
                description=(
                    "Who the session cookie belongs to. With probe=1, a visitor "
                    "who is signed out gets authenticated false instead of an error."
                ),
                security=_SESSION,
                parameters=[{
                    "name": "probe",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "boolean"},
                }],
                example={"authenticated": True, "project_id": "00000000-0000-4000-8000-000000000001", "status": "pending"},
            ),
        },
        "/api/portal/logout": {
            "post": _op(
                tag="Portal",
                summary="End the portal session",
                description="Clears the portal session cookie.",
                security=_SESSION,
                example={"ok": True},
            ),
        },
        "/api/portal/projects/{project_id}": {
            "get": _op(
                tag="Portal",
                summary="Read one project",
                description=(
                    "The signed-in customer's project: plan, status, and team. "
                    "Another customer's id is rejected."
                ),
                security=_SESSION,
                parameters=[{
                    "name": "project_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "format": "uuid"},
                }],
                example={
                    "project_id": "00000000-0000-4000-8000-000000000001",
                    "package": "bidaya",
                    "status": "pending",
                    "requires_payment": True,
                },
                responses={
                    "200": {"description": "The project."},
                    "401": {"description": "Portal login required."},
                },
            ),
        },
        "/api/ceo/consult": {
            "post": _op(
                tag="Consultant",
                summary="Ask the AI CEO for a plan",
                description=(
                    "Diagnoses a business goal and recommends a real plan from the "
                    "catalog. No API key is required. The text is not stored as a lead."
                ),
                body={
                    "problem": "Customers ask about orders on WhatsApp and nobody follows up.",
                    "lang": "en",
                },
                example={
                    "plan": {"key": "bidaya", "name_en": "Starter", "price": "790"},
                },
                responses={
                    "200": {"description": "A diagnosis and a recommended plan."},
                    "400": {"description": "The problem is too short."},
                },
            ),
        },
        "/api/support/ticket": {
            "post": _op(
                tag="Support",
                summary="Open a support ticket",
                description=(
                    "Stores a support question and tells the customer the reply window. "
                    "consent must be true. The reference is an id, not a secret."
                ),
                body={
                    "name": "Example Studio",
                    "email": "owner@example.com",
                    "question": "How do I add another agent?",
                    "consent": True,
                    "lang": "en",
                },
                example={"ok": True, "reference": "T-EXAMPLE", "response_time": "within one business day"},
                responses={
                    "200": {"description": "Ticket stored."},
                    "422": {"description": "A required field is missing or consent was not given."},
                },
            ),
        },
        "/api/leads": {
            "post": _op(
                tag="Support",
                summary="Register interest",
                description=(
                    "Public lead form. A phone, when sent, must be a real number. "
                    "The response contains the new lead id only."
                ),
                body={
                    "name": "Example Studio",
                    "phone": "0550000000",
                    "email": "owner@example.com",
                    "message": "I want the Starter plan.",
                    "package": "bidaya",
                },
                example={
                    "success": True,
                    "lead_id": "00000000-0000-4000-8000-000000000002",
                    "email_queued": True,
                },
            ),
        },
        "/api/payments/capabilities": {
            "get": _op(
                tag="Payments",
                summary="Which payment methods can take money",
                description=(
                    "Booleans and public labels only. Card checkout is Moyasar "
                    "(mada, Visa, Mastercard). No key, bank account, or webhook "
                    "value is included."
                ),
                example={
                    "card": False,
                    "paypal": False,
                    "moyasar_status": "unavailable",
                    "methods": {"mada": False, "creditcard": False, "stcpay": False, "paypal": False},
                },
            ),
        },
        "/api/payments": {
            "post": _op(
                tag="Payments",
                summary="Start a card payment",
                description=(
                    "Starts a guest card payment. method is mada, creditcard, or "
                    "stcpay. refund_consent must be true. amount in the response "
                    "is halalas (790 SAR is 79000). The reply may include a "
                    "checkout URL. It never includes the Moyasar secret key."
                ),
                body={
                    "package": "bidaya",
                    "method": "creditcard",
                    "customer_name": "Example Studio",
                    "customer_phone": "0550000000",
                    "customer_email": "owner@example.com",
                    "billing_period": "monthly",
                    "refund_consent": True,
                },
                example={
                    "payment_id": "00000000-0000-4000-8000-000000000003",
                    "status": "pending",
                    "gateway": "moyasar",
                    "redirect_url": "https://checkout.moyasar.com/invoices/example",
                    "amount": 79000,
                    "vat": 0,
                    "total": 79000,
                },
                responses={
                    "200": {"description": "Payment started. Send the buyer to redirect_url."},
                    "400": {"description": "The method or the package is not accepted."},
                    "422": {"description": "Refund consent was not given."},
                    "503": {"description": "Card checkout is not open."},
                },
            ),
        },
        "/api/voice/status": {
            "get": _op(
                tag="Voice",
                summary="Voice advisor availability",
                description=(
                    "Whether the public voice advisor can start a call. "
                    "This call does not mint a client credential."
                ),
                example={"ok": False, "reason": "unconfigured", "max_seconds": 180},
            ),
        },
    }
    for path in paths:
        for denied in DENIED_PARTS:
            if denied in path:
                raise RuntimeError(f"refusing to publish {path}")

    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Al-Narjis AI Public API",
            "version": __version__,
            "description": (
                "Customer API for Al-Narjis AI (النرجس), the Arabic-first platform at "
                "https://karmaai.online. Plans are 790, 1,490, and 2,990 SAR per month "
                "before VAT.\n\n"
                "واجهة العميل لمنصة النرجس. الباقات 790 و1490 و2990 ريال شهرياً قبل الضريبة.\n\n"
                "Authentication is the portal session cookie after signup or a one-time "
                "code. This API does not issue API keys. Owner, admin, webhook, and "
                "payment-test routes are not in this document."
            ),
            "contact": {"email": "AlNarjisai@gmail.com", "url": "https://karmaai.online/contact"},
        },
        "servers": [
            {"url": "https://karmaai.online", "description": "Production"},
        ],
        "tags": [
            {"name": "Status", "description": "Liveness and the public status feed."},
            {"name": "Catalog", "description": "Plans and the public agent roster."},
            {"name": "Portal", "description": "Signup and the customer session."},
            {"name": "Consultant", "description": "The public AI CEO diagnosis."},
            {"name": "Support", "description": "Tickets and interest registration."},
            {"name": "Payments", "description": "Moyasar card checkout. Amounts are halalas."},
            {"name": "Voice", "description": "Public voice advisor availability."},
        ],
        "components": {
            "securitySchemes": {
                "portalSession": {
                    "type": "apiKey",
                    "in": "cookie",
                    "name": "narjis_portal",
                    "description": (
                        "HttpOnly session cookie set by POST /api/portal/projects or "
                        "POST /api/portal/login/verify. It is a browser session, not an "
                        "API key. Send it only to karmaai.online."
                    ),
                },
            },
        },
        "paths": paths,
    }
