export const activeCalls = [
  { id: 'call-live-418', caller: 'Jordan Williams', queue: 'Clinic Intake', state: 'Booking', duration: '02:18', sentiment: 'Stable', risk: 'None', agent: 'Mira v3' },
  { id: 'call-urgent-204', caller: 'Eleanor Brooks', queue: 'Emergency Dispatch', state: 'Handoff pending', duration: '01:42', sentiment: 'Escalating', risk: 'Emergency', agent: 'Relay v3' },
  { id: 'call-review-200', caller: 'Unknown caller', queue: 'Human Review', state: 'Reasoning', duration: '00:46', sentiment: 'Unclear', risk: 'Low confidence', agent: 'Haven v3' },
];

export const routingRules = [
  { name: 'Emergency escalation', condition: 'Urgency = emergency', priority: 1, destination: 'Emergency Dispatch', fallback: 'Create incident task', tone: 'danger' },
  { name: 'Low-confidence review', condition: 'ASR confidence < 0.65', priority: 2, destination: 'Human Review Queue', fallback: 'Callback task', tone: 'violet' },
  { name: 'Booking failure recovery', condition: 'Booking failed = true', priority: 3, destination: 'Clinic Intake', fallback: 'Scheduler task', tone: 'cyan' },
  { name: 'After-hours callback', condition: 'Business hours = false', priority: 5, destination: 'Next-day callback', fallback: 'Notify sales', tone: 'muted' },
];

export const agentVersions = [
  { version: 'v4', status: 'Approved', pass: '97.5%', latency: '718ms', handoff: '17.2%', note: 'Explicit booking-failure fallback and confirmation language.' },
  { version: 'v3', status: 'Active', pass: '96.0%', latency: '736ms', handoff: '19.0%', note: 'Current production-style deterministic baseline.' },
  { version: 'v2', status: 'Deprecated', pass: '91.2%', latency: '752ms', handoff: '22.4%', note: 'Superseded by strengthened consent and escalation rules.' },
];

export const reviewQueue = [
  { caller: 'Unknown caller', reason: 'Low transcription confidence', score: 52, status: 'Needs review', agent: 'Relay v3', evidence: 'Caller did not provide address or service type.' },
  { caller: 'Eleanor Brooks', reason: 'Emergency routing event', score: 92, status: 'Compliance review', agent: 'Relay v3', evidence: 'Water-leak emergency was routed to a human dispatch team.' },
  { caller: 'Nina Alvarez', reason: 'Restricted-topic transfer', score: 88, status: 'Reviewed', agent: 'Atlas v3', evidence: 'Coverage questions were deferred to licensed claims staff.' },
];

export const providerRows = [
  { name: 'Local deterministic simulator', type: 'Telephony orchestration', status: 'Demo provider', health: 'Healthy', detail: 'Fully working local simulation — no carrier connection.' },
  { name: 'Deepgram-compatible adapter', type: 'STT', status: 'Not configured', health: 'Not tested', detail: 'Optional provider boundary; no credentials stored.' },
  { name: 'ElevenLabs-compatible adapter', type: 'TTS', status: 'Not configured', health: 'Not tested', detail: 'Optional provider boundary; no voice generation invoked.' },
  { name: 'Local mock CRM', type: 'CRM sync', status: 'Demo provider', health: 'Healthy', detail: 'Idempotent mock delivery with retry records.' },
  { name: 'Google Calendar-compatible adapter', type: 'Calendar', status: 'Not configured', health: 'Not tested', detail: 'Local deterministic calendar remains active.' },
];

export const reports = [
  { title: 'Weekly Call Quality Report', date: 'Jul 7, 2026', type: 'Quality', freshness: 'Synthetic demo dataset', status: 'Ready' },
  { title: 'Daily Voice Operations Brief', date: 'Jul 7, 2026', type: 'Operations', freshness: 'Synthetic demo dataset', status: 'Scheduled' },
  { title: 'Escalation and Handoff Report', date: 'Jul 6, 2026', type: 'Routing', freshness: 'Synthetic demo dataset', status: 'Ready' },
];

export const alerts = [
  { title: 'Emergency escalation detected', severity: 'Critical', queue: 'Emergency Dispatch', age: '2m ago', action: 'Open call' },
  { title: 'CRM mock delivery needs retry', severity: 'High', queue: 'Clinic Intake', age: '12m ago', action: 'Retry safely' },
  { title: 'Unreviewed low-confidence call', severity: 'Medium', queue: 'Human Review', age: '24m ago', action: 'Review evidence' },
];
