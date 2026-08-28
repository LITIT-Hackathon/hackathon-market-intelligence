# Hackathon Challenge — Opportunity Radar

## Goal

Build an AI-powered market intelligence solution that turns IT job-market
data into explainable, ranked B2B collaboration opportunities.

The objective is not only to identify companies that are hiring.

The solution should identify meaningful hiring patterns and determine
which companies may represent potential business opportunities.

Think:

Job listings
    ↓
Structured market signals
    ↓
Company-level hiring patterns
    ↓
Potential collaboration opportunities
    ↓
Ranked and explainable sales leads

---

## Problem

Public job postings contain useful information about:

- company growth
- new projects
- technology adoption
- hiring pressure
- transformation programmes
- skills shortages
- geographic expansion

Individually, these job listings are noisy.

Your task is to transform this data into useful market intelligence that
could help a sales team answer:

> Which companies should we approach, why, and what evidence supports that decision?

---

## Provided Data

The following historical German job-posting dataset is provided as the
main reference dataset:

https://huggingface.co/datasets/mischeiwiller/german-job-postings

The dataset contains approximately 70,000 German job postings and includes
information such as:

- employer
- job title
- location / region
- publication date
- source URL
- seniority
- occupation classifications
- extracted skills and metadata

Teams may use additional public data sources if desired.

---

## Minimum Expected Result

Your solution should:

1. Ingest and process the supplied job-market dataset.
2. Identify and normalize companies where necessary.
3. Extract or derive relevant hiring signals.
4. Aggregate job information at company level.
5. Identify potential collaboration or business opportunities.
6. Rank the identified opportunities.
7. Explain why each company received its ranking.
8. Preserve supporting evidence from the underlying job data.
9. Expose the results through a simple API, dashboard, report, or other
   demonstrable interface.

---

## Example

A possible result could look like:

Company: Example GmbH

Opportunity score: 87 / 100

Opportunity:
Potential software-engineering delivery partnership

Signals:
- 14 software engineering vacancies published recently
- strong concentration of Java and Azure roles
- several senior positions
- hiring activity increased significantly compared with the historical baseline

Reasoning:
The company appears to be rapidly expanding engineering capacity around a
cloud transformation programme. The concentration and timing of vacancies
may indicate delivery-capacity pressure.

Evidence:
- Senior Java Developer
- Azure Cloud Architect
- DevOps Engineer
- Backend Engineer
- ...

The scoring approach and interpretation are up to the team.

---

## Important

There is no predefined algorithm for determining an opportunity.

Teams are expected to decide:

- what constitutes a meaningful hiring signal;
- how companies should be compared;
- how opportunities should be scored;
- where AI/ML/LLMs provide value;
- how evidence and confidence should be represented.

The system should not simply rank companies by number of vacancies.

The business value comes from interpreting the underlying patterns.

---

## Scope

A production-ready system is not required.

A working, demonstrable MVP is sufficient.

The following are NOT required:

- crawling the entire public web;
- production CRM integration;
- automated outreach;
- production-grade data pipelines;
- perfect company/entity resolution.

Teams may use open-source libraries, external APIs and AI models.

---

## Stretch Goals

Examples include:

- live job acquisition;
- hiring velocity / acceleration detection;
- technology trend detection;
- company clustering;
- competitor vs. partner classification;
- geographic analysis;
- confidence scoring;
- suggested sales approach;
- CRM-ready export;
- scheduled market monitoring.

---

## Provided Resources

Each team will receive:

- GCP sandbox environment with $300 in credits
- LLM/API token credits for AI model usage

Teams are free to use these resources where they add value to their solution.

---

## Deliverable

At the end of the hackathon, demonstrate:

- a working MVP;
- a ranked set of potential opportunities;
- evidence explaining the rankings;
- the technical approach used;
- key assumptions and limitations.

The final demonstration should show how raw job-market data becomes
actionable business intelligence.
