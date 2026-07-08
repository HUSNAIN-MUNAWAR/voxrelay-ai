
'use client';
import { AlertTriangle, Loader2, LockKeyhole, ServerCrash } from 'lucide-react';
import { Panel } from './ui';

export function LoadingState({ title = 'Loading live operational data' }: { title?: string }) {
  return <Panel className="p-6"><div className="flex items-center gap-3 text-sm text-slate-300"><Loader2 className="animate-spin text-cyan-200" size={18}/>{title}</div><div className="mt-5 grid gap-3 md:grid-cols-3">{[0,1,2].map(i => <div key={i} className="h-24 animate-pulse rounded-xl border border-white/[.06] bg-white/[.025]" />)}</div></Panel>;
}
export function ErrorState({ title = 'Operational data is unavailable', detail, requestId }: { title?: string; detail?: string; requestId?: string }) {
  return <Panel className="border-amber-300/20 bg-amber-300/[.04] p-6"><div className="flex gap-3"><ServerCrash className="text-amber-200" size={20}/><div><p className="font-medium text-amber-100">{title}</p><p className="mt-2 text-sm leading-6 text-slate-400">{detail || 'The local FastAPI service may not be running. The UI does not hide this failure; start the API or use the deterministic demo fallback.'}</p>{requestId && <p className="mt-2 text-xs text-slate-500">Request ID: {requestId}</p>}</div></div></Panel>;
}
export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <Panel className="p-6 text-center"><AlertTriangle className="mx-auto text-slate-500" size={22}/><p className="mt-3 font-medium">{title}</p><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500">{detail}</p></Panel>;
}
export function PermissionState({ permission }: { permission: string }) {
  return <Panel className="p-6"><div className="flex gap-3"><LockKeyhole className="text-violet-200" size={20}/><div><p className="font-medium">Permission required</p><p className="mt-2 text-sm text-slate-500">This action requires <code>{permission}</code>. Request approval from an Organization Admin.</p></div></div></Panel>;
}
