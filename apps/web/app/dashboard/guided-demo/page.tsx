import { BookOpenCheck, ClipboardCheck, RadioTower, ShieldCheck, WandSparkles } from 'lucide-react';
import { Badge, Panel, SectionTitle } from '../../components/ui';
const journeys = [
  ['Clinic Booking With Reliable CRM Sync', 'Start clinic simulation, observe consent and extraction, create booking, simulate CRM failure, retry idempotently, generate report.', RadioTower],
  ['Emergency Plumbing Escalation', 'Detect emergency routing, transfer to emergency team, create urgent follow-up, inspect audit trail.', ShieldCheck],
  ['Agent Release Governance', 'Create version, run evaluation, submit, approve, stage, activate and inspect audit history.', WandSparkles],
  ['Quality Review and Coaching', 'Open low-confidence call, inspect evidence, flag issue, create coaching task and mark training candidate.', ClipboardCheck],
  ['Executive Operations Brief', 'Review operations metrics, provider warning, watchlist and export a local PDF report.', BookOpenCheck],
] as const;
export default function GuidedDemo(){return <><SectionTitle eyebrow="Client presentation mode" title="Guided demo journeys" description="Dismissible, practical storylines for showing the end-to-end deterministic local platform without pretending external providers are active." action={<Badge tone="violet">Synthetic data only</Badge>} /><div className="grid gap-4 lg:grid-cols-2">{journeys.map(([title, detail, Icon], index)=><Panel key={title} className="p-5"><div className="flex gap-4"><div className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl border border-violet-300/20 bg-violet-300/[.08] text-violet-100"><Icon size={20}/></div><div><p className="kicker">Demo {index+1}</p><h2 className="mt-2 text-lg font-semibold">{title}</h2><p className="mt-2 text-sm leading-6 text-slate-400">{detail}</p><button className="mt-4 rounded-xl border border-cyan-300/20 bg-cyan-300/[.06] px-3 py-2 text-xs font-medium text-cyan-100">Open journey checklist</button></div></div></Panel>)}</div></>}
