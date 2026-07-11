/**
 * DashboardCEO.jsx — Dashboard CEO Enterprise (Phase 2)
 * KPIs : CA, commandes, leads, MRR, conversion, appointments
 */
import { useState, useEffect } from "react";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell, Legend,
} from "recharts";

const COLORS = ["#6366f1", "#22d3ee", "#f59e0b", "#10b981", "#ef4444"];

function KPICard({ title, value, sub, trend, icon }) {
  const isUp = trend >= 0;
  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-gray-500">{title}</span>
        <span className="text-2xl">{icon}</span>
      </div>
      <div className="text-3xl font-bold text-gray-800">{value}</div>
      {sub && <div className="text-xs text-gray-400">{sub}</div>}
      {trend !== undefined && (
        <div className={`text-sm font-semibold ${isUp ? "text-emerald-500" : "text-red-500"}`}>
          {isUp ? "▲" : "▼"} {Math.abs(trend)}% vs période précédente
        </div>
      )}
    </div>
  );
}

function SectionTitle({ title, subtitle }) {
  return (
    <div className="mb-4">
      <h2 className="text-lg font-bold text-gray-800">{title}</h2>
      {subtitle && <p className="text-sm text-gray-400">{subtitle}</p>}
    </div>
  );
}

export default function DashboardCEO() {
  const [data, setData] = useState(null);
  const [period, setPeriod] = useState(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    const token = localStorage.getItem("access_token") || "";
    fetch(`/api/v1/dashboard-enterprise/ceo?period_days=${period}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [period]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-10 w-10 border-4 border-indigo-500 border-t-transparent" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 bg-red-50 rounded-xl text-red-600">
        Erreur chargement dashboard CEO : {error}
      </div>
    );
  }

  const statusData = data?.orders?.by_status
    ? Object.entries(data.orders.by_status).map(([name, value]) => ({ name, value }))
    : [];

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900">Dashboard CEO</h1>
          <p className="text-sm text-gray-400 mt-1">Vue exécutive — Performance Business</p>
        </div>
        <div className="flex gap-2">
          {[7, 30, 90].map((d) => (
            <button
              key={d}
              onClick={() => setPeriod(d)}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition ${
                period === d
                  ? "bg-indigo-600 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {d}j
            </button>
          ))}
        </div>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <KPICard
          title="Chiffre d'affaires"
          value={`${(data?.revenue?.current || 0).toLocaleString()} TND`}
          sub={`MRR : ${(data?.mrr_tnd || 0).toLocaleString()} TND`}
          trend={data?.revenue?.change_pct}
          icon="💰"
        />
        <KPICard
          title="Commandes"
          value={(data?.orders?.current || 0).toLocaleString()}
          sub={`Valeur moy. : ${(data?.avg_order_value_tnd || 0).toFixed(2)} TND`}
          trend={data?.orders?.change_pct}
          icon="📦"
        />
        <KPICard
          title="Nouveaux Leads"
          value={(data?.leads?.current || 0).toLocaleString()}
          trend={data?.leads?.change_pct}
          icon="🎯"
        />
        <KPICard
          title="Conversion"
          value={`${data?.conversion_rate_pct || 0}%`}
          sub={`Rendez-vous : ${data?.appointments || 0}`}
          icon="📈"
        />
      </div>

      {/* Breakdown Statut Commandes */}
      {statusData.length > 0 && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 mb-6">
          <SectionTitle title="Répartition commandes par statut" />
          <div className="flex flex-wrap gap-6 items-center">
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={statusData}
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  dataKey="value"
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                >
                  {statusData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Metrics Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-gradient-to-br from-indigo-500 to-indigo-700 text-white rounded-2xl p-5">
          <div className="text-sm opacity-75 mb-1">MRR (30j)</div>
          <div className="text-3xl font-bold">{(data?.mrr_tnd || 0).toLocaleString()} TND</div>
        </div>
        <div className="bg-gradient-to-br from-emerald-500 to-emerald-700 text-white rounded-2xl p-5">
          <div className="text-sm opacity-75 mb-1">Valeur Moy. Commande</div>
          <div className="text-3xl font-bold">{(data?.avg_order_value_tnd || 0).toFixed(2)} TND</div>
        </div>
        <div className="bg-gradient-to-br from-amber-500 to-amber-700 text-white rounded-2xl p-5">
          <div className="text-sm opacity-75 mb-1">Taux Conversion</div>
          <div className="text-3xl font-bold">{data?.conversion_rate_pct || 0}%</div>
        </div>
      </div>
    </div>
  );
}
