# RapidSales.ai - AI Pipeline Architecture & Cost Optimisation

## Overview

RapidSales.ai currently uses GPT-4o for all outreach workflows including WhatsApp messages, personalised emails, and AI-generated voice call scripts. While this approach provides strong output quality, it creates major operational challenges at scale.

The platform currently supports around 200 active clients, each running campaigns to 500-2000 leads. As campaign volume grows, the existing architecture becomes expensive, slower, and difficult to monitor.

This document proposes a revised AI pipeline architecture focused on:

- Reducing LLM costs
- Improving response latency
- Adding observability and monitoring
- Increasing reliability through fallback handling
- Keeping the system practical for a small engineering team

---

# Existing System Problems

## 1. High AI Cost

The current system uses GPT-4o for every workflow step:

- WhatsApp generation
- Email generation
- Voice script generation

This causes AI costs to reach approximately 38% of gross revenue.

---

## 2. High Latency

Voice script generation currently averages around 4.2 seconds because every request generates a completely new script using GPT-4o.

---

## 3. No Observability

The platform currently has no proper monitoring system.

The team only discovers failures after clients report issues, which creates operational risk and poor customer experience.

---

## 4. Repeated LLM Calls

Many clients generate very similar voice scripts based on identical industries and product categories.

The current system regenerates these scripts repeatedly instead of reusing previous outputs.

---

# Proposed Architecture

## High-Level Architecture Goals

The revised pipeline focuses on:

- Using smaller models where high intelligence is unnecessary
- Using caching for repeated requests
- Moving heavy processing into asynchronous queues
- Adding observability and alerting
- Maintaining acceptable output quality while significantly reducing cost

---

# Proposed Pipeline Flow

![Proposed Architecture](./diagrams/proposed_pipeline.png)

### Pipeline Steps

1. Lead data enters the outreach system
2. Tasks are pushed into an async queue
3. WhatsApp messages are generated using GPT-4o-mini
4. Emails are generated using GPT-4o-mini
5. Voice scripts use GPT-4o only when required
6. Redis cache checks for reusable voice scripts
7. Responses are logged and monitored
8. Delivery status and failures are tracked through dashboards and alerts

---

# Model Selection Strategy

## WhatsApp Messages → GPT-4o-mini

### Reasoning

WhatsApp messages are:

- Short
- Template-oriented
- Low complexity
- High volume

Using GPT-4o for these messages is unnecessarily expensive.

GPT-4o-mini is sufficient for generating short personalised outreach while significantly reducing token cost and latency.

---

## Emails → GPT-4o-mini

### Reasoning

Emails require slightly better structure and personalisation compared to WhatsApp messages, but they still do not require the full reasoning capabilities of GPT-4o.

GPT-4o-mini provides a strong balance between quality and operational cost.

---

## Voice Call Scripts → GPT-4o

### Reasoning

Voice calls are the most important stage in the outreach pipeline because they directly interact with high-intent leads.

These scripts require:

- Better contextual understanding
- More natural conversation flow
- Dynamic objections handling
- Higher response quality

Because of this, GPT-4o is still justified for this workflow.

---

# Cost Optimisation Analysis

## WhatsApp Workflow

### Current
GPT-4o for all messages

### Proposed
GPT-4o-mini

### Estimated Savings
Approximately 80–90% reduction in token cost for this stage.

### Trade-off
Slight reduction in creativity, but acceptable because WhatsApp outreach is mostly short-form and template-driven.

---

## Email Workflow

### Current
GPT-4o for all emails

### Proposed
GPT-4o-mini

### Estimated Savings
Approximately 70–80% reduction in cost.

### Trade-off
Minor reduction in long-form writing quality, but still acceptable for outbound campaigns.

---

## Voice Script Workflow

### Current
Fresh GPT-4o generation for every request

### Proposed
- GPT-4o only when required
- Redis caching for repeated industry/product combinations

### Estimated Savings
Approximately 30–40% reduction for voice generation costs.

### Trade-off
Some cached scripts may feel slightly repetitive, but this can be controlled with prompt variation and TTL expiration.

---

# Estimated Overall Reduction

The proposed architecture can realistically reduce total LLM cost by approximately:

# 60–75%

while maintaining acceptable output quality and significantly improving scalability.

---

# Async vs Sync Processing

## Async Tasks

The following operations should run asynchronously:

- WhatsApp generation
- Email generation
- Voice script generation
- Bulk campaign processing
- Retry handling

### Reasoning

These workflows operate at high volume and do not require immediate user-facing responses.

Running them asynchronously improves:

- Scalability
- Throughput
- Reliability
- Queue management

### Suggested Tools

- Celery
- Redis Queue
- RabbitMQ

---

## Sync Tasks

The following operations should remain synchronous:

- Dashboard interactions
- Campaign creation
- User authentication
- Manual trigger actions

These actions require immediate feedback to the user.

---

# Caching Strategy

## Redis-Based Cache

Voice script generation is one of the most expensive operations in the system.

Many requests repeat similar combinations such as:

- Healthcare + CRM
- Real Estate + ERP
- FinTech + SaaS

Instead of regenerating scripts every time, the system should cache outputs using:

industry + product_category

as the cache key.

---

## Cache Benefits

- Reduces repeated GPT calls
- Improves response time
- Lowers operational cost
- Reduces API dependency

---

## Cache Expiration (TTL)

Recommended TTL:

24 hours

---

# Fallback Handling

LLM failures should never completely stop the outreach workflow.

The proposed fallback strategy is:

```bash
GPT-4o
↓
GPT-4o-mini
↓
Predefined Template
```

---

## Failure Scenarios Covered

- OpenAI API timeout
- Rate limiting
- Temporary service outage
- Invalid response generation

---

## Benefits

- Higher reliability
- Better client experience
- Reduced workflow interruption
- More resilient production system

---

# Observability & Monitoring

The current platform lacks observability, making debugging and reliability extremely difficult.

The revised architecture introduces structured logging, alerts, and monitoring dashboards.

---

# Logging Strategy

## LLM Layer Logs

Track:

- Request latency
- Token usage
- Model name
- Cost estimation
- Failure reason

---

## Queue Layer Logs

Track:

- Queue delay
- Retry count
- Failed jobs
- Processing duration

---

## Cache Logs

Track:

- Cache hit rate
- Cache miss rate
- Expired keys

---

## Delivery Logs

Track:

- Message delivery success
- Email bounce rate
- Voice call completion status

---

# Alert Conditions

## High Latency Alert

Trigger if:

Average latency > 5 seconds

---

## Failure Rate Alert

Trigger if:

Failure rate > 10%

---

## Cost Spike Alert

Trigger if:

Daily token usage increases abnormally

---

## Queue Backlog Alert

Trigger if:

Pending jobs exceed threshold

---

# AI System Health Dashboard

![Observability Dashboard](./diagrams/observability_dashboard.png)

The dashboard should display the following metrics:

1. Average LLM Latency
2. Total Token Usage
3. API Error Rate
4. Cache Hit Rate
5. Successful Delivery Rate

---

# Engineering Pragmatism

The proposed architecture intentionally avoids overengineering.

The design is:

- Lightweight
- Cost-efficient
- Operationally practical
- Suitable for a startup-scale engineering team

This system can realistically be implemented by a small team of 3 engineers within approximately one month.

---

# Future Improvements

Potential future improvements include:

- Lead scoring before expensive voice calls
- A/B testing for prompts
- Fine-tuned outreach templates
- Better cache invalidation strategies
- Real-time campaign analytics
- Adaptive model routing based on lead quality

---

# Conclusion

The revised architecture focuses on reducing operational cost while improving reliability, scalability, and monitoring.

Instead of using a single expensive model for every task, the system now uses a more practical model allocation strategy combined with asynchronous processing, caching, and observability tooling.

This approach provides a better balance between performance, cost, and engineering maintainability for a growing AI outreach platform.
