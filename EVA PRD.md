# Product Requirements Document (PRD)

# EVA (Enterprise Voice Assistant)

Evidence-Based Multi-Source Enterprise Reasoning System

Version: MVP v1.0

Methodology: Agile SDLC

Target Development Timeline: 2–3 Weeks

Project Type: Portfolio-Grade Production-Oriented AI System

---

# Executive Summary

EVA is a production-oriented enterprise voice AI system capable of retrieving information from multiple enterprise knowledge sources and reasoning across them to assist customers in real time.

Unlike traditional chatbots that answer questions from a single knowledge base, EVA synthesizes evidence from structured and unstructured enterprise systems including:

* Customer Records
* Subscription Data
* Billing Records
* Support Tickets
* Usage Analytics
* Product Documentation
* Internal Policies

The system provides evidence-backed responses through natural voice conversations in Bangla and English.

The core innovation is not voice interaction.

The core innovation is cross-source evidence reasoning.

Voice serves as the primary interaction interface.

---

# Product Vision

Build a production-oriented AI system that demonstrates how modern enterprises can combine:

* Voice AI
* Tool-Augmented LLMs
* Retrieval-Augmented Generation
* Structured Data Retrieval
* Multi-Source Reasoning
* Enterprise Knowledge Systems

into a single customer support experience.

The project should clearly demonstrate advanced AI engineering capabilities rather than simple chatbot development.

---

# Primary Goal

A recruiter, AI engineer, or hiring manager reviewing the project should immediately recognize:

"This person knows how to design and build production-oriented AI systems."

---

# Core Problem

Customer support issues rarely require information from a single source.

Example:

Customer asks:

"Why was I charged twice and why hasn't my issue been resolved?"

Answering this requires:

* Billing history
* Previous support tickets
* Subscription status
* Refund policy

Most chatbots cannot combine information across systems.

EVA solves this by retrieving evidence from multiple sources and generating evidence-backed conclusions.

---

# Key Differentiator

Traditional Support Chatbot

Customer Query
↓
Documentation Search
↓
Answer

EVA

Customer Query
↓
Intent Analysis
↓
Tool Selection
↓
Multi-Source Retrieval
↓
Evidence Aggregation
↓
Cross-Source Reasoning
↓
Evidence-Based Response

---

# Success Criteria

The system should demonstrate:

✓ Voice AI Integration

✓ Tool-Augmented LLM Systems

✓ Multi-Source Retrieval

✓ Evidence-Based Reasoning

✓ RAG Architecture

✓ Production-Oriented Architecture

✓ Evaluation Methodology

✓ Enterprise System Design

---

# Supported Languages

Primary:

* Bangla

Secondary:

* English

Supported Conversation Modes:

* Bangla
* English
* Code-Switched Bangla-English

Examples:

"আমার subscription inactive কেন?"

"আমার refund request-এর update কী?"

"Why was I charged twice last month?"

---

# Enterprise Environment

The MVP simulates a SaaS company.

Company Name:

CloudDesk CRM

The company maintains:

* Customer Profiles
* Subscription Records
* Billing Records
* Support Tickets
* CRM Notes
* Product Documentation
* Internal Policies
* Usage Analytics

---

# System Architecture

Voice Layer
↓
Orchestrator
↓
Intent Analysis
↓
Tool Selection
↓
Retrieval Layer
↓
Evidence Aggregation
↓
Reasoning Engine
↓
Response Generation
↓
Voice Output

---

# Architecture Philosophy

The LLM does not directly access databases.

The LLM only interacts with controlled tools.

All enterprise information is retrieved through tool interfaces.

---

# Functional Requirements

## FR-01 Voice Interaction

Users must communicate naturally through voice.

Capabilities:

* Streaming audio input
* Streaming audio output
* Real-time interaction
* Voice interruption support

Technology:

* Gemini Native Audio

---

## FR-02 Intent Analysis

The system must determine:

* Customer intent
* Required information sources
* Required tools

Example:

Query:

"Why was I charged twice?"

Intent:

Billing Inquiry

Required Sources:

* Billing Records
* Tickets
* Refund Policy

---

## FR-03 Tool Selection

The system must dynamically determine which tools are necessary.

The system should avoid unnecessary retrieval.

Example:

Refund Query

Retrieve:

* Billing
* Tickets
* Policy

Do Not Retrieve:

* Product Documentation

---

## FR-04 Structured Data Retrieval

The system must retrieve customer-specific information.

Supported Sources:

* Customer Profiles
* Subscriptions
* Billing Records
* Support Tickets
* Usage Analytics

---

## FR-05 Knowledge Retrieval

The system must retrieve unstructured knowledge.

Supported Sources:

* Documentation
* FAQs
* Internal Policies
* Troubleshooting Guides

Retrieval Method:

* Vector Search
* Semantic Search

---

## FR-06 Evidence Aggregation

The system must combine retrieved information into a unified context package.

Example:

Customer Profile
+
Billing History
+
Support Tickets
+
Policy Documents

↓

Evidence Package

---

## FR-07 Evidence-Based Reasoning

Reasoning is defined as:

Combining evidence from multiple sources to generate conclusions that cannot be produced from a single source.

Supported Reasoning Types:

### Evidence Corroboration

Multiple sources support the same conclusion.

### Policy Application

Apply company policies to customer situations.

### Root Cause Analysis

Identify likely causes of customer issues.

### Decision Support

Determine likely customer eligibility.

---

## FR-08 Response Generation

Responses must be:

* Accurate
* Evidence-Based
* Personalized
* Conversational

The system should explain conclusions using retrieved evidence.

---

## FR-09 Conversational Memory

The system should maintain context within the current session.

Examples:

* Previous questions
* Previous tool results
* Customer references

Memory Scope:

Session Only

---

## FR-10 Call Summary Generation

After each conversation:

Generate:

* Conversation Summary
* Sources Used
* Reasoning Summary
* Recommended Next Actions

---

# Tool Architecture

## Customer Tool

Functions:

* get_customer_profile()
* get_subscription_status()

---

## Billing Tool

Functions:

* get_billing_history()
* get_refund_history()

---

## Ticket Tool

Functions:

* get_support_tickets()
* get_ticket_status()

---

## Analytics Tool

Functions:

* get_usage_analytics()

---

## Knowledge Tool

Functions:

* search_documentation()
* search_policies()

---

# Security Requirements

## Authentication

MVP Authentication:

* Mock Customer Verification
* Customer ID Verification

Future:

* OTP
* Phone Verification

---

## Authorization

The system must only access records belonging to the authenticated customer.

---

## Database Access

The LLM must never generate SQL queries.

The LLM interacts exclusively through tools.

---

## Data Minimization

Only necessary information should be retrieved.

---

# Hallucination Prevention

The system must generate conclusions only from retrieved evidence.

If evidence is insufficient:

Respond:

"I do not have enough information to determine that."

instead of guessing.

---

# Failure Handling

If retrieval fails:

* Continue with available evidence
* Inform the user
* Avoid unsupported conclusions

Example:

"I was unable to access billing information, but I reviewed your support history."

---

# Database Design

Single PostgreSQL Database

Tables:

customers

subscriptions

billing_records

support_tickets

usage_analytics

crm_notes

conversation_sessions

conversation_messages

---

# Vector Database

PGVector

Collections:

documentation

policies

knowledge_articles

troubleshooting_guides

---

# Evaluation Framework

The system must include evaluation scenarios.

Evaluation Dataset:

50 Synthetic Support Scenarios

Categories:

* Billing Issues
* Subscription Issues
* Refund Requests
* Product Problems
* Account Access

Metrics:

### Retrieval Accuracy

Were correct sources selected?

### Reasoning Accuracy

Was the final conclusion correct?

### Hallucination Rate

Did the system generate unsupported claims?

### Response Quality

Was the response useful?

---

# Analytics Dashboard

Display:

Conversation Timeline

Retrieved Sources

Tool Calls

Reasoning Trace

Token Usage

Latency Metrics

Confidence Score

Final Resolution

---

# Technology Stack

Frontend

* TanStack Start
* TypeScript
* TailwindCSS

Voice Layer

* Gemini Native Audio

Backend

* FastAPI
* Python

Database

* PostgreSQL

Vector Search

* PGVector

Observability

* Langfuse

Deployment

* Docker

Hosting

* Railway

---

# Agile Development Plan

Sprint 1

Foundation

Deliverables:

* Database Schema
* Synthetic Dataset
* FastAPI Backend
* PostgreSQL Integration
* PGVector Setup

---

Sprint 2

Retrieval Layer

Deliverables:

* Customer Tool
* Billing Tool
* Ticket Tool
* Knowledge Tool

---

Sprint 3

Reasoning Engine

Deliverables:

* Intent Analysis
* Tool Selection
* Evidence Aggregation
* Reasoning Pipeline

---

Sprint 4

Voice Experience

Deliverables:

* Gemini Audio Integration
* Conversational Memory
* Call Summaries

---

Sprint 5

Evaluation & Dashboard

Deliverables:

* Evaluation Dataset
* Metrics
* Dashboard
* Demo Scenarios

---

# Future Roadmap

Phase 2

* Phone Calling Integration
* Twilio Integration
* Human Handoff
* CRM Integration
* Sentiment Analysis
* Long-Term Memory
* Advanced Authentication
* Multi-Tenant Architecture

---

# Final Success Metric

A reviewer should be able to watch a 3-minute demonstration and clearly observe:

1. Voice conversation.

2. Dynamic tool selection.

3. Retrieval from multiple enterprise sources.

4. Evidence aggregation.

5. Cross-source reasoning.

6. Evidence-backed conclusions.

The reviewer should conclude:

"This is not a chatbot. This is a production-oriented AI reasoning system."
