import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, auth } from '../services/api';

export default function AppDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [app, setApp] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionBusy, setActionBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [runBusy, setRunBusy] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [runOutput, setRunOutput] = useState<string | null>(null);

  useEffect(() => {
    if (!auth.isLoggedIn()) {
      navigate('/login');
      return;
    }

    if (!id) return;

    setLoading(true);
    api.getAppDetails(id)
      .then((data) => {
        setApp(data);
        setError(null);
      })
      .catch((err: any) => {
        setError(err?.message ?? 'Failed to load app details');
      })
      .finally(() => setLoading(false));
  }, [id, navigate]);

  const status = app?.status ?? {};
  const health = app?.health ?? {};
  const cli = app?.cli ?? {};
  const processes = status?.processes ?? [];
  const metricCards = useMemo(() => ([
    { label: 'Processes', value: status?.process_count ?? 0 },
    { label: 'Healthy Targets', value: health?.healthy_count ?? 0 },
    { label: 'Degraded Targets', value: health?.degraded_count ?? 0 },
    { label: 'Avg Response', value: health?.avg_response_time_ms != null ? `${health.avg_response_time_ms} ms` : 'n/a' },
  ]), [status, health]);

  const requestBody = useMemo(() => cli?.request_body ?? {}, [cli]);

  const handleAction = async (action: 'start' | 'stop' | 'restart' | 'scale') => {
    if (!id) return;
    setActionBusy(action);
    try {
      const replicas = action === 'scale' ? (status?.process_count ?? 0) + 1 : undefined;
      await api.appAction(id, action, replicas);
      const fresh = await api.getAppDetails(id);
      setApp(fresh);
    } catch (err: any) {
      setError(err?.message ?? `Failed to ${action}`);
    } finally {
      setActionBusy(null);
    }
  };

  const handleRun = async () => {
    if (!id) return;
    setRunBusy(true);
    setRunError(null);
    setRunOutput(null);
    try {
      const response = await api.runApp(id, requestBody);
      setRunOutput(JSON.stringify(response, null, 2));
    } catch (err: any) {
      setRunError(err?.message ?? 'Run failed');
    } finally {
      setRunBusy(false);
    }
  };

  if (loading) {
    return <div style={{ padding: '2rem', textAlign: 'center' }}>Loading...</div>;
  }

  if (!app) {
    return (
      <div style={{ padding: '2rem', maxWidth: '800px', margin: '0 auto' }}>
        <Link to="/dashboard" style={{ color: '#4b5563', textDecoration: 'none' }}>← Back to Dashboard</Link>
        <div style={{ marginTop: '1.5rem', color: '#b91c1c' }}>{error ?? 'App not found'}</div>
      </div>
    );
  }

  const appName = app?.name ?? id;
  const appVersion = app?.version ?? app?.status?.app_version ?? 'unknown';
  const isRegistered = app?.status?.registered ?? false;
  const processStatuses = processes.map((process: any) => process.status);
  let statusLabel = 'Unregistered';
  if (isRegistered) {
    if (processStatuses.some((status: string) => status === 'crashed' || status === 'unhealthy')) {
      statusLabel = 'Degraded';
    } else if (processStatuses.length > 0 && processStatuses.every((status: string) => status === 'stopped')) {
      statusLabel = 'Stopped';
    } else if (processStatuses.some((status: string) => status === 'starting')) {
      statusLabel = 'Starting';
    } else {
      statusLabel = 'Healthy';
    }
  }
  const statusColor = statusLabel === 'Healthy' ? '#10b981' : statusLabel === 'Degraded' ? '#f59e0b' : statusLabel === 'Stopped' ? '#ef4444' : '#6b7280';

  return (
    <div style={{ padding: '2rem', maxWidth: '800px', margin: '0 auto' }}>
      <div style={{ marginBottom: '2rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <Link to="/dashboard" style={{ color: '#4b5563', textDecoration: 'none' }}>← Back to Dashboard</Link>
        <h1 style={{ margin: 0 }}>{appName} <span style={{ fontSize: '1rem', fontWeight: 'normal', color: '#6b7280' }}>v{appVersion}</span></h1>
      </div>

      {error && <div style={{ marginBottom: '1rem', color: '#b91c1c' }}>{error}</div>}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '1.5rem', marginBottom: '2rem' }}>
        <div style={{ backgroundColor: 'white', padding: '1.5rem', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
          <h3 style={{ marginTop: 0, color: '#4b5563' }}>Status</h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <div style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: statusColor }}></div>
            <span style={{ fontSize: '1.25rem', fontWeight: 'bold' }}>{statusLabel}</span>
          </div>
          <div style={{ marginTop: '0.75rem', color: '#6b7280', fontSize: '0.95rem' }}>
            Registered nodes: {status?.process_count ?? 0}
          </div>
        </div>
        <div style={{ backgroundColor: 'white', padding: '1.5rem', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
          <h3 style={{ marginTop: 0, color: '#4b5563' }}>Performance</h3>
          {metricCards.map((metric) => (
            <div key={metric.label} style={{ marginBottom: '0.5rem' }}>
              <strong>{metric.label}:</strong> {metric.value}
            </div>
          ))}
        </div>
      </div>

      <div style={{ backgroundColor: 'white', padding: '1.5rem', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', marginBottom: '2rem' }}>
        <h3 style={{ marginTop: 0 }}>Lifecycle Controls</h3>
        <div style={{ display: 'flex', gap: '1rem' }}>
          <button onClick={() => handleAction('start')} disabled={actionBusy !== null} style={{ backgroundColor: '#10b981', color: 'white', padding: '0.5rem 1rem', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold', opacity: actionBusy ? 0.7 : 1 }}>Start</button>
          <button onClick={() => handleAction('stop')} disabled={actionBusy !== null} style={{ backgroundColor: '#ef4444', color: 'white', padding: '0.5rem 1rem', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold', opacity: actionBusy ? 0.7 : 1 }}>Stop</button>
          <button onClick={() => handleAction('restart')} disabled={actionBusy !== null} style={{ backgroundColor: '#f59e0b', color: 'white', padding: '0.5rem 1rem', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold', opacity: actionBusy ? 0.7 : 1 }}>Restart</button>
          <button onClick={() => handleAction('scale')} disabled={actionBusy !== null} style={{ backgroundColor: '#3b82f6', color: 'white', padding: '0.5rem 1rem', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold', opacity: actionBusy ? 0.7 : 1 }}>Scale Up</button>
        </div>
      </div>

      <div style={{ backgroundColor: '#1f2937', color: '#f3f4f6', padding: '1.5rem', borderRadius: '8px' }}>
        <h3 style={{ marginTop: 0, color: '#f9fafb' }}>Run Access</h3>
        <div style={{ display: 'grid', gap: '1rem' }}>
          <div>
            <div style={{ color: '#9ca3af', fontSize: '0.9rem' }}>Primary run request</div>
            <div style={{ fontFamily: 'monospace', wordBreak: 'break-all' }}>{cli.proxy_curl_command ?? cli.curl_command ?? `curl -sS -X POST http://localhost:8000/v1/apps/${id}/run -H 'Content-Type: application/json' -d '{"raw_email":"Can we reschedule tomorrow's meeting?"}'`}</div>
          </div>
          <div>
            <div style={{ color: '#9ca3af', fontSize: '0.9rem' }}>Request body</div>
            <div style={{ fontFamily: 'monospace', wordBreak: 'break-all' }}>{JSON.stringify(requestBody)}</div>
          </div>
          <div>
            <div style={{ color: '#9ca3af', fontSize: '0.9rem' }}>Run sample</div>
            <button
              onClick={handleRun}
              disabled={runBusy}
              style={{ marginTop: '0.5rem', backgroundColor: '#2563eb', color: 'white', padding: '0.5rem 1rem', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold', opacity: runBusy ? 0.7 : 1 }}
            >
              {runBusy ? 'Running...' : 'Run via Gateway'}
            </button>
            {runError && <div style={{ marginTop: '0.75rem', color: '#fca5a5' }}>{runError}</div>}
            {runOutput && (
              <pre style={{ marginTop: '0.75rem', padding: '0.75rem', backgroundColor: '#0f172a', borderRadius: '6px', color: '#e2e8f0', overflowX: 'auto' }}>{runOutput}</pre>
            )}
          </div>
          <div>
            <div style={{ color: '#9ca3af', fontSize: '0.9rem' }}>Per-node run routes</div>
            {cli.targets?.length > 0 ? (
              cli.targets.map((target: any) => (
                <div key={`${target.artifact_id}-${target.vm_ip}-${target.port}`} style={{ marginTop: '0.5rem' }}>
                  <div style={{ color: '#cbd5e1' }}># {target.artifact_id}</div>
                  <div style={{ fontFamily: 'monospace', wordBreak: 'break-all' }}>{target.run_endpoint}</div>
                  <div style={{ fontFamily: 'monospace', wordBreak: 'break-all', color: '#9ca3af' }}>{target.curl_command}</div>
                </div>
              ))
            ) : (
              <div style={{ color: '#9ca3af' }}>No monitored health targets yet.</div>
            )}
          </div>
        </div>
      </div>

      <div style={{ backgroundColor: 'white', padding: '1.5rem', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', marginTop: '2rem' }}>
        <h3 style={{ marginTop: 0, color: '#4b5563' }}>Running Processes</h3>
        {processes.length > 0 ? (
          <div style={{ display: 'grid', gap: '0.75rem' }}>
            {processes.map((process: any) => (
              <div key={process.process_id} style={{ border: '1px solid #e5e7eb', borderRadius: '6px', padding: '0.75rem' }}>
                <div><strong>{process.artifact_id}</strong> <span style={{ color: '#6b7280' }}>({process.artifact_type})</span></div>
                <div style={{ color: '#6b7280', fontSize: '0.9rem' }}>{process.vm_ip}:{process.port} • {process.status}</div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ color: '#6b7280' }}>No running processes registered for this app.</div>
        )}
      </div>
    </div>
  );
}
