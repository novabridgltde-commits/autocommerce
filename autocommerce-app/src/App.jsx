// src/App.jsx
import CookieConsentBanner from './components/CookieConsentBanner';
import PrivacyPolicy from './pages/PrivacyPolicy';
import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, NavLink, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { StoreProvider, useStore } from './context/StoreContext';
import { ToastProvider } from './context/ToastContext';
import Auth from './pages/Auth';
import Dashboard from './pages/Dashboard';
import Products from './pages/Products';
import Orders from './pages/Orders';
import Conversations from './pages/Conversations';
import Settings from './pages/Settings';
import SuperAdmin from './pages/SuperAdmin';
import Landing from './pages/Landing';
import Appointments from './pages/Appointments';
import StockSources from './pages/StockSources';
import SocialBroadcast from './pages/SocialBroadcast';
import StorefrontPageV2 from './pages/StorefrontPageV2';
import BusinessSetup from './pages/BusinessSetup';
import MyStorefront from './pages/MyStorefront';
import PaymentLinks from './pages/PaymentLinks';
import Promotions from './pages/Promotions';
import PredictiveRestocking from './pages/PredictiveRestocking';
import LoyaltyIA from './pages/LoyaltyIA';
import VisualBuilder from './pages/VisualBuilder';
import B2BPortal from './pages/B2BPortal';
import ResetPassword from './pages/ResetPassword';
import LanguageSwitcher from './components/LanguageSwitcher';

/* ── Navigation items (traduits dynamiquement) ────────────────────────────── */
function useNavItems(role) {
  const { t } = useTranslation();

  const ADMIN_NAV = [
    { path: '/dashboard',        label: t('nav_items.dashboard') },
    { path: '/products',         label: t('nav_items.products') },
    { path: '/orders',           label: t('nav_items.orders') },
    { path: '/appointments',     label: t('nav_items.appointments') },
    { path: '/conversations',    label: t('nav_items.conversations') },
    { path: '/social-broadcast', label: t('nav_items.social_broadcast') },
    { path: '/payment-links',    label: t('nav_items.payment_links') },
    { path: '/promotions',       label: t('nav_items.promotions') },
    { path: '/visual-builder',   label: t('nav_items.visual_builder') },
    { path: '/restocking',       label: t('nav_items.predictive_restocking') },
    { path: '/loyalty-ia',       label: t('nav_items.loyalty_ia') },
    { path: '/b2b-portal',       label: t('nav_items.b2b_portal') },
    { path: '/my-storefront',     label: t('nav_items.my_storefront') },
    { path: '/settings',         label: t('nav_items.settings') },
  ];

  const SUPER_ADMIN_NAV = [
    { path: '/super-admin', label: t('nav_items.super_admin') },
  ];

  return role === 'super_admin' ? SUPER_ADMIN_NAV : ADMIN_NAV;
}

function FullScreenLoader() {
  const { t } = useTranslation();
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 text-gray-600 font-semibold">
      {t('common.loading')}
    </div>
  );
}

function Layout() {
  const { isAuthenticated, role, logout, authReady } = useStore();
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const isRTL = i18n.language === 'ar';
  const [sidebarOpen, setSidebarOpen] = React.useState(false);
  const navItems = useNavItems(role);

  if (!authReady) return <FullScreenLoader />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div
      className="min-h-screen bg-gray-50 flex flex-col lg:flex-row"
      dir={isRTL ? 'rtl' : 'ltr'}
    >
      {/* Mobile top bar */}
      <div className="lg:hidden bg-white border-b border-gray-100 px-4 py-3 flex items-center justify-between sticky top-0 z-50">
        <div className="flex items-center gap-2">
          <span className="text-2xl">🛍️</span>
          <p className="font-bold text-gray-900 text-sm">AutoCommerce</p>
        </div>
        <div className="flex items-center gap-2">
          <LanguageSwitcher variant="compact" />
          <button onClick={() => setSidebarOpen(!sidebarOpen)} className="text-gray-600 text-xl">☰</button>
        </div>
      </div>

      {/* Sidebar */}
      <aside
        className={`fixed lg:static inset-y-0 ${isRTL ? 'right-0' : 'left-0'} w-64 bg-white border-${isRTL ? 'l' : 'r'} border-gray-100 flex flex-col shadow-lg lg:shadow-sm z-40 transform transition-transform lg:translate-x-0 ${sidebarOpen ? 'translate-x-0' : isRTL ? 'translate-x-full' : '-translate-x-full'}`}
      >
        <div className="p-4 lg:p-6 border-b border-gray-100">
          <div className="flex items-center gap-2 lg:gap-3">
            <span className="text-2xl lg:text-3xl">🛍️</span>
            <div>
              <p className="font-bold text-gray-900 text-xs lg:text-sm">AutoCommerce</p>
              <p className="text-[9px] lg:text-[10px] font-bold text-gray-400 uppercase">V25</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-3 lg:p-4 space-y-1 overflow-y-auto">
          {navItems.map(({ path, label }) => (
            <NavLink
              key={path}
              to={path}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-2 lg:gap-3 px-3 lg:px-4 py-2 lg:py-3 rounded-lg text-xs lg:text-sm font-bold transition-all ${
                  isActive
                    ? path === '/social-broadcast'
                      ? 'bg-gradient-to-r from-violet-600 to-pink-500 text-white shadow-md'
                      : 'bg-gray-900 text-white'
                    : path === '/social-broadcast'
                      ? 'text-violet-600 hover:bg-violet-50 hover:text-violet-700'
                      : 'text-gray-500 hover:bg-gray-50 hover:text-gray-900'
                }`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="p-3 lg:p-4 border-t border-gray-100">
          {/* Language switcher in sidebar */}
          <div className="mb-3">
            <LanguageSwitcher variant="sidebar" />
          </div>
          <div className="mb-3 px-3 py-2 bg-gray-50 rounded-lg">
            <p className="text-[9px] font-bold text-gray-400 uppercase">{t('sidebar.role')}</p>
            <p className="text-xs font-bold text-gray-700 capitalize">{role?.replace('_', ' ')}</p>
          </div>
          <button
            onClick={handleLogout}
            className="w-full text-left px-3 py-2 rounded-lg text-xs lg:text-sm text-red-600 hover:bg-red-50 font-bold transition-colors"
          >
            {t('sidebar.logout')}
          </button>
        </div>
      </aside>

      {sidebarOpen && (
        <div className="fixed inset-0 bg-black/30 z-30 lg:hidden" onClick={() => setSidebarOpen(false)} />
      )}

      <main className="flex-1 p-4 lg:p-10 overflow-auto bg-white lg:bg-gray-50">
        <Routes>
          {role === 'super_admin' ? (
            <>
              <Route path="/super-admin" element={<SuperAdmin />} />
              <Route path="*" element={<Navigate to="/super-admin" replace />} />
            </>
          ) : (
            <>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/products" element={<Products />} />
              {/* P1.2 FIX: Deep-link routes for Appointments — each tab accessible by URL */}
              <Route path="/appointments" element={<Navigate to="/appointments/agenda" replace />} />
              <Route path="/appointments/agenda" element={<Appointments initialTab="agenda" />} />
              <Route path="/appointments/services" element={<Appointments initialTab="services" />} />
              <Route path="/appointments/availability" element={<Appointments initialTab="availability" />} />
              <Route path="/appointments/settings" element={<Appointments initialTab="settings" />} />
              <Route path="/orders" element={<Orders />} />
              <Route path="/conversations" element={<Conversations />} />
              {/* P1.1 FIX: Deep-link routes for Settings — each tab accessible by URL */}
              <Route path="/settings" element={<Navigate to="/settings/store" replace />} />
              <Route path="/settings/store" element={<Settings initialTab="store" />} />
              <Route path="/settings/whatsapp" element={<Settings initialTab="whatsapp" />} />
              <Route path="/settings/payments" element={<Settings initialTab="payments" />} />
              <Route path="/settings/ai" element={<Settings initialTab="agent" />} />
              <Route path="/settings/social" element={<Settings initialTab="social" />} />
              <Route path="/settings/users" element={<Settings initialTab="users" />} />
              <Route path="/stock-sources" element={<StockSources />} />
              <Route path="/social-broadcast" element={<SocialBroadcast />} />
              <Route path="/payment-links" element={<PaymentLinks />} />
              <Route path="/promotions" element={<Promotions />} />
              <Route path="/visual-builder" element={<VisualBuilder />} />
              <Route path="/restocking" element={<PredictiveRestocking />} />
              <Route path="/loyalty-ia" element={<LoyaltyIA />} />
              <Route path="/b2b-portal" element={<B2BPortal />} />
              <Route path="/my-storefront" element={<MyStorefront />} />
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </>
          )}
        </Routes>
      </main>
    </div>
  );
}

function PublicRoute() {
  const { isAuthenticated, role, authReady } = useStore();
  if (!authReady) return <FullScreenLoader />;
  if (isAuthenticated) {
    return <Navigate to={role === 'super_admin' ? '/super-admin' : '/dashboard'} replace />;
  }
  return <Auth />;
}

export default function App() {
  return (
    <StoreProvider>
      <ToastProvider>
        <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<PublicRoute />} />
            <Route path="/reset-password" element={<ResetPassword />} />
            <Route path="/privacy" element={<PrivacyPolicy />} />
            <Route path="/store/:storeId" element={<StorefrontPageV2 />} />
            {/* AUDIT FIX: Alias /boutique/:slug → /store/:slug pour compatibilité */}
            <Route path="/boutique/:storeId" element={<StorefrontPageV2 />} />
            <Route path="/setup" element={<BusinessSetup />} />
            <Route path="/*" element={<Layout />} />
          </Routes>
            <CookieConsentBanner />
  </BrowserRouter>
      </ToastProvider>
    </StoreProvider>
  );
}
