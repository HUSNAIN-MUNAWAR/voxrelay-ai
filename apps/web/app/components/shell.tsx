'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import {
  Activity,
  Bell,
  Bot,
  CalendarDays,
  ChevronDown,
  Command,
  FileBarChart2,
  Gauge,
  Headphones,
  KeyRound,
  LayoutDashboard,
  LockKeyhole,
  Menu,
  Network,
  PhoneCall,
  RadioTower,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Users,
  Waves,
  X,
} from 'lucide-react';
import { Badge, cn } from './ui';

const primaryNavigation = [
  ['/dashboard', 'Command center', LayoutDashboard],
  ['/dashboard/live', 'Live call console', Waves],
  ['/dashboard/supervisor', 'Supervisor console', RadioTower],
  ['/dashboard/calls', 'Calls inbox', PhoneCall],
  ['/dashboard/review', 'Review & quality', Headphones],
  ['/dashboard/leads', 'Leads & CRM', Users],
  ['/dashboard/calendar', 'Scheduling ops', CalendarDays],
] as const;

const controlNavigation = [
  ['/dashboard/agents', 'Agent governance', Bot],
  ['/dashboard/quality', 'Evaluation center', ShieldCheck],
  ['/dashboard/queues', 'Queue operations', Activity],
  ['/dashboard/routing', 'Routing policies', Network],
  ['/dashboard/analytics', 'Analytics & forecast', Gauge],
  ['/dashboard/reports', 'Reporting center', FileBarChart2],
  ['/dashboard/providers', 'Provider operations', SlidersHorizontal],
  ['/dashboard/governance', 'Privacy & compliance', LockKeyhole],
  ['/dashboard/security', 'Security center', KeyRound],
] as const;

const commandItems = [
  ['Open Live Call Console', '/dashboard/live'],
  ['Open Supervisor Console', '/dashboard/supervisor'],
  ['Review High-Risk Calls', '/dashboard/review'],
  ['Create Voice Agent', '/dashboard/agents'],
  ['Open Agent Evaluation', '/dashboard/quality'],
  ['Open Leads', '/dashboard/leads'],
  ['Open Calendar', '/dashboard/calendar'],
  ['Open Queue Operations', '/dashboard/queues'],
  ['Open Compliance Center', '/dashboard/governance'],
  ['Generate Report', '/dashboard/reports'],
  ['Open Provider Operations', '/dashboard/providers'],
] as const;

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [workspaceOpen, setWorkspaceOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [query, setQuery] = useState('');

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setPaletteOpen((open) => !open);
      }
      if (event.key === 'Escape') setPaletteOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const filteredCommands = commandItems.filter(([label]) => label.toLowerCase().includes(query.toLowerCase()));

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[278px_1fr]">
      <aside className={cn('border-b border-white/[.08] bg-[#0a0c19]/95 px-4 py-5 backdrop-blur-xl lg:fixed lg:inset-y-0 lg:w-[278px] lg:border-b-0 lg:border-r', mobileOpen ? 'block' : 'hidden lg:block')}>
        <div className="flex items-center justify-between px-3">
          <Link href="/" className="flex items-center gap-3" onClick={() => setMobileOpen(false)}>
            <span className="relative grid h-10 w-10 place-items-center rounded-xl bg-violet-400/15 text-violet-100 ring-1 ring-violet-300/25">
              <Waves size={20} />
              <span className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full bg-lime-300 shadow-[0_0_12px_rgba(199,250,115,.9)]" />
            </span>
            <span>
              <strong className="block text-sm tracking-tight">VoxRelay <em className="not-italic text-violet-300">AI</em></strong>
              <small className="text-[10px] tracking-[.16em] text-slate-500">VOICE OPERATIONS</small>
            </span>
          </Link>
          <button className="text-slate-400 lg:hidden" onClick={() => setMobileOpen(false)} aria-label="Close navigation"><X size={18} /></button>
        </div>

        <button onClick={() => setWorkspaceOpen(!workspaceOpen)} className="relative mt-6 flex w-full items-center justify-between rounded-xl border border-white/[.08] bg-white/[.025] px-3 py-3 text-left transition hover:bg-white/[.05]">
          <span><span className="block text-[10px] uppercase tracking-[.14em] text-slate-500">Workspace</span><span className="mt-1 block text-sm text-slate-100">Northstar Property Group</span></span>
          <ChevronDown size={15} className={cn('text-slate-500 transition', workspaceOpen && 'rotate-180')} />
          {workspaceOpen && <span className="absolute left-0 right-0 top-[calc(100%+8px)] z-30 overflow-hidden rounded-xl border border-white/[.1] bg-[#111426] p-1 shadow-2xl">
            {['Northstar Property Group', 'CareBridge Clinics', 'Apex Home Services'].map((name, index) => <button key={name} onClick={() => setWorkspaceOpen(false)} className={cn('block w-full rounded-lg px-3 py-2 text-left text-xs transition hover:bg-white/[.06]', index === 0 ? 'text-violet-100' : 'text-slate-400')}>{name}<span className="float-right text-[10px] text-slate-600">{index === 0 ? 'Admin' : 'Demo'}</span></button>)}
          </span>}
        </button>

        <button onClick={() => setPaletteOpen(true)} className="mt-3 flex w-full items-center gap-2 rounded-xl border border-white/[.08] bg-white/[.025] px-3 py-2.5 text-left text-xs text-slate-500 transition hover:border-violet-300/25 hover:text-slate-300">
          <Search size={14} /><span className="flex-1">Search operations…</span><kbd className="rounded border border-white/10 px-1.5 py-0.5 text-[10px]">⌘ K</kbd>
        </button>

        <nav className="mt-5 space-y-1">
          <p className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-[.15em] text-slate-600">Operations</p>
          {primaryNavigation.map(([href, label, Icon]) => <NavItem key={href} href={href} label={label} Icon={Icon} active={path === href} onClick={() => setMobileOpen(false)} />)}
          <p className="mt-5 px-3 pb-2 text-[10px] font-semibold uppercase tracking-[.15em] text-slate-600">Control plane</p>
          {controlNavigation.map(([href, label, Icon]) => <NavItem key={href} href={href} label={label} Icon={Icon} active={path === href} onClick={() => setMobileOpen(false)} />)}
        </nav>

        <div className="mt-6 rounded-2xl border border-violet-300/15 bg-violet-400/[.055] p-3">
          <p className="kicker text-violet-300">Deterministic demo</p>
          <p className="mt-2 text-xs leading-5 text-slate-400">Provider adapters, calls, contacts, metrics and delivery outcomes are clearly marked as local synthetic behavior.</p>
          <Badge tone="violet"><span className="status-dot" /> Demo mode active</Badge>
        </div>

        <div className="mt-5 flex items-center justify-between rounded-xl border border-white/[.08] p-3">
          <span className="flex items-center gap-2 text-xs text-slate-300"><span className="grid h-7 w-7 place-items-center rounded-full bg-cyan-300/15 text-[10px] text-cyan-100">DA</span>Demo Admin</span><ChevronDown size={15} className="text-slate-500" />
        </div>
      </aside>

      <main className="min-w-0 px-4 py-5 lg:col-start-2 lg:px-8 lg:py-7">
        <header className="mb-7 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <button className="grid h-9 w-9 place-items-center rounded-xl border border-white/[.08] bg-white/[.03] text-slate-300 lg:hidden" onClick={() => setMobileOpen(true)} aria-label="Open navigation"><Menu size={17} /></button>
            <div className="hidden items-center gap-2 text-xs text-slate-500 md:flex"><span className="status-dot" />Queue SLA healthy <span className="mx-2 text-white/15">/</span>PII controls active <span className="mx-2 text-white/15">/</span>Local providers</div>
            <div className="md:hidden"><Badge tone="lime">Control plane healthy</Badge></div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => setPaletteOpen(true)} className="hidden items-center gap-2 rounded-xl border border-white/[.08] bg-white/[.03] px-3 py-2 text-xs text-slate-400 md:flex"><Command size={14} />Command palette</button>
            <Link href="/dashboard/search" className="grid h-9 w-9 place-items-center rounded-xl border border-white/[.08] bg-white/[.03] text-slate-300" aria-label="Search"><Search size={17} /></Link>
            <button className="relative grid h-9 w-9 place-items-center rounded-xl border border-white/[.08] bg-white/[.03] text-slate-300" aria-label="Notifications"><Bell size={17} /><span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-violet-300" /></button>
          </div>
        </header>
        {children}
      </main>

      {paletteOpen && <div className="fixed inset-0 z-50 grid place-items-start bg-[#050611]/70 p-4 pt-[12vh] backdrop-blur-sm" onMouseDown={() => setPaletteOpen(false)}>
        <div className="w-full max-w-xl overflow-hidden rounded-2xl border border-violet-300/20 bg-[#111426] shadow-[0_25px_90px_rgba(0,0,0,.55)]" onMouseDown={(event) => event.stopPropagation()}>
          <div className="flex items-center gap-3 border-b border-white/[.07] px-4 py-3"><Command size={17} className="text-violet-200" /><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search calls, leads, agents, reports, or actions…" className="w-full bg-transparent text-sm text-slate-100 outline-none placeholder:text-slate-600" /><kbd className="text-[10px] text-slate-600">ESC</kbd></div>
          <div className="p-2"><p className="px-2 py-2 text-[10px] font-semibold uppercase tracking-[.15em] text-slate-600">Suggested actions</p>{filteredCommands.map(([label, href], index) => <button key={label} onClick={() => { setPaletteOpen(false); router.push(href); }} className={cn('flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left transition hover:bg-white/[.06]', index === 0 && 'bg-violet-300/[.07]')}><span className="grid h-7 w-7 place-items-center rounded-lg bg-white/[.05] text-violet-200"><Command size={14} /></span><span className="flex-1 text-sm text-slate-200">{label}</span><span className="text-xs text-slate-600">↵</span></button>)}</div>
          <div className="border-t border-white/[.07] px-4 py-2 text-[10px] text-slate-600">Tenant-scoped navigation only. Search results never cross workspace boundaries.</div>
        </div>
      </div>}
    </div>
  );
}

function NavItem({ href, label, Icon, active, onClick }: { href: string; label: string; Icon: typeof Waves; active: boolean; onClick: () => void }) {
  return <Link href={href} onClick={onClick} className={cn('group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition', active ? 'bg-violet-400/13 text-violet-100 ring-1 ring-violet-300/15' : 'text-slate-400 hover:bg-white/[.04] hover:text-white')}><Icon size={17} className={active ? 'text-cyan-200' : 'text-slate-500 group-hover:text-slate-300'} /><span className="flex-1">{label}</span>{href === '/dashboard/live' && <span className="status-dot" />}</Link>;
}
