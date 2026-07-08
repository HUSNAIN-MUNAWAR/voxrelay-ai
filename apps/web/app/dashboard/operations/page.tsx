'use client';
import { useEffect, useState } from 'react';
import { Activity, Database, RadioTower, ServerCog } from 'lucide-react';
import { SectionTitle, Metric, Panel, Badge } from '../../components/ui';
import { LoadingState, ErrorState } from '../../components/states';
import { platformOperations } from '../../lib/api-client';
import { useApiSession } from '../../lib/use-api-session';

export default function OperationsConsole() {
  const { token, loading, error } = useApiSession();
  const [data, setData] = useState<any>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  useEffect(() => { if (!token) return; platformOperations(token).then(r => r.data ? setData(r.data) : setApiError(r.error || 'Operations API unavailable')); }, [token]);
  if (loading) return <LoadingState title="Loading platform operations telemetry" />;
  if (error || apiError) return <ErrorState detail={error || apiError || undefined} />;
  const health = data?.health || {};
  const telemetry = data?.telemetry || {};
  return <><SectionTitle eyebrow="Platform operations" title="Operational reliability console" description="Production-oriented health, stream, worker and queue visibility for the deterministic local reference platform." action={<Badge tone="cyan">API backed</Badge>} />
  <div className="grid gap-4 md:grid-cols-4"><Metric label="API health" value={health.api || 'ok'} icon={<ServerCog size={18}/>}/><Metric label="Database" value={health.database || 'connected'} icon={<Database size={18}/>}/><Metric label="WebSocket" value={health.websocket || 'available'} icon={<RadioTower size={18}/>}/><Metric label="Active calls" value={String(telemetry.active_calls ?? 0)} icon={<Activity size={18}/>}/></div>
  <Panel className="mt-5 p-5"><p className="text-sm font-medium">Traceability boundary</p><p className="mt-2 text-sm leading-6 text-slate-400">Call events, transcript segments, extracted entities, booking attempts, CRM jobs, quality evaluations and audit records can be inspected through the Phase 3 trace endpoint.</p><pre className="mt-4 overflow-auto rounded-xl border border-white/[.08] bg-black/20 p-4 text-xs text-slate-400">{JSON.stringify(data, null, 2)}</pre></Panel></>;
}
