'use client';

import { useEffect, useState } from 'react';

export default function Home() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/health?XTransformPort=8080')
      .then(r => r.ok ? r.json() : null)
      .then(d => { setData(d); setLoading(false); })
      .catch(() => { setData(null); setLoading(false); });
  }, []);

  const healthy = data?.status === 'healthy';
  const bridge = data?.bridge_healthy;
  const constitution = data?.constitution_ok;

  return (
    <div style={{ minHeight: '100vh', padding: '24px', background: '#0a0a0a', color: '#fafafa' }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 'bold' }}>MetaEngine Dashboard</h1>
        <p style={{ color: '#888', marginBottom: '24px' }}>Constitutionally-safe self-improving AI system</p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px', marginBottom: '24px' }}>
          <div style={{ padding: '16px', border: '1px solid #333', borderRadius: '8px' }}>
            <div style={{ fontSize: '14px', color: '#888', marginBottom: '8px' }}>LLM Bridge</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: bridge ? '#22c55e' : '#ef4444' }} />
              <span style={{ fontSize: '24px', fontWeight: 'bold' }}>{bridge ? 'Online' : 'Offline'}</span>
            </div>
            <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>Port 3031</div>
          </div>

          <div style={{ padding: '16px', border: '1px solid #333', borderRadius: '8px' }}>
            <div style={{ fontSize: '14px', color: '#888', marginBottom: '8px' }}>Constitution</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: constitution ? '#22c55e' : '#ef4444' }} />
              <span style={{ fontSize: '24px', fontWeight: 'bold' }}>{constitution ? 'Enforced' : 'Error'}</span>
            </div>
            <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>12 K0 invariants</div>
          </div>

          <div style={{ padding: '16px', border: '1px solid #333', borderRadius: '8px' }}>
            <div style={{ fontSize: '14px', color: '#888', marginBottom: '8px' }}>System Status</div>
            <div style={{ fontSize: '24px', fontWeight: 'bold' }}>
              {loading ? 'Loading...' : healthy ? 'Healthy' : 'Degraded'}
            </div>
            <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
              {data?.timestamp || 'No data'}
            </div>
          </div>
        </div>

        <div style={{ padding: '16px', border: '1px solid #333', borderRadius: '8px', marginBottom: '24px' }}>
          <h2 style={{ fontSize: '18px', fontWeight: 'bold', marginBottom: '12px' }}>Project Metrics</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px', fontSize: '14px' }}>
            <div>Phases: <strong>63</strong></div>
            <div>Modules: <strong>98</strong></div>
            <div>Tests: <strong>1,517</strong> (0 failures)</div>
            <div>Mechanisms: <strong>126</strong></div>
            <div>Observations: <strong>73</strong></div>
            <div>Graph nodes: <strong>1,756</strong></div>
            <div>Benchmark categories: <strong>7</strong></div>
            <div>Trainers: <strong>6</strong> (RLAIF+PBT+AlphaZero+ES+MARL+RedTeam)</div>
            <div>Attack vectors: <strong>7</strong></div>
            <div>Cloud DB keys: <strong>275</strong></div>
          </div>
        </div>

        <div style={{ padding: '16px', border: '1px solid #333', borderRadius: '8px', marginBottom: '24px' }}>
          <h2 style={{ fontSize: '18px', fontWeight: 'bold', marginBottom: '12px' }}>Constitution K0 Invariants</h2>
          <div style={{ fontSize: '13px', color: '#aaa', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '8px' }}>
            <div>• NO_TRUTH_FROM_RANKING_OR_VOTING</div>
            <div>• PRESERVE_ABSTENTION</div>
            <div>• SEPARATE_GENERATION_AND_PROMOTION</div>
            <div>• NO_EXECUTABLE_SELF_MODIFICATION</div>
            <div>• FROZEN_EVALUATION_CONTRACT</div>
            <div>• MUTATION_REQUIRES_RECEIPT</div>
            <div>• PROVENANCE_PRIMARY_EVIDENCE</div>
            <div>• IMMUTABLE_HISTORY_WITH_SUPERSESSION</div>
            <div>• CANONICAL_NOT_SCIENTIFIC_TRUTH</div>
            <div>• PRIVACY_PERMISSION_FAIL_CLOSED</div>
            <div>• ROLLBACK_RECOVERY_REQUIRED</div>
            <div>• NO_NORMAL_KERNEL_SELF_MUTATION</div>
          </div>
          <div style={{ marginTop: '8px', fontSize: '12px', color: '#666' }}>
            Amendment authority: NOT_IMPLEMENTED (constitution cannot be changed by the system)
          </div>
        </div>

        <div style={{ padding: '16px', border: '1px solid #333', borderRadius: '8px', marginBottom: '24px' }}>
          <h2 style={{ fontSize: '18px', fontWeight: 'bold', marginBottom: '12px' }}>REST API Endpoints</h2>
          <div style={{ fontSize: '13px', color: '#aaa', fontFamily: 'monospace' }}>
            <div>GET  /api/health — System health (bridge + constitution)</div>
            <div>GET  /api/constitution — 12 K0 invariants + amendment authority</div>
            <div>GET  /api/modules — All 98 Python modules with LOC</div>
            <div>GET  /api/state-bus — Accumulated state (126 mechanisms, 73 obs)</div>
            <div>GET  /api/benchmark — Last benchmark results</div>
            <div>POST /api/benchmark/run — Trigger benchmark (async)</div>
            <div>GET  /api/strict-tests — Strict test factory results</div>
            <div>GET  /api/version — Version info</div>
          </div>
        </div>

        <div style={{ textAlign: 'center', fontSize: '12px', color: '#555', padding: '16px' }}>
          <p>MetaEngine v2.3.0-alpha.1 | 63 phases | 1,517 tests | truth_effect=NONE</p>
          <p style={{ marginTop: '4px' }}>
            {data?.timestamp ? `Last health check: ${data.timestamp}` : 'Connect to API on port 8080 for live data'}
          </p>
        </div>
      </div>
    </div>
  );
}
