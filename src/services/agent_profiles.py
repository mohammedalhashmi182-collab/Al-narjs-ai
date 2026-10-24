"""Al-Narjis runtime capability profiles for specialist agents.

This is production runtime policy. Development-only GSK skills are deliberately
not treated as agent capabilities unless an equivalent runtime tool is wired.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

COMMON_SKILLS = (
    "requirement_extraction", "critical_reasoning", "assumption_control",
    "source_discipline", "saudi_business_context", "actionable_delivery",
)
CATEGORY_SKILLS = {
    "analysis": ("research_design", "evidence_synthesis", "uncertainty_calibration", "quantitative_reasoning"),
    "marketing": ("customer_psychology", "positioning", "conversion_copy", "offer_clarity"),
    "content": ("editorial_structure", "audience_fit", "fact_preservation", "native_arabic"),
    "automation": ("systems_thinking", "failure_analysis", "test_design", "safe_execution"),
    "support": ("intent_detection", "grounded_answering", "de_escalation", "handoff_judgement"),
    "general": ("problem_decomposition", "decision_support", "clear_communication"),
}
AGENT_SKILLS = {
    "market_analyst": ("market_research", "tam_sam_som", "trend_analysis", "source_triage"),
    "competitor_analyst": ("competitive_intelligence", "benchmarking", "positioning_map", "claim_verification"),
    "data_analyst": ("data_quality", "descriptive_statistics", "anomaly_detection", "unit_checks"),
    "search_discovery": ("search_strategy", "query_expansion", "source_ranking", "citation_hygiene"),
    "business_ideas": ("opportunity_discovery", "feasibility_screening", "business_modeling", "risk_mapping"),
    "finance_pricing": ("unit_economics", "pricing_strategy", "margin_analysis", "scenario_modeling", "arithmetic_verification"),
    "legal_privacy": ("saudi_pdpl", "contract_risk_triage", "regulatory_source_check", "legal_uncertainty_escalation"),
    "security_compliance": ("threat_modeling", "secure_defaults", "privacy_by_design", "control_verification"),
    "software_engineer": ("python_engineering", "web_architecture", "debugging", "testing", "secure_coding"),
    "integrations_engineer": ("api_design", "oauth", "webhooks", "idempotency", "integration_debugging"),
    "qa_engineer": ("regression_testing", "edge_case_design", "acceptance_testing", "failure_reproduction"),
    "quality_gate": ("factuality_review", "completeness_review", "consistency_check", "source_audit"),
    "sales_closer": ("consultative_selling", "objection_handling", "value_framing", "policy_safe_closing"),
    "lead_acquisition": ("lead_qualification", "account_research", "personalization", "outreach_strategy"),
    "marketing_agent": ("go_to_market", "campaign_strategy", "channel_selection", "measurement_plan"),
    "social_media": ("platform_native_copy", "hook_design", "content_calendar", "brand_consistency"),
    "customer_service": ("knowledge_grounding", "case_triage", "policy_compliance", "handoff_control"),
    "customer_manager": ("account_context", "retention_signals", "customer_health", "next_best_action"),
    "store_manager": ("ecommerce_operations", "catalog_analysis", "order_insights", "conversion_friction"),
    "product_describer": ("product_positioning", "benefit_translation", "catalog_consistency", "conversion_copy"),
    "content_writer": ("long_form_writing", "research_synthesis", "seo_structure", "editorial_quality"),\n    "content_ideas": ("creative_strategy", "trend_translation", "content_pillars", "idea_prioritization"),\n    "email_writer": ("business_email", "subject_line_design", "cta_clarity", "tone_control"),\n    "cv_writer": ("resume_strategy", "ats_structure", "achievement_framing", "career_positioning"),\n    "text_improver": ("editing", "clarity", "tone_alignment", "meaning_preservation"),
    "article_writer": ("article_research", "narrative_structure", "fact_checking", "source_attribution"),
    "content_manager": ("content_strategy", "editorial_planning", "distribution", "performance_review"),
    "ad_writer": ("direct_response_copy", "hook_testing", "cta_design", "policy_safe_claims"),
    "localization": ("transcreation", "saudi_localization", "terminology_control", "cultural_review"),
    "project_manager": ("scope_control", "dependency_mapping", "milestone_planning", "risk_tracking"),
    "time_manager": ("prioritization", "capacity_planning", "schedule_design", "execution_rhythm"),
    "product_designer": ("ux_reasoning", "information_architecture", "interaction_design", "accessibility"),
    "prototype_engineer": ("rapid_prototyping", "technical_feasibility", "integration_planning", "testability"),
    "policy_guardian": ("policy_interpretation", "approval_boundaries", "risk_escalation", "auditability"),
    "orchestrator": ("executive_synthesis", "delegation", "cross_agent_coordination", "decision_quality"),
}
TOOL_AGENTS = {
    "web_search": frozenset({
        "market_analyst", "competitor_analyst", "data_analyst", "search_discovery",
        "business_ideas", "finance_pricing", "legal_privacy", "security_compliance",
        "marketing_agent", "lead_acquisition", "content_writer", "article_writer",
        "social_media", "software_engineer", "integrations_engineer",
    }),
    "data_files": frozenset({"data_analyst", "finance_pricing", "market_analyst", "competitor_analyst"}),
    "store": frozenset({"store_manager", "product_describer", "marketing_agent", "data_analyst"}),
    "knowledge_base": frozenset({
        "customer_service", "customer_manager", "sales_closer", "lead_acquisition",
        "marketing_agent", "social_media", "content_writer", "article_writer",
        "content_manager", "ad_writer", "email_writer", "market_analyst", "competitor_analyst",
        "data_analyst", "finance_pricing", "legal_privacy", "security_compliance",
        "software_engineer", "integrations_engineer", "store_manager",
        "product_describer", "project_manager", "business_ideas",
    }),
}
STRICT_EVIDENCE_AGENTS = frozenset({
    "market_analyst", "competitor_analyst", "data_analyst", "search_discovery",
    "finance_pricing", "legal_privacy", "security_compliance",
})
CREATIVE_AGENTS = frozenset({
    "ad_writer", "content_ideas", "social_media", "content_writer", "article_writer", "product_describer",
})


@dataclass(frozen=True)
class AgentRuntimeProfile:
    slug: str
    skills: tuple[str, ...]
    tools: tuple[str, ...]
    evidence_mode: str
    quality_gate: bool
    temperature_cap: float
    min_tokens: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "skills": list(self.skills), "tools": list(self.tools),
            "evidence_mode": self.evidence_mode, "quality_gate": self.quality_gate,
            "temperature_cap": self.temperature_cap, "min_tokens": self.min_tokens,
        }


def profile_for(slug: str, category: str | None = None) -> AgentRuntimeProfile:
    category = (category or "general").lower()
    skills = tuple(dict.fromkeys(
        COMMON_SKILLS + CATEGORY_SKILLS.get(category, CATEGORY_SKILLS["general"]) + AGENT_SKILLS.get(slug, ())
    ))
    tools = tuple(name for name, agents in TOOL_AGENTS.items() if slug in agents)
    evidence_mode = "strict" if slug in STRICT_EVIDENCE_AGENTS else (
        "creative" if slug in CREATIVE_AGENTS else "grounded"
    )
    return AgentRuntimeProfile(
        slug=slug,
        skills=skills,
        tools=tools,
        evidence_mode=evidence_mode,
        quality_gate=slug != "quality_gate",
        temperature_cap=0.35 if evidence_mode == "strict" else (0.65 if evidence_mode == "creative" else 0.5),
        min_tokens=2400 if evidence_mode == "strict" else 2200,
    )


def system_block(slug: str, category: str | None = None, *, locale: str = "ar",
                 client_name: str = "", has_evidence: bool = False) -> str:
    p = profile_for(slug, category)
    language = "Arabic" if locale.startswith("ar") else "English"
    evidence = (
        "STRICT EVIDENCE MODE: every current/external claim must be traceable to supplied evidence. "
        "Separate facts, calculations, assumptions and recommendations."
        if p.evidence_mode == "strict"
        else "Ground recommendations in supplied evidence and clearly label assumptions."
    )
    return (
        "\n\n=== AL-NARJIS RUNTIME CONTRACT ===\n"
        "You are an Al-Narjis AI specialist. Never mention or inherit another project identity.\n"
        f"Agent: {slug}. Client: {client_name or 'current tenant'}. Output language: {language}.\n"
        "Active skills: " + ", ".join(p.skills) + ".\n"
        "Allowed runtime tools: " + (", ".join(p.tools) if p.tools else "none") + ".\n"
        "For laws, statistics, competitors, prices, dates, URLs and other external facts, use only client input "
        "or the runtime evidence supplied with this task. Never invent citations, metrics, customer facts or results.\n"
        + evidence + "\n"
        "Do the complete job. Check arithmetic, names, dates, units and contradictions. "
        "If information is missing, state the assumption or limitation. Never claim an action was executed without proof.\n"
        + ("Runtime evidence is attached." if has_evidence else "No runtime evidence was attached.")
        + "\n=== END AL-NARJIS RUNTIME CONTRACT ==="
    )
