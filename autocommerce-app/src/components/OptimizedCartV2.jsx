import React, { useMemo, useState } from 'react';
import api from '../api';

/**
 * OptimizedCartV2 — Panier optimisé avec aperçu promotions/coupons
 */
export default function OptimizedCartV2({ items, store, storeId }) {
  const [isOpen, setIsOpen] = useState(false);
  const [customerName, setCustomerName] = useState('');
  const [customerPhone, setCustomerPhone] = useState('');
  const [couponCode, setCouponCode] = useState('');
  const [preview, setPreview] = useState(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [previewError, setPreviewError] = useState('');

  if (!items || items.length === 0) return null;

  const normalizedItems = useMemo(() => items.map((item) => {
    const price = item.promo_price && item.promo_price < item.price ? item.promo_price : item.price;
    return {
      product_id: item.id,
      name: item.name,
      qty: item.quantity || 1,
      unit_price: price,
      category: item.category,
      tax_category: item.tax_category || item.category,
      is_tax_exempt: !!item.is_tax_exempt,
    };
  }), [items]);

  const baseTotal = normalizedItems.reduce((sum, item) => sum + (item.unit_price * item.qty), 0);
  const effectiveItems = preview?.items || normalizedItems;
  const effectiveTotal = preview?.pricing?.total_amount ?? baseTotal;
  const effectiveDiscount = preview?.discount_amount ?? 0;

  const applyCouponPreview = async () => {
    if (!storeId) return;
    setLoadingPreview(true);
    setPreviewError('');
    try {
      const { data } = await api.post(`/storefront/${storeId}/promotions/preview`, {
        items: normalizedItems,
        coupon_codes: couponCode.trim() ? [couponCode.trim()] : [],
        channel: 'storefront',
        customer_name: customerName || undefined,
        customer_phone: customerPhone || undefined,
      });
      setPreview(data);
    } catch (err) {
      setPreview(null);
      setPreviewError(err?.response?.data?.detail || 'Coupon invalide ou promotion indisponible');
    } finally {
      setLoadingPreview(false);
    }
  };

  const generateOrderMessage = () => {
    let msg = `🛒 *Nouvelle Commande*\n\n`;

    if (customerName) msg += `👤 *Nom:* ${customerName}\n`;
    if (customerPhone) msg += `📱 *Téléphone:* ${customerPhone}\n`;

    msg += `\n*Produits:*\n`;
    effectiveItems.forEach((item, idx) => {
      const lineTotal = (Number(item.unit_price || 0) * Number(item.qty || 1)).toFixed(3);
      msg += `${idx + 1}. ${item.name} x${item.qty || 1} = ${lineTotal} DT\n`;
    });

    if (preview?.applied_promotions?.length) {
      msg += `\n*Promotions appliquées:*\n`;
      preview.applied_promotions.forEach((promo) => {
        const amount = Number(promo.discount_amount || 0).toFixed(3);
        msg += `- ${promo.promotion_name}${amount !== '0.000' ? ` (-${amount} DT)` : ''}\n`;
      });
    }

    if (couponCode.trim()) {
      msg += `\n🎟️ *Code promo:* ${couponCode.trim()}\n`;
    }

    if (effectiveDiscount > 0) {
      msg += `💸 *Remise:* -${Number(effectiveDiscount).toFixed(3)} DT\n`;
    }

    msg += `\n💰 *Total:* ${Number(effectiveTotal).toFixed(3)} DT\n`;
    msg += `\n✅ Merci de confirmer cette commande !`;
    return msg;
  };

  const getContactUrl = (channel) => {
    const msg = encodeURIComponent(generateOrderMessage());

    switch (channel) {
      case 'whatsapp':
        return `https://wa.me/${(store.whatsapp_phone || '').replace(/\D/g, '')}?text=${msg}`;
      case 'messenger':
        return store.messenger_page_id
          ? `https://m.me/${store.messenger_page_id}?ref=order`
          : null;
      case 'instagram':
        return store.instagram_handle
          ? `https://instagram.com/${store.instagram_handle.replace('@', '')}`
          : null;
      case 'tiktok':
        return store.tiktok_handle
          ? `https://tiktok.com/@${store.tiktok_handle.replace('@', '')}`
          : null;
      default:
        return null;
    }
  };

  const channels = [
    { id: 'whatsapp', label: 'WhatsApp', icon: '💬', enabled: !!store.whatsapp_phone },
    { id: 'messenger', label: 'Messenger', icon: '💭', enabled: !!store.messenger_page_id },
    { id: 'instagram', label: 'Instagram', icon: '📷', enabled: !!store.instagram_handle },
    { id: 'tiktok', label: 'TikTok', icon: '🎵', enabled: !!store.tiktok_handle },
  ].filter((c) => c.enabled);

  return (
    <>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-6 left-6 z-40 w-16 h-16 rounded-full shadow-lg hover:shadow-xl transition-all active:scale-95 flex items-center justify-center text-2xl font-bold"
        style={{ backgroundColor: '#111827', color: '#fff' }}
      >
        🛒
        <span className="absolute -top-2 -right-2 bg-red-500 text-white text-xs font-bold w-6 h-6 rounded-full flex items-center justify-center">
          {items.length}
        </span>
      </button>

      {isOpen && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-end sm:items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-gray-900 text-white p-4 flex justify-between items-center rounded-t-2xl">
              <h2 className="text-lg font-bold">Votre panier</h2>
              <button onClick={() => setIsOpen(false)} className="text-2xl">✕</button>
            </div>

            <div className="p-4 space-y-4">
              <div className="space-y-3 max-h-48 overflow-y-auto">
                {effectiveItems.map((item, idx) => (
                  <div key={`${item.product_id || item.name}-${idx}`} className="flex justify-between items-start pb-3 border-b border-gray-100">
                    <div className="flex-1">
                      <p className="font-semibold text-gray-900 text-sm">{item.name}</p>
                      <p className="text-xs text-gray-600">x{item.qty || item.quantity || 1}</p>
                    </div>
                    <p className="font-bold text-gray-900">{(Number(item.unit_price || 0) * Number(item.qty || item.quantity || 1)).toFixed(3)} DT</p>
                  </div>
                ))}
              </div>

              <div className="bg-gray-100 rounded-lg p-3 space-y-2">
                <div className="flex justify-between items-center text-sm">
                  <span className="text-gray-600">Sous-total</span>
                  <span className="font-semibold text-gray-900">{baseTotal.toFixed(3)} DT</span>
                </div>
                {effectiveDiscount > 0 && (
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-green-700">Remise</span>
                    <span className="font-semibold text-green-700">-{Number(effectiveDiscount).toFixed(3)} DT</span>
                  </div>
                )}
                <div className="flex justify-between items-center border-t border-gray-200 pt-2">
                  <span className="font-semibold text-gray-900">Total</span>
                  <span className="text-xl font-bold text-gray-900">{Number(effectiveTotal).toFixed(3)} DT</span>
                </div>
              </div>

              <div className="space-y-3 border-t border-gray-200 pt-4">
                <input
                  type="text"
                  placeholder="Votre nom"
                  value={customerName}
                  onChange={(e) => setCustomerName(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
                />
                <input
                  type="tel"
                  placeholder="Votre téléphone"
                  value={customerPhone}
                  onChange={(e) => setCustomerPhone(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
                />
              </div>

              <div className="space-y-2 border-t border-gray-200 pt-4">
                <p className="text-xs font-semibold text-gray-600">Code promo</p>
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="PROMO2026"
                    value={couponCode}
                    onChange={(e) => setCouponCode(e.target.value.toUpperCase())}
                    className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
                  />
                  <button
                    type="button"
                    onClick={applyCouponPreview}
                    disabled={loadingPreview}
                    className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 disabled:opacity-60"
                  >
                    {loadingPreview ? '...' : 'Appliquer'}
                  </button>
                </div>
                {previewError && <p className="text-xs text-red-600">{previewError}</p>}
                {!!preview?.applied_promotions?.length && (
                  <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-sm">
                    {preview.applied_promotions.map((promo) => (
                      <div key={`${promo.promotion_id}-${promo.coupon_code || 'auto'}`} className="flex justify-between gap-3 text-green-800">
                        <span>{promo.promotion_name}</span>
                        <span>{Number(promo.discount_amount || 0).toFixed(3) === '0.000' ? 'appliquée' : `-${Number(promo.discount_amount || 0).toFixed(3)} DT`}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="space-y-2 border-t border-gray-200 pt-4">
                <p className="text-xs font-semibold text-gray-600 mb-2">Envoyer la commande via :</p>
                {channels.map((channel) => {
                  const url = getContactUrl(channel.id);
                  if (!url) return null;
                  return (
                    <a
                      key={channel.id}
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center justify-center gap-2 w-full py-3 rounded-lg font-semibold text-sm transition-all hover:opacity-90 active:scale-95"
                      style={{
                        backgroundColor: channel.id === 'whatsapp' ? '#25D366' :
                          channel.id === 'messenger' ? '#0084FF' :
                            channel.id === 'instagram' ? '#E4405F' : '#000000',
                        color: '#fff',
                      }}
                    >
                      <span className="text-lg">{channel.icon}</span>
                      <span>{channel.label}</span>
                    </a>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
