// autocommerce-app/src/pages/LoyaltyIA.jsx — Plan E3 page.
import React, { useEffect, useState } from "react";
import { api } from "../api";

const SEGMENT_COLOR = {
  champions: "#16a34a",
  loyal: "#2563eb",
  at_risk: "#f59e0b",
  hibernating: "#64748b",
  new: "#a855f7",
};

export default function LoyaltyIA() {
  const [segments, setSegments] = useState([]);
  const [models, setModels] = useState([]);
  const [churnPreview, setChurnPreview] = useState([]);
  const [recoPreview, setRecoPreview] = useState([]);
  const [newSegment, setNewSegment] = useState({ name: "", description: "", color: "#2563eb",
    segment_type: "rfm", rules: { min_lifetime: 0, max_recency_days: 365 } });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function load() {
    setBusy(true); setError(null);
    try {
      const [s, m] = await Promise.all([
        api.get("/loyalty-ia/segments"),
        api.get("/loyalty-ia/models"),
      ]);
      setSegments(Array.isArray(s) ? s : []);
      setModels(Array.isArray(m) ? m : []);
    } catch (e) { setError(String(e?.message || e)); }
    finally { setBusy(false); }
  }
  useEffect(() => { load(); }, []);

  async function createSegment() {
    setBusy(true);
    try {
      await api.post("/loyalty-ia/segments", newSegment);
      setNewSegment({ ...newSegment, name: "" });
      await load();
    } catch (e) { setError(String(e?.message || e)); }
    finally { setBusy(false); }
  }

  async function runChurnDemo() {
    setBusy(true); setError(null);
    try {
      const now = new Date();
      const items = [
        { customer_id: 1, days_since_last_reward: 12, support_tickets_30d: 0,
          avg_orders_per_month: 4, orders: [{ at: now.toISOString(), total: 199.9 }] },
        { customer_id: 2, days_since_last_reward: 40, support_tickets_30d: 1,
          avg_orders_per_month: 1.5, orders: [{ at: new Date(now - 50 * 86400e3).toISOString(), total: 49 }] },
        { customer_id: 3, days_since_last_reward: 90, support_tickets_30d: 3,
          avg_orders_per_month: 0.3, orders: [{ at: new Date(now - 120 * 86400e3).toISOString(), total: 19 }] },
      ];
      const r = await api.post("/loyalty-ia/churn/bulk", items);
      setChurnPreview(r.results || []);
    } catch (e) { setError(String(e?.message || e)); }
    finally { setBusy(false); }
  }

  async function runRecoDemo() {
    setBusy(true); setError(null);
    try {
      const r = await api.post("/loyalty-ia/recommend", {
        customer_purchase_skus: ["SKU-A", "SKU-B"],
        cooccurrence: {
          "SKU-A": { "SKU-X": 7, "SKU-Y": 3 },
          "SKU-B": { "SKU-X": 5, "SKU-Z": 9 },
        },
        catalog_skus: ["SKU-A", "SKU-B", "SKU-X", "SKU-Y", "SKU-Z"],
        out_of_stock: [],
        top_n: 3,
        customer_id: 42,
      });
      setRecoPreview(r.recommendations || []);
    } catch (e) { setError(String(e?.message || e)); }
    finally { setBusy(false); }
  }

  async function promote(modelId) {
    setBusy(true);
    try {
      await api.post(`/loyalty-ia/models/${modelId}/promote`, {});
      await load();
    } catch (e) { setError(String(e?.message || e)); }
    finally { setBusy(false); }
  }

  return (
    <div className="p-6 space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Loyalty IA</h1>
        <div className="flex gap-2">
          <button onClick={runChurnDemo} disabled={busy}
            className="px-3 py-1.5 text-sm bg-rose-600 text-white rounded">
            Démo churn
          </button>
          <button onClick={runRecoDemo} disabled={busy}
            className="px-3 py-1.5 text-sm bg-emerald-600 text-white rounded">
            Démo reco
          </button>
        </div>
      </header>

      {error && <div className="bg-red-50 text-red-700 p-2 rounded">{error}</div>}

      <section className="border rounded p-4 space-y-3">
        <h2 className="font-semibold">Segmentation (RFM + règles)</h2>
        <div className="grid grid-cols-4 gap-2">
          <input className="border rounded px-2 py-1 text-sm col-span-2"
            placeholder="Nom du segment"
            value={newSegment.name}
            onChange={(e) => setNewSegment({ ...newSegment, name: e.target.value })} />
          <select className="border rounded px-2 py-1 text-sm"
            value={newSegment.segment_type}
            onChange={(e) => setNewSegment({ ...newSegment, segment_type: e.target.value })}>
            <option value="rfm">RFM</option>
            <option value="behavioral">Behavioral</option>
            <option value="lifecycle">Lifecycle</option>
            <option value="custom">Custom</option>
          </select>
          <input className="border rounded px-2 py-1 text-sm w-16"
            value={newSegment.color}
            onChange={(e) => setNewSegment({ ...newSegment, color: e.target.value })} />
        </div>
        <button disabled={busy || !newSegment.name} onClick={createSegment}
          className="px-3 py-1 bg-blue-600 text-white text-sm rounded disabled:opacity-50">
          Créer le segment
        </button>
        <div className="flex flex-wrap gap-2 mt-2">
          {segments.length === 0
            ? <p className="text-xs text-slate-500">Aucun segment.</p>
            : segments.map((s) => (
                <div key={s.id} className="px-3 py-1 rounded text-sm text-white"
                  style={{ backgroundColor: s.color || "#475569" }}>
                  {s.name} <span className="opacity-70 ml-1">({s.segment_type})</span>
                </div>
              ))}
        </div>
      </section>

      <section className="grid md:grid-cols-2 gap-6">
        <div className="border rounded p-4">
          <h2 className="font-semibold mb-2">Recommandations personnalisées</h2>
          {recoPreview.length === 0
            ? <p className="text-xs text-slate-500">Cliquez "Démo reco".</p>
            : <ul className="divide-y">
                {recoPreview.map((r, i) => (
                  <li key={i} className="py-1 flex justify-between">
                    <span>{r.sku}</span>
                    <span className="text-xs text-slate-500">score {r.score}</span>
                  </li>
                ))}
              </ul>}
        </div>
        <div className="border rounded p-4">
          <h2 className="font-semibold mb-2">Détection churn</h2>
          {churnPreview.length === 0
            ? <p className="text-xs text-slate-500">Cliquez "Démo churn".</p>
            : <ul className="divide-y">
                {churnPreview.map((c) => (
                  <li key={c.customer_id} className="py-2">
                    <div className="text-sm">
                      Client {c.customer_id} —{" "}
                      <span className="font-semibold"
                        style={{ color: c.risk_band === "high" ? "#dc2626"
                              : c.risk_band === "medium" ? "#f59e0b"
                              : "#16a34a" }}>
                        {c.risk_band} ({c.score})
                      </span>
                    </div>
                    <div className="text-xs text-slate-500">
                      RFM: {c.drivers.rfm_segment} · recency {c.drivers.recency_days}j
                    </div>
                  </li>
                ))}
              </ul>}
        </div>
      </section>

      <section className="border rounded p-4">
        <h2 className="font-semibold mb-2">Model Registry</h2>
        {models.length === 0
          ? <p className="text-xs text-slate-500">Aucun modèle.</p>
          : <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-500">
                  <th>Nom</th><th>Version</th><th>État</th><th>Métrique</th><th></th>
                </tr>
              </thead>
              <tbody>
                {models.map((m) => (
                  <tr key={m.id} className="border-t">
                    <td>{m.name}</td>
                    <td>{m.version}</td>
                    <td>
                      <span className={`text-xs px-2 rounded ${
                        m.state === "production" ? "bg-emerald-200 text-emerald-900"
                        : m.state === "archived" ? "bg-slate-200 text-slate-700"
                        : "bg-amber-200 text-amber-900"
                      }`}>
                        {m.state}
                      </span>
                    </td>
                    <td className="text-xs text-slate-500">
                      {JSON.stringify(m.metrics || {}).slice(0, 60)}
                    </td>
                    <td>
                      {m.state !== "production" && (
                        <button onClick={() => promote(m.id)}
                          className="text-xs px-2 py-1 bg-emerald-600 text-white rounded">
                          Promouvoir
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>}
      </section>
    </div>
  );
}
