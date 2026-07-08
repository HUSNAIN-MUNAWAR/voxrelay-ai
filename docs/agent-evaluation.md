# Agent evaluation

The seeded evaluation suite contains 40 deterministic cases across real estate, clinic booking, emergency plumbing, maintenance, insurance, low-confidence input, consent refusal, booking failures, after-hours calls, restricted topics, repeat customers, interruptions, handoff requests and CRM failure simulation.

Each test case has expected entities, routing, booking/handoff and policy behavior. Evaluation runs store pass/fail evidence and are used by release gates. The local scoring is deterministic and rule-assisted; it must not be interpreted as an LLM accuracy benchmark.
