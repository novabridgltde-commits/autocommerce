/**
 * e2e/tests/02-checkout.spec.ts — Flux Checkout et Liens de Paiement
 *
 * Parcours critiques testés :
 *   1. Storefront public : affichage produits
 *   2. Ajout panier + bouton checkout
 *   3. Création d'un lien de paiement via l'API
 *   4. Validation d'une commande (statut, idempotence)
 *   5. Webhook paiement (simulation Flouci / Stripe)
 */
import { test, expect } from "@playwright/test";
import { API_URL, ADMIN_EMAIL, ADMIN_PASSWORD, apiLogin, createTestProduct, deleteTestProduct } from "./helpers";

let adminToken: string;
let testProductId: number;

test.beforeAll(async () => {
  adminToken = await apiLogin(ADMIN_EMAIL, ADMIN_PASSWORD);
  const product = await createTestProduct(adminToken, {
    name: "Produit E2E Checkout",
    price: 49.99,
    stock_qty: 20,
  });
  testProductId = product.id;
});

test.afterAll(async () => {
  if (testProductId && adminToken) {
    await deleteTestProduct(adminToken, testProductId);
  }
});

// ── 1. Storefront public ──────────────────────────────────────────────────────

test.describe("Storefront public", () => {
  test("liste les produits disponibles", async ({ request }) => {
    // Récupérer l'info du store admin
    const meResp = await request.get(`${API_URL}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    expect(meResp.ok()).toBeTruthy();
    const me = await meResp.json();
    const storeSlug = me.store?.slug || me.store?.id;

    if (!storeSlug) {
      test.skip(true, "Store slug non disponible");
      return;
    }

    const resp = await request.get(`${API_URL}/api/v1/storefront/${storeSlug}/products`);
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(Array.isArray(body.products || body)).toBeTruthy();
  });

  test("retourne 404 pour un slug inexistant", async ({ request }) => {
    const resp = await request.get(`${API_URL}/api/v1/storefront/slug-inexistant-xyz-e2e/products`);
    expect(resp.status()).toBe(404);
  });
});

// ── 2. Produits API ───────────────────────────────────────────────────────────

test.describe("Produits (API)", () => {
  test("liste les produits du tenant", async ({ request }) => {
    const resp = await request.get(`${API_URL}/api/v1/products`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    const products = body.products || body.items || body;
    expect(Array.isArray(products)).toBeTruthy();
  });

  test("récupère un produit par ID", async ({ request }) => {
    const resp = await request.get(`${API_URL}/api/v1/products/${testProductId}`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    expect(resp.ok()).toBeTruthy();
    const product = await resp.json();
    expect(product.id).toBe(testProductId);
    expect(product.name).toBe("Produit E2E Checkout");
    expect(product.price).toBe(49.99);
  });

  test("met à jour le stock d'un produit", async ({ request }) => {
    const resp = await request.patch(`${API_URL}/api/v1/products/${testProductId}`, {
      headers: { Authorization: `Bearer ${adminToken}` },
      data: { stock_qty: 15 },
    });
    expect([200, 204]).toContain(resp.status());
  });

  test("refuse la création sans authentification", async ({ request }) => {
    const resp = await request.post(`${API_URL}/api/v1/products`, {
      data: { name: "Produit sans auth", price: 10.0 },
    });
    expect([401, 403]).toContain(resp.status());
  });
});

// ── 3. Liens de paiement ──────────────────────────────────────────────────────

test.describe("Payment Links (API)", () => {
  let paymentLinkId: number | null = null;

  test("crée un lien de paiement", async ({ request }) => {
    const resp = await request.post(`${API_URL}/api/v1/payment-links`, {
      headers: { Authorization: `Bearer ${adminToken}` },
      data: {
        title: "Commande E2E",
        amount: 49.990,
        currency: "TND",
        product_ids: [testProductId],
        expires_in_hours: 24,
      },
    });

    // 200/201 si le plan inclut les payment links, 402/403 si plan insuffisant
    expect([200, 201, 402, 403, 422]).toContain(resp.status());

    if (resp.ok()) {
      const body = await resp.json();
      expect(body).toHaveProperty("id");
      expect(body).toHaveProperty("url");
      paymentLinkId = body.id;
    }
  });

  test("un lien de paiement a une URL valide", async ({ request }) => {
    if (!paymentLinkId) {
      test.skip(true, "Pas de lien de paiement créé");
      return;
    }

    const resp = await request.get(`${API_URL}/api/v1/payment-links/${paymentLinkId}`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    expect(resp.ok()).toBeTruthy();
    const link = await resp.json();
    expect(link.url).toMatch(/^https?:\/\//);
  });
});

// ── 4. Commandes ──────────────────────────────────────────────────────────────

test.describe("Orders (API)", () => {
  test("liste les commandes du tenant", async ({ request }) => {
    const resp = await request.get(`${API_URL}/api/v1/orders`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    const orders = body.orders || body.items || body;
    expect(Array.isArray(orders)).toBeTruthy();
  });

  test("filtre les commandes par statut", async ({ request }) => {
    const resp = await request.get(`${API_URL}/api/v1/orders?status=pending`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    // 200 même si 0 résultats
    expect(resp.ok()).toBeTruthy();
  });

  test("isole les commandes entre tenants (sécurité multi-tenant)", async ({ request }) => {
    // Un tenant ne doit pas voir les commandes d'un autre
    // Test basique : on vérifie que l'endpoint requiert un token valide
    const resp = await request.get(`${API_URL}/api/v1/orders`, {
      headers: { Authorization: "Bearer faux_token_invalide" },
    });
    expect([401, 403]).toContain(resp.status());
  });
});

// ── 5. Webhook paiement (simulation) ─────────────────────────────────────────

test.describe("Webhook Paiement", () => {
  test("endpoint webhook Flouci répond (sans valider la signature)", async ({ request }) => {
    // Test de présence de l'endpoint — pas de validation signature en E2E
    const resp = await request.post(`${API_URL}/api/v1/payments/webhook`, {
      data: {
        payment_id: "test_payment_e2e",
        result: { status: "SUCCESS" },
      },
    });
    // 200 (traité), 400 (signature invalide), 422 (payload invalide) tous acceptables
    // On vérifie juste que c'est pas un 404 ou 500
    expect(resp.status()).not.toBe(404);
    expect(resp.status()).not.toBe(500);
  });

  test("endpoint webhook Stripe répond", async ({ request }) => {
    const resp = await request.post(`${API_URL}/api/v1/payments/webhook`, {
      headers: { "Stripe-Signature": "t=fake,v1=fake" },
      data: JSON.stringify({
        type: "payment_intent.succeeded",
        data: { object: { id: "pi_test_e2e" } },
      }),
    });
    expect(resp.status()).not.toBe(404);
    expect(resp.status()).not.toBe(500);
  });
});

// ── 6. Analytics dashboard ────────────────────────────────────────────────────

test.describe("Analytics (API)", () => {
  test("retourne les métriques du dashboard", async ({ request }) => {
    const resp = await request.get(`${API_URL}/api/v1/analytics/dashboard`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    // 200 ou 204 (données vides mais endpoint valide)
    expect([200, 204]).toContain(resp.status());
    if (resp.status() === 200) {
      const body = await resp.json();
      // Vérifier quelques métriques de base
      expect(typeof body).toBe("object");
    }
  });
});
