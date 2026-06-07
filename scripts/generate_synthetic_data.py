"""Generate synthetic evaluation scenarios and markdown documentation.

Produces:
  - ``{out}/eval_scenarios.jsonl`` — 50 lines (5 categories × 10)
  - ``{out}/docs/{collection}/*.md`` — 48 files (4 collections × 12)

Usage::

    uv run python -m scripts.generate_synthetic_data --seed 42 --out data/synthetic
"""

# ruff: noqa: E501

import argparse
import json
import sys
from pathlib import Path

from faker import Faker

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CATEGORIES = [
    "Billing",
    "Subscription",
    "Refund",
    "Product",
    "Account Access",
]
SCENARIOS_PER_CATEGORY = 10

COLLECTIONS = [
    "documentation",
    "policies",
    "knowledge_articles",
    "troubleshooting_guides",
]
DOCS_PER_COLLECTION = 12

# ---------------------------------------------------------------------------
# Scenario data helpers
# ---------------------------------------------------------------------------


def _make_scenarios(fake: Faker) -> list[dict]:
    """Return the 50 evaluation scenarios (10 per category)."""

    scenarios: list[dict] = []

    def add(category: str, uid: str, utterance: str, intent: str, tool: str,
            slots: dict, keywords: list[str]) -> None:
        scenarios.append({
            "id": uid,
            "category": category,
            "user_utterance": utterance,
            "expected_intent": intent,
            "expected_tool": tool,
            "expected_slots": slots,
            "ground_truth_answer_keywords": keywords,
        })

    # ---- Billing (10) ----------------------------------------------------
    add("Billing", "eval-001",
        "I was charged twice for my monthly subscription. Can you help me get a refund for the duplicate charge?",
        "resolve_duplicate_charge", "billing",
        {"issue_type": "duplicate_charge", "amount": "auto"},
        ["refund", "duplicate", "charge", "double", "billing"])
    add("Billing", "eval-002",
        "Where can I download my invoice from last month? I need it for my records.",
        "request_invoice", "billing",
        {"document_type": "invoice", "period": "last_month"},
        ["invoice", "download", "PDF", "billing", "statement"])
    add("Billing", "eval-003",
        "My credit card expired last week and I need to update my payment method before the next billing cycle.",
        "update_payment_method", "billing",
        {"action": "update", "payment_method": "credit_card"},
        ["payment", "method", "credit card", "update", "billing"])
    add("Billing", "eval-004",
        f"Can you explain what this ${fake.random_int(20, 200)} charge on my account is for? I don't recognize it.",
        "explain_charge", "billing",
        {"issue_type": "unrecognized_charge"},
        ["charge", "explain", "transaction", "billing", "detail"])
    add("Billing", "eval-005",
        "I need a detailed billing statement for the last six months for my accountant.",
        "request_statement", "billing",
        {"document_type": "statement", "period": "6_months"},
        ["statement", "billing", "detailed", "accountant", "history"])
    add("Billing", "eval-006",
        "Why was I charged sales tax on my subscription? I thought our organization was tax-exempt.",
        "inquire_tax", "billing",
        {"issue_type": "tax_charge", "expected_status": "tax_exempt"},
        ["tax", "exempt", "sales tax", "charge", "billing"])
    add("Billing", "eval-007",
        "Can I change my billing cycle from monthly to annual? I want to save on the annual discount.",
        "change_billing_cycle", "billing",
        {"current_cycle": "monthly", "target_cycle": "annual"},
        ["billing", "cycle", "annual", "monthly", "change", "discount"])
    add("Billing", "eval-008",
        "I want to set up automatic payments so I never miss a due date again.",
        "setup_auto_pay", "billing",
        {"action": "setup", "feature": "auto_pay"},
        ["auto-pay", "automatic", "payment", "setup", "due date"])
    add("Billing", "eval-009",
        "There's an incorrect charge of $199 on my account. I never authorized this purchase.",
        "dispute_charge", "billing",
        {"issue_type": "unauthorized_charge", "amount": "199"},
        ["dispute", "unauthorized", "charge", "fraud", "refund"])
    add("Billing", "eval-010",
        "What payment methods do you accept? Can I pay using PayPal or bank transfer?",
        "inquire_payment_methods", "billing",
        {"action": "inquire", "payment_methods": ["PayPal", "bank_transfer"]},
        ["payment", "methods", "PayPal", "bank transfer", "accept"])

    # ---- Subscription (10) -----------------------------------------------
    add("Subscription", "eval-011",
        "I want to upgrade my plan from Basic to Premium. What additional features will I get?",
        "upgrade_plan", "billing",
        {"current_plan": "Basic", "target_plan": "Premium"},
        ["upgrade", "plan", "Premium", "features", "pricing"])
    add("Subscription", "eval-012",
        "How do I cancel my subscription? I'm not using the service enough to justify the cost.",
        "cancel_subscription", "billing",
        {"action": "cancel", "reason": "underutilization"},
        ["cancel", "subscription", "cancel", "service", "deactivate"])
    add("Subscription", "eval-013",
        "Can I downgrade from Enterprise to Professional? We have downsized our team this quarter.",
        "downgrade_plan", "billing",
        {"current_plan": "Enterprise", "target_plan": "Professional", "reason": "team_downsize"},
        ["downgrade", "plan", "Enterprise", "Professional", "team"])
    add("Subscription", "eval-014",
        "How do I add more users to my existing subscription? We just hired five new team members.",
        "add_users", "billing",
        {"action": "add_users", "count": 5},
        ["add", "users", "seat", "team", "subscription"])
    add("Subscription", "eval-015",
        "When does my free trial end and will I be automatically charged after it expires?",
        "trial_details", "billing",
        {"action": "inquire", "trial_action": "auto_charge"},
        ["trial", "end date", "auto-charge", "expiration", "billing"])
    add("Subscription", "eval-016",
        "What happens to my data if I decide to cancel my subscription? Can I export it first?",
        "data_retention_query", "billing",
        {"action": "cancel", "concern": "data_retention"},
        ["data", "export", "cancel", "retention", "backup"])
    add("Subscription", "eval-017",
        "I want to switch from monthly to annual billing. How much will I save with the annual plan?",
        "switch_billing_frequency", "billing",
        {"current_frequency": "monthly", "target_frequency": "annual"},
        ["annual", "monthly", "switch", "save", "billing"])
    add("Subscription", "eval-018",
        "Can I pause my subscription instead of canceling it? I plan to come back in two months.",
        "pause_subscription", "billing",
        {"action": "pause", "duration_months": 2},
        ["pause", "subscription", "hold", "suspend", "temporary"])
    add("Subscription", "eval-019",
        "I want to change the add-ons included in my current subscription plan.",
        "modify_addons", "billing",
        {"action": "modify", "resource": "addons"},
        ["add-on", "modify", "change", "subscription", "features"])
    add("Subscription", "eval-020",
        "Can you show me my subscription renewal date and the history of my past subscriptions?",
        "subscription_history", "billing",
        {"action": "view", "resource": "subscription_history"},
        ["renewal", "history", "subscription", "past", "timeline"])

    # ---- Refund (10) -----------------------------------------------------
    add("Refund", "eval-021",
        "I need to request a refund for the Pro plan I just purchased. It does not meet my requirements.",
        "request_refund", "billing",
        {"action": "refund", "item": "Pro_plan", "reason": "not_suitable"},
        ["refund", "Pro plan", "request", "unsatisfied", "money back"])
    add("Refund", "eval-022",
        "I was charged for a service I never used. I want my money back immediately.",
        "request_refund", "billing",
        {"action": "refund", "reason": "service_not_used"},
        ["refund", "unused", "service", "charge", "money back"])
    add("Refund", "eval-023",
        "How long does a refund usually take to appear back in my bank account?",
        "check_refund_timeline", "billing",
        {"action": "inquire", "topic": "refund_timeline"},
        ["refund", "timeline", "processing", "bank", "days"])
    add("Refund", "eval-024",
        "I cancelled my subscription last week but I was still charged this month. Please reverse the charge.",
        "refund_after_cancellation", "billing",
        {"issue_type": "post_cancellation_charge"},
        ["cancelled", "charged", "refund", "reverse", "billing error"])
    add("Refund", "eval-025",
        "Can I get a partial refund since I only used the service for one week of the billing month?",
        "request_partial_refund", "billing",
        {"action": "refund", "type": "partial", "usage_days": 7},
        ["partial", "refund", "prorated", "usage", "credit"])
    add("Refund", "eval-026",
        "Your support team promised me a refund two weeks ago and I still haven't received it.",
        "escalate_refund", "billing",
        {"issue_type": "refund_not_received", "promised_date": "2_weeks_ago"},
        ["refund", "promised", "not received", "escalate", "overdue"])
    add("Refund", "eval-027",
        "I accidentally purchased the wrong plan. Can I get a refund and switch to the correct one?",
        "refund_and_switch_plan", "billing",
        {"action": "refund_and_switch", "reason": "wrong_purchase"},
        ["refund", "switch", "plan", "wrong", "exchange"])
    add("Refund", "eval-028",
        "The product did not work as advertised. I am requesting a full refund under your satisfaction guarantee.",
        "request_refund_warranty", "billing",
        {"action": "refund", "reason": "not_as_advertised", "policy": "satisfaction_guarantee"},
        ["refund", "guarantee", "not as advertised", "full", "satisfaction"])
    add("Refund", "eval-029",
        "I was overcharged by $50 on my last invoice. I want the difference refunded to my card.",
        "refund_overcharge", "billing",
        {"issue_type": "overcharge", "amount": 50},
        ["overcharged", "refund", "difference", "invoice", "adjustment"])
    add("Refund", "eval-030",
        "What is your refund policy for annual subscriptions? I am considering cancelling.",
        "inquire_refund_policy", "billing",
        {"action": "inquire", "policy_type": "annual_refund"},
        ["refund policy", "annual", "cancellation", "terms", "prorated"])

    # ---- Product (10) ----------------------------------------------------
    add("Product", "eval-031",
        "Does CloudDesk integrate with Salesforce? We use both and need them to sync data.",
        "integration_inquiry", "knowledge",
        {"product": "CloudDesk", "integration": "Salesforce"},
        ["Salesforce", "integration", "sync", "connect", "CRM"])
    add("Product", "eval-032",
        "Can I generate custom reports with the Analytics module? I need weekly sales summaries.",
        "feature_inquiry", "knowledge",
        {"feature": "custom_reports", "module": "Analytics"},
        ["reports", "Analytics", "custom", "sales", "dashboard"])
    add("Product", "eval-033",
        "What are the differences between the mobile app and the web version of CloudDesk?",
        "feature_comparison", "knowledge",
        {"items": ["mobile_app", "web_version"]},
        ["mobile", "web", "differences", "features", "comparison"])
    add("Product", "eval-034",
        "Do you offer a REST API for custom integrations with our internal tools?",
        "api_inquiry", "knowledge",
        {"feature": "REST_API"},
        ["API", "REST", "integration", "developer", "documentation"])
    add("Product", "eval-035",
        "Is there a way to automate email follow-ups to customers after a support ticket is closed?",
        "automation_inquiry", "knowledge",
        {"feature": "automated_email_followup"},
        ["automate", "email", "follow-up", "workflow", "trigger"])
    add("Product", "eval-036",
        "Can I import my existing customer data from a CSV file into CloudDesk?",
        "data_import_inquiry", "knowledge",
        {"feature": "csv_import", "source": "CSV"},
        ["import", "CSV", "migrate", "data", "customers"])
    add("Product", "eval-037",
        "Does CloudDesk support multi-language communication with customers? We serve international clients.",
        "multilingual_inquiry", "knowledge",
        {"feature": "multi_language"},
        ["multi-language", "translation", "international", "localization", "language"])
    add("Product", "eval-038",
        "What kind of customer support options are available on the Enterprise plan?",
        "support_options_inquiry", "knowledge",
        {"plan": "Enterprise", "feature": "support_options"},
        ["support", "Enterprise", "options", "SLA", "premium"])
    add("Product", "eval-039",
        "Can I customize the dashboard to display my most important KPIs and metrics?",
        "dashboard_customization", "knowledge",
        {"feature": "custom_dashboard", "use_case": "KPI_monitoring"},
        ["dashboard", "customize", "KPI", "metrics", "widgets"])
    add("Product", "eval-040",
        "Do you offer onboarding training sessions for new team members who join our account?",
        "training_inquiry", "knowledge",
        {"feature": "onboarding_training"},
        ["training", "onboarding", "workshop", "team", "setup"])

    # ---- Account Access (10) ---------------------------------------------
    add("Account Access", "eval-041",
        "I forgot my password and cannot log in to my account. How do I reset it?",
        "password_reset", "customer",
        {"action": "reset", "issue": "forgot_password"},
        ["password", "reset", "forgot", "login", "recover"])
    add("Account Access", "eval-042",
        "Can you help me unlock my account? I have been locked out after too many failed login attempts.",
        "unlock_account", "customer",
        {"action": "unlock", "reason": "too_many_attempts"},
        ["unlock", "account", "locked", "login", "attempts"])
    add("Account Access", "eval-043",
        "How do I change the email address associated with my CloudDesk account?",
        "change_email", "customer",
        {"action": "update", "field": "email"},
        ["change", "email", "update", "profile", "account"])
    add("Account Access", "eval-044",
        "I am getting an error message saying my account has been disabled. Can you help me reactivate it?",
        "reactivate_account", "customer",
        {"issue": "account_disabled", "action": "reactivate"},
        ["disabled", "reactivate", "account", "error", "suspended"])
    add("Account Access", "eval-045",
        "Can I set up two-factor authentication to make my account more secure?",
        "setup_2fa", "customer",
        {"action": "enable", "feature": "two_factor_auth"},
        ["two-factor", "2FA", "authentication", "security", "enable"])
    add("Account Access", "eval-046",
        "How do I add a new team member to our organization's CloudDesk account?",
        "add_team_member", "customer",
        {"action": "add", "resource": "team_member"},
        ["add", "team member", "invite", "user", "organization"])
    add("Account Access", "eval-047",
        "I lost access to my authenticator app and I cannot log in. Can you disable 2FA for me temporarily?",
        "disable_2fa_recovery", "customer",
        {"issue": "lost_authenticator", "action": "disable_2fa"},
        ["authenticator", "lost", "2FA", "disable", "recovery"])
    add("Account Access", "eval-048",
        "Why do I keep seeing a session expired error every time I try to access the dashboard?",
        "session_error_troubleshoot", "customer",
        {"issue": "session_expired", "feature": "dashboard"},
        ["session", "expired", "error", "dashboard", "timeout"])
    add("Account Access", "eval-049",
        "Can you merge two accounts? I accidentally created a duplicate when I signed up.",
        "merge_accounts", "customer",
        {"action": "merge", "issue": "duplicate_account"},
        ["merge", "duplicate", "account", "combine", "consolidate"])
    add("Account Access", "eval-050",
        "I need to transfer admin rights to another user in my organization. How do I do that?",
        "transfer_admin", "customer",
        {"action": "transfer", "role": "admin"},
        ["admin", "transfer", "ownership", "role", "permissions"])

    assert len(scenarios) == 50, f"Expected 50 scenarios, got {len(scenarios)}"
    return scenarios


# ---------------------------------------------------------------------------
# Markdown document helpers
# ---------------------------------------------------------------------------


def _ensure_word_count(fake: Faker, parts: list[str], min_words: int = 200) -> list[str]:
    """Append Faker paragraphs until the combined word count reaches *min_words*."""
    word_count = sum(len(p.split()) for p in parts if p.strip())
    while word_count < min_words:
        para = fake.paragraph(nb_sentences=6)
        parts.append("")
        parts.append(para)
        word_count += len(para.split())
    return parts


def _slug(title: str) -> str:
    """Convert a title to a kebab-case slug using only f-strings (no slugify)."""
    return title.lower().replace(" ", "-").replace("'", "").replace(",", "")


def _doc_file_name(idx: int, title: str) -> str:
    """Return a zero-padded filename like ``01-getting-started.md``."""
    return f"{idx:02d}-{_slug(title)}.md"


def _make_documentation_docs(fake: Faker) -> list[dict]:
    """Return 12 documentation markdown documents."""
    docs = []

    topics = [
        ("Getting Started with CloudDesk", [
            "## Introduction",
            "",
            "Welcome to CloudDesk CRM. This guide walks you through the initial setup process so you can start",
            "managing your customer relationships effectively. CloudDesk provides a unified platform for tracking",
            "leads, managing deals, and delivering support across multiple channels.",
            "",
            "## System Requirements",
            "",
            "Before installing CloudDesk, ensure your environment meets the following minimum requirements.",
            "The platform supports all modern web browsers including Chrome, Firefox, Safari, and Edge.",
            "For the mobile app, devices must run iOS 14 or Android 11 and above.",
            "",
            "## Initial Configuration",
            "",
        ]),
        ("Managing Customer Profiles", [
            "## Overview",
            "",
            "Customer profiles are the foundation of your CRM data. This document explains how to create,",
            "edit, and maintain accurate customer records. Each profile can store contact information,",
            "communication history, deal associations, and custom fields tailored to your business needs.",
            "",
            "## Creating a New Customer Record",
            "",
            "To add a new customer, navigate to the Customers section and click the Add Customer button.",
            "Fill in the required fields including name, email address, and phone number. Optional fields",
            "such as company name, industry, and notes can be added later.",
            "",
        ]),
        ("Setting Up Automated Workflows", [
            "## Introduction to Workflows",
            "",
            "Automated workflows help you streamline repetitive tasks and ensure consistent follow-up",
            "with your leads and customers. CloudDesk provides a visual workflow builder that lets you",
            "create trigger-based automation sequences without writing any code.",
            "",
            "## Creating a Workflow",
            "",
            "Navigate to the Automation section and click Create Workflow. Choose a trigger event such",
            "as New Lead Created, Deal Stage Changed, or Ticket Resolved. Then define the actions that",
            "should execute automatically when the trigger occurs.",
            "",
        ]),
        ("Configuring Email Notifications", [
            "## Email Notification Overview",
            "",
            "CloudDesk sends email notifications for various events including new ticket assignments,",
            "deal updates, and invoice reminders. This guide explains how to configure which notifications",
            "are sent and to whom within your organization.",
            "",
            "## Global Notification Settings",
            "",
            "Administrators can access the notification settings from the Configuration panel. From here,",
            "you can enable or disable specific notification types, set quiet hours, and configure",
            "digest email frequency for daily or weekly summaries.",
            "",
        ]),
        ("Creating Custom Report Dashboards", [
            "## Dashboard Customization",
            "",
            "Custom dashboards allow you to visualize the metrics that matter most to your business.",
            "CloudDesk offers a drag-and-drop dashboard builder with a variety of chart types including",
            "bar charts, line graphs, pie charts, and data tables.",
            "",
            "## Adding Widgets",
            "",
            "To build a dashboard, click Create Dashboard and give it a name. Use the widget library",
            "to add data visualizations. Each widget can be configured with specific filters, date ranges,",
            "and data sources from across the CRM platform.",
            "",
        ]),
        ("Integrating Third Party Applications", [
            "## Integration Platform",
            "",
            "CloudDesk connects with hundreds of third-party applications through its integration",
            "marketplace. Popular integrations include email platforms, accounting software, marketing",
            "automation tools, and productivity suites.",
            "",
            "## Available Connectors",
            "",
            "Browse the integrations catalog from the Settings menu. Each connector provides step-by-step",
            "setup instructions and configuration options. Most integrations can be configured in minutes",
            "using OAuth-based authentication.",
            "",
        ]),
        ("Exporting and Importing Data", [
            "## Data Migration Tools",
            "",
            "CloudDesk provides comprehensive tools for importing existing customer data and exporting",
            "your data for backup or analysis. The platform supports CSV, Excel, and JSON formats.",
            "",
            "## Importing Data",
            "",
            "To import data, navigate to Data Management and select Import. Upload your file and use",
            "the column mapping tool to match your fields to CloudDesk data fields. A preview shows",
            "how the data will appear before you finalize the import.",
            "",
        ]),
        ("Managing Team Roles and Permissions", [
            "## Role-Based Access Control",
            "",
            "CloudDesk provides granular permission controls that allow administrators to define exactly",
            "what each team member can see and do within the platform. Roles can be customized to match",
            "your organizational structure.",
            "",
            "## Default Roles",
            "",
            "The system includes several predefined roles: Administrator, Manager, Agent, and Viewer.",
            "Each role comes with a specific set of permissions that can be further customized to meet",
            "your team's requirements.",
            "",
        ]),
        ("Setting Up SSO Authentication", [
            "## Single Sign-On Overview",
            "",
            "Single Sign-On (SSO) allows your team to log in to CloudDesk using their existing corporate",
            "credentials. CloudDesk supports SAML 2.0 and OpenID Connect protocols.",
            "",
            "## Configuring SSO",
            "",
            "To enable SSO, go to Authentication Settings in the Admin panel. Select your identity provider",
            "from the list or configure a custom provider. You will need to provide your IdP metadata URL",
            "or upload the metadata XML file.",
            "",
        ]),
        ("Using the Mobile Application", [
            "## Mobile App Features",
            "",
            "The CloudDesk mobile app brings the power of your CRM to your smartphone. Available for",
            "iOS and Android, the app provides access to contacts, deals, tickets, and dashboards.",
            "",
            "## Getting Started",
            "",
            "Download the app from the App Store or Google Play Store. Log in using your CloudDesk",
            "credentials. The mobile interface automatically syncs with your desktop data in real time.",
            "",
        ]),
        ("Customizing Pipeline Stages", [
            "## Sales Pipeline Management",
            "",
            "Sales pipelines track the progress of deals from initial contact to closing. CloudDesk",
            "allows you to create multiple pipelines and customize the stages to match your sales process.",
            "",
            "## Creating Pipeline Stages",
            "",
            "Go to Pipeline Settings and click Add Pipeline. Name your pipeline and add stages in the",
            "order that represents your sales workflow. Each stage can be assigned a probability percentage",
            "for forecasting purposes.",
            "",
        ]),
        ("API Reference Guide", [
            "## CloudDesk REST API",
            "",
            "The CloudDesk API provides programmatic access to all core CRM functions. This reference",
            "documents available endpoints, authentication requirements, and usage examples.",
            "",
            "## Authentication",
            "",
            "All API requests require an API key passed in the Authorization header. Generate API keys",
            "from the Developer Settings page in your account. Keys can be scoped to specific permissions.",
            "",
        ]),
    ]

    for idx, (title, body_parts) in enumerate(topics, start=1):
        parts = [
            f"# {title}",
            "",
            *body_parts,
        ]
        parts = _ensure_word_count(fake, parts)
        content = "\n".join(parts)
        docs.append({
            "collection": "documentation",
            "filename": _doc_file_name(idx, title),
            "content": content,
        })

    return docs


def _make_policies_docs(fake: Faker) -> list[dict]:
    """Return 12 policy markdown documents."""
    docs = []

    topics = [
        ("Terms of Service", [
            "## Acceptance of Terms",
            "",
            "By accessing or using CloudDesk CRM, you agree to be bound by these Terms of Service.",
            "If you do not agree with any part of these terms, you may not use the service. These terms",
            "constitute a legally binding agreement between your organization and CloudDesk Inc.",
            "",
            "## Service Description",
            "",
            "CloudDesk provides a cloud-based customer relationship management platform that includes",
            "contact management, sales tracking, customer support tools, and analytics features.",
        ]),
        ("Privacy Policy", [
            "## Information We Collect",
            "",
            "CloudDesk collects information you provide when creating an account, uploading customer data,",
            "and using platform features. This includes names, email addresses, phone numbers, and",
            "business information necessary for CRM functionality.",
            "",
            "## How We Use Your Information",
            "",
            "Your data is used to provide and improve the CloudDesk service. We do not sell your personal",
            "information to third parties. Data is processed and stored securely in compliance with",
            "applicable data protection regulations.",
        ]),
        ("Data Retention Policy", [
            "## Retention Periods",
            "",
            "CloudDesk retains customer data for the duration of your active subscription plus a grace",
            "period of 90 days after cancellation. During this grace period, you may request a data export.",
            "",
            "## Data Deletion",
            "",
            "Upon expiration of the retention period, all customer data is permanently deleted from our",
            "systems. Deletion includes database records, backups, and cached copies across all data centers.",
        ]),
        ("Refund and Cancellation Policy", [
            "## Refund Eligibility",
            "",
            "Monthly subscriptions may be refunded within the first 14 days of service. Annual subscriptions",
            "are eligible for a prorated refund minus any usage for the months already consumed.",
            "",
            "## Processing Time",
            "",
            "Refunds are processed within 5 to 10 business days after approval. The refund will be issued",
            "to the original payment method used for the purchase.",
        ]),
        ("Service Level Agreement", [
            "## Uptime Guarantee",
            "",
            "CloudDesk guarantees 99.9 percent platform uptime measured on a monthly basis. Scheduled",
            "maintenance windows are excluded from uptime calculations and will be announced at least",
            "48 hours in advance.",
            "",
            "## Support Response Times",
            "",
            "Enterprise customers receive priority support with a maximum 1-hour response time for",
            "critical issues. Standard customers receive responses within 4 hours during business hours.",
        ]),
        ("Acceptable Use Policy", [
            "## Permitted Use",
            "",
            "CloudDesk may be used for lawful business purposes including customer relationship management,",
            "sales tracking, and customer support operations. Users must comply with all applicable laws",
            "and regulations.",
            "",
            "## Prohibited Activities",
            "",
            "Users may not upload illegal content, send spam through the platform, attempt to breach",
            "system security, or use the service for any unlawful purpose. Violations may result in",
            "immediate account termination.",
        ]),
        ("Security Policy", [
            "## Data Security Measures",
            "",
            "CloudDesk employs industry-standard security measures including encryption in transit and",
            "at rest, regular security audits, and access controls. All data is encrypted using AES-256",
            "at rest and TLS 1.3 in transit.",
            "",
            "## Incident Response",
            "",
            "Our security team monitors systems 24/7 for potential threats. In the event of a security",
            "incident, affected customers are notified within 72 hours of confirmation.",
        ]),
        ("Data Processing Agreement", [
            "## Data Processor Role",
            "",
            "CloudDesk acts as a data processor on behalf of its customers. This Data Processing Agreement",
            "sets out the terms governing the processing of personal data by CloudDesk.",
            "",
            "## Sub-processors",
            "",
            "CloudDesk uses carefully selected sub-processors to deliver the service. A current list of",
            "sub-processors is maintained on our trust page. Customers will be notified of any changes.",
        ]),
        ("Cookie Policy", [
            "## How We Use Cookies",
            "",
            "CloudDesk uses cookies and similar tracking technologies to enhance your experience, analyze",
            "usage patterns, and provide personalized content. Cookies are small text files stored on",
            "your device.",
            "",
            "## Managing Cookies",
            "",
            "You can control cookie preferences through your browser settings. Disabling certain cookies",
            "may affect platform functionality. Essential cookies cannot be disabled as they are necessary",
            "for the service to operate.",
        ]),
        ("User Code of Conduct", [
            "## Community Standards",
            "",
            "All CloudDesk users are expected to maintain professional and respectful communication when",
            "interacting with other users, support staff, and through the platform's messaging features.",
            "",
            "## Reporting Violations",
            "",
            "If you encounter behavior that violates this Code of Conduct, please report it to our trust",
            "and safety team. All reports are investigated promptly and confidentially.",
        ]),
        ("Billing and Payment Terms", [
            "## Subscription Fees",
            "",
            "Subscription fees are billed in advance on a monthly or annual basis depending on your chosen",
            "billing cycle. Fees are non-refundable except as specified in the Refund Policy.",
            "",
            "## Late Payments",
            "",
            "Payments not received within 15 days of the due date may result in service suspension.",
            "A late fee of 1.5 percent per month may be applied to overdue balances.",
        ]),
        ("Third Party Integration Policy", [
            "## Integration Responsibility",
            "",
            "CloudDesk provides connectors to third-party services for your convenience. CloudDesk is not",
            "responsible for the functionality, security, or data practices of third-party services.",
            "",
            "## Data Sharing",
            "",
            "When you enable an integration, data may be shared between CloudDesk and the third-party",
            "service according to the integration's configuration. Review each service's privacy policy.",
        ]),
    ]

    for idx, (title, body_parts) in enumerate(topics, start=1):
        parts = [
            f"# {title}",
            "",
            *body_parts,
        ]
        parts = _ensure_word_count(fake, parts)
        content = "\n".join(parts)
        docs.append({
            "collection": "policies",
            "filename": _doc_file_name(idx, title),
            "content": content,
        })

    return docs


def _make_knowledge_articles_docs(fake: Faker) -> list[dict]:
    """Return 12 knowledge-article markdown documents."""
    docs = []

    topics = [
        ("How to Reset Your Password", [
            "## Step-by-Step Guide",
            "",
            "If you have forgotten your CloudDesk password, follow these steps to reset it. You will need",
            "access to the email address associated with your account to complete the reset process.",
            "This procedure works for both web and mobile applications.",
            "",
            "## Instructions",
            "",
            "Go to the login page and click the Forgot Password link. Enter your registered email address",
            "and check your inbox for a password reset email. Click the link in the email to create a new",
            "password. Choose a strong password with at least 12 characters including letters and numbers.",
        ]),
        ("Best Practices for Data Entry", [
            "## Data Quality Guidelines",
            "",
            "Maintaining clean and consistent data is essential for getting the most value from CloudDesk.",
            "This article outlines best practices for entering and maintaining customer data in the system.",
            "",
            "## Standardization Tips",
            "",
            "Use consistent formatting for phone numbers, addresses, and company names. Establish naming",
            "conventions for deals and contacts. Regularly audit your data for duplicates and outdated entries.",
            "Encourage team members to fill in all relevant fields when creating new records.",
        ]),
        ("Understanding the Dashboard", [
            "## Dashboard Overview",
            "",
            "The CloudDesk dashboard provides a real-time snapshot of your key business metrics. This article",
            "explains the default widgets and how to interpret the data displayed on your home screen.",
            "",
            "## Default Widgets",
            "",
            "The default dashboard includes widgets for active deals, recent tickets, upcoming tasks, and",
            "monthly revenue. Each widget can be customized, resized, or removed. Click on any widget to",
            "drill down into the underlying data for more detailed analysis.",
        ]),
        ("Managing Contact Lists", [
            "## Contact Organization",
            "",
            "CloudDesk allows you to organize your contacts into lists and segments for targeted communication.",
            "This article covers creating, managing, and using contact lists effectively.",
            "",
            "## Creating Lists",
            "",
            "Navigate to the Contacts section and select Lists. Click Create List and define the criteria",
            "for automatic list population. Dynamic lists update automatically as new contacts are added or",
            "existing ones are modified. Static lists require manual addition of contacts.",
        ]),
        ("Creating Email Templates", [
            "## Template Basics",
            "",
            "Email templates save time by allowing you to reuse common email formats for customer communication.",
            "CloudDesk provides a template editor with rich text formatting and variable insertion.",
            "",
            "## Building Templates",
            "",
            "Go to Templates in the Settings menu and click New Template. Use the editor to compose your",
            "message. Insert variables such as customer name, company, and deal amount using the variable",
            "picker. Templates can be organized into folders for easy access.",
        ]),
        ("Automating Repetitive Tasks", [
            "## Workflow Automation",
            "",
            "CloudDesk automation rules help you eliminate manual work by automatically performing actions",
            "based on triggers. This article explains common automation patterns and use cases.",
            "",
            "## Common Automations",
            "",
            "Popular automation rules include assigning new leads to the appropriate sales representative,",
            "sending welcome emails to new customers, creating follow-up tasks when a deal reaches a",
            "specific stage, and escalating overdue support tickets to managers.",
        ]),
        ("Setting Up Goal Tracking", [
            "## Goals and Targets",
            "",
            "Goal tracking in CloudDesk helps your team stay focused on key performance indicators. This",
            "article explains how to set up individual and team goals for revenue, deals closed, and",
            "customer satisfaction metrics.",
            "",
            "## Creating Goals",
            "",
            "Navigate to the Reports section and select Goals. Click Add Goal and choose the metric type.",
            "Set a target value and time period. Goals can be assigned to individuals or teams and progress",
            "is displayed on the dashboard in real time.",
        ]),
        ("Using the Search Feature", [
            "## Search Capabilities",
            "",
            "CloudDesk provides a powerful search engine that indexes all your CRM data. This article covers",
            "search syntax, filters, and tips for finding information quickly.",
            "",
            "## Search Tips",
            "",
            "Use the global search bar at the top of any page to search across contacts, deals, tickets,",
            "and notes. Advanced search operators allow you to filter by date range, record type, and",
            "assigned user. Saved searches can be shared with your team.",
        ]),
        ("Collaborating with Team Members", [
            "## Team Collaboration Tools",
            "",
            "CloudDesk includes several features designed to facilitate team collaboration. This article",
            "covers internal notes, mentions, shared views, and activity feeds.",
            "",
            "## Using Mentions",
            "",
            "Type the @ symbol followed by a team member's name to notify them in notes and comments.",
            "Mentioned users receive a notification and can respond directly from their notification center.",
            "This keeps communication contextually linked to the relevant record.",
        ]),
        ("Understanding the Activity Timeline", [
            "## Timeline Overview",
            "",
            "Every record in CloudDesk includes an activity timeline that logs all interactions and changes.",
            "This article explains how to use timelines to track customer interactions and audit changes.",
            "",
            "## Timeline Events",
            "",
            "The timeline automatically records events such as emails sent, notes added, deals moved between",
            "stages, and tickets updated. Each event includes a timestamp and the user who performed the action.",
            "Timelines provide a complete audit trail for every customer record.",
        ]),
        ("Managing Document Templates", [
            "## Document Generation",
            "",
            "CloudDesk allows you to create document templates for proposals, contracts, and invoices.",
            "This article covers creating templates and generating documents from CRM data.",
            "",
            "## Creating Templates",
            "",
            "Go to Documents in the Settings section and select Templates. Use the document editor to design",
            "your template layout. Insert fields from the CRM such as customer name, deal value, and product",
            "details. Templates support multiple file formats including PDF and Word.",
        ]),
        ("Configuring Report Schedules", [
            "## Scheduled Reports",
            "",
            "CloudDesk can automatically generate and email reports on a recurring schedule. This article",
            "explains how to set up daily, weekly, and monthly report deliveries.",
            "",
            "## Setting Up Schedules",
            "",
            "Create a report using the report builder and save it. Click the Schedule button and choose",
            "the frequency and recipients. Reports are generated automatically and delivered as PDF or CSV",
            "attachments at the specified interval.",
        ]),
    ]

    for idx, (title, body_parts) in enumerate(topics, start=1):
        parts = [
            f"# {title}",
            "",
            *body_parts,
        ]
        parts = _ensure_word_count(fake, parts)
        content = "\n".join(parts)
        docs.append({
            "collection": "knowledge_articles",
            "filename": _doc_file_name(idx, title),
            "content": content,
        })

    return docs


def _make_troubleshooting_docs(fake: Faker) -> list[dict]:
    """Return 12 troubleshooting-guide markdown documents."""
    docs = []

    topics = [
        ("Cannot Log In to Account", [
            "## Symptoms",
            "",
            "Users are unable to access their CloudDesk account and see an error message on the login page.",
            "This can occur due to incorrect credentials, account lockouts, or session issues.",
            "",
            "## Troubleshooting Steps",
            "",
            "First, verify that you are using the correct email address and password. Use the Forgot Password",
            "link to reset your credentials if needed. Check that Caps Lock is not enabled and that there",
            "are no extra spaces in your password field.",
        ]),
        ("Email Notifications Not Sending", [
            "## Symptoms",
            "",
            "Team members are not receiving email notifications for events such as new ticket assignments,",
            "deal updates, or invoice reminders. This can affect team responsiveness.",
            "",
            "## Troubleshooting Steps",
            "",
            "Check the Notification Settings in your profile to ensure email notifications are enabled.",
            "Verify that the email addresses on user profiles are correct. Ask your IT team to check",
            "that CloudDesk emails are not being blocked by your email security filters.",
        ]),
        ("Data Not Syncing Across Devices", [
            "## Symptoms",
            "",
            "Changes made on the web application are not visible on the mobile app and vice versa.",
            "This can cause confusion and data inconsistencies across the team.",
            "",
            "## Troubleshooting Steps",
            "",
            "First, ensure both devices have an active internet connection. On the mobile app, pull down",
            "to trigger a manual sync. Log out and log back in on both devices to force a full data refresh.",
            "Check that you are running the latest version of the mobile application.",
        ]),
        ("Report Generation Failing", [
            "## Symptoms",
            "",
            "Custom or scheduled reports fail to generate or produce incomplete results with error messages.",
            "This can impact business reporting and decision-making processes.",
            "",
            "## Troubleshooting Steps",
            "",
            "Check that the report's date range and filters are valid. Very large datasets may cause timeouts.",
            "Try reducing the date range or adding additional filters. Verify that all referenced fields",
            "and custom fields still exist and have not been deleted or renamed.",
        ]),
        ("Integration Connection Errors", [
            "## Symptoms",
            "",
            "Third-party integrations show a disconnected or error status and data does not sync between",
            "CloudDesk and the external service.",
            "",
            "## Troubleshooting Steps",
            "",
            "Navigate to the Integrations page and check the status of each connector. Re-authenticate the",
            "integration by clicking Reconnect and following the OAuth flow. Verify that the third-party",
            "service is operational and that your API keys or tokens have not expired.",
        ]),
        ("Dashboard Not Loading Properly", [
            "## Symptoms",
            "",
            "The CloudDesk dashboard displays a loading spinner indefinitely or shows partial content with",
            "JavaScript errors in the browser console.",
            "",
            "## Troubleshooting Steps",
            "",
            "Clear your browser cache and cookies and reload the page. Try accessing the dashboard in an",
            "incognito or private browsing window. Disable browser extensions that may interfere with",
            "page rendering. Check the CloudDesk status page for any ongoing incidents.",
        ]),
        ("Import Failing with Errors", [
            "## Symptoms",
            "",
            "CSV or Excel file imports fail partway through with validation errors or data format issues.",
            "This prevents data migration and slows down onboarding.",
            "",
            "## Troubleshooting Steps",
            "",
            "Verify that your file meets the format requirements specified in the import guide. Check for",
            "special characters, extra commas, or mismatched column headers. Ensure date fields use ISO",
            "format YYYY-MM-DD. Split large files into smaller batches of 1000 records or fewer.",
        ]),
        ("API Rate Limit Exceeded", [
            "## Symptoms",
            "",
            "API requests return HTTP 429 Too Many Requests responses. This prevents integrations and",
            "automated scripts from functioning correctly.",
            "",
            "## Troubleshooting Steps",
            "",
            "Review the API rate limits for your plan tier in the API documentation. Implement exponential",
            "backoff in your integration code to handle rate limiting gracefully. Consider upgrading your",
            "plan for higher rate limits if you consistently hit the cap.",
        ]),
        ("Mobile App Crashing", [
            "## Symptoms",
            "",
            "The CloudDesk mobile application crashes frequently, freezes during use, or fails to open.",
            "This affects field teams who rely on mobile access.",
            "",
            "## Troubleshooting Steps",
            "",
            "Ensure your device meets the minimum OS requirements. Update the app to the latest version",
            "from the App Store or Google Play Store. Restart your device and clear the app cache from",
            "the device settings. If the issue persists, uninstall and reinstall the application.",
        ]),
        ("Search Results Incomplete", [
            "## Symptoms",
            "",
            "The global search feature returns partial or no results for queries that should match existing",
            "records. This reduces productivity and user trust in the system.",
            "",
            "## Troubleshooting Steps",
            "",
            "Check that the records you are searching for have been fully indexed. New records may take a",
            "few minutes to appear in search results. Use more general search terms to broaden results.",
            "Verify that you have the necessary permissions to view the records you are searching for.",
        ]),
        ("Performance Slow on Large Datasets", [
            "## Symptoms",
            "",
            "CloudDesk pages load slowly, queries take a long time to return results, and the interface",
            "feels sluggish when working with large amounts of data.",
            "",
            "## Troubleshooting Steps",
            "",
            "Use filters and date ranges to limit the amount of data displayed on screen. Archive old records",
            "that are no longer actively needed. Consider upgrading to a plan with dedicated infrastructure",
            "if you consistently work with datasets exceeding 100,000 records.",
        ]),
        ("SSO Authentication Failure", [
            "## Symptoms",
            "",
            "Users cannot log in using Single Sign-On. They see an SSO error page or are redirected back to",
            "the login screen without being authenticated.",
            "",
            "## Troubleshooting Steps",
            "",
            "Verify that the SSO configuration in CloudDesk matches your identity provider settings. Check",
            "that the SAML certificate has not expired. Ensure the ACS URL and entity ID are correctly",
            "configured in both systems. Review the IdP logs for detailed error information.",
        ]),
    ]

    for idx, (title, body_parts) in enumerate(topics, start=1):
        parts = [
            f"# {title}",
            "",
            *body_parts,
        ]
        parts = _ensure_word_count(fake, parts)
        content = "\n".join(parts)
        docs.append({
            "collection": "troubleshooting_guides",
            "filename": _doc_file_name(idx, title),
            "content": content,
        })

    return docs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic EVA evaluation data (50 scenarios + 48 docs).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility.",
    )
    parser.add_argument(
        "--out",
        default="data/synthetic",
        help="Output directory (default: data/synthetic).",
    )
    args = parser.parse_args()

    fake = Faker(locale="en_US")
    fake.seed_instance(args.seed)

    out_path = Path(args.out)
    docs_path = out_path / "docs"

    # --- Scenarios --------------------------------------------------------
    scenarios = _make_scenarios(fake)
    jsonl_path = out_path / "eval_scenarios.jsonl"
    out_path.mkdir(parents=True, exist_ok=True)

    with open(jsonl_path, "w", encoding="utf-8") as f:
        for s in scenarios:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"Wrote {len(scenarios)} scenarios to {jsonl_path}")

    # --- Markdown docs ----------------------------------------------------
    all_docs: list[dict] = []
    all_docs.extend(_make_documentation_docs(fake))
    all_docs.extend(_make_policies_docs(fake))
    all_docs.extend(_make_knowledge_articles_docs(fake))
    all_docs.extend(_make_troubleshooting_docs(fake))

    for doc in all_docs:
        collection_dir = docs_path / doc["collection"]
        collection_dir.mkdir(parents=True, exist_ok=True)
        file_path = collection_dir / doc["filename"]
        file_path.write_text(doc["content"], encoding="utf-8")

    # Verify counts
    per_collection: dict[str, int] = {}
    for d in all_docs:
        per_collection[d["collection"]] = per_collection.get(d["collection"], 0) + 1

    print(f"Wrote {len(all_docs)} docs ({docs_path})")
    for col, count in sorted(per_collection.items()):
        print(f"  {col}: {count} files")
    assert len(all_docs) == 48, f"Expected 48 docs, got {len(all_docs)}"
    assert all(
        c in per_collection and per_collection[c] == 12 for c in COLLECTIONS
    ), "Not all collections have exactly 12 docs"

    # Verify word counts
    doc: dict
    for doc in all_docs:
        wc = len(doc["content"].split())
        assert wc >= 200, f"Doc {doc['collection']}/{doc['filename']} has only {wc} words"

    print("All word-count checks passed (>=200 each).")
    sys.exit(0)


if __name__ == "__main__":
    main()
