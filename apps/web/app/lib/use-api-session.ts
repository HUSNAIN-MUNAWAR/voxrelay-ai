
'use client';

import { useEffect, useState } from 'react';
import { login, type SessionState } from './api-client';

export function useApiSession(email = 'admin@voxrelay.demo') {
  const [session, setSession] = useState<SessionState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let cancelled = false;
    login(email).then((result) => {
      if (cancelled) return;
      if (result.data) { setSession(result.data); setError(null); }
      else setError(result.error || 'Demo API unavailable');
      setLoading(false);
    });
    return () => { cancelled = true; };
  }, [email]);
  return { session, token: session?.accessToken || '', loading, error, setSession };
}
