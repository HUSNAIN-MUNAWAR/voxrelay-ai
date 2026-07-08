# Voice state machine

The simulation persists meaningful transitions as call events. The local simulator intentionally does not emulate a carrier connection; it demonstrates the lifecycle and control surfaces.

```mermaid
stateDiagram-v2
  [*] --> Queued
  Queued --> Ringing
  Ringing --> Connected
  Connected --> ConsentPending
  ConsentPending --> Listening: consent captured
  ConsentPending --> HandoffPending: consent declined / policy
  Listening --> Reasoning
  Reasoning --> Speaking
  Speaking --> CollectingData
  CollectingData --> Booking
  CollectingData --> HandoffPending
  Booking --> WrappingUp
  HandoffPending --> HumanTakeover
  HumanTakeover --> WrappingUp
  WrappingUp --> Completed
  Queued --> Abandoned
  Connected --> Failed
```

A transcript segment, extraction event, booking event, handoff event, alert and audit record can be attached to a transition. Emergency and restricted-topic conditions are never silently ignored; the local routing policy creates visible escalation artifacts.
