/**
 * e2e/tests/helpers.ts — Helpers partagés pour les tests E2E AutoCommerce
 */
import { Page, expect } from "@playwright/test";

// ── Constantes ────────────────────────────────────────────────────────────────

export const API_URL = process.env.E2E_API_URL || "http://localhost:8000";

export const ADMIN_EMAIL    = process.env.E2E_ADMIN_EMAIL    || "admin@autocommerce.tn";
export const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || "admin_test_password";

export const TEST_USER_EMAIL    = "testuser_e2e@autocommerce.tn";
export const TEST_USER_PASSWORD = "Test@E2E2026!";
export const TEST_STORE_NAME    = "Boutique E2E Test";

// ── Auth helpers ──────────────────────────────────────────────────────────────

/**
 * Se connecte en tant qu'admin et retourne le token JWT.
 * Utilise l'API directement pour ne pas dépendre de l'UI de login dans tous les tests.
 */
export async function apiLogin(
  email = ADMIN_EMAIL,
  password = ADMIN_PASSWORD,
): Promise<string> {
  const response = await fetch(`${API_URL}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    throw new Error(`Login failed: HTTP ${response.status}`);
  }

  const data = await response.json();
  return data.access_token as string;
}

/**
 * Injecte un token dans le localStorage/cookies de la page (bypass UI login).
 */
export async function injectAuthToken(page: Page, token: string): Promise<void> {
  await page.evaluate((tok) => {
    // AutoCommerce utilise un cookie httpOnly en prod, mais en dev/test on peut
    // setter via l'API call qui set le cookie automatiquement
    // On stocke aussi dans sessionStorage pour les composants React
    sessionStorage.setItem("auth_token", tok);
  }, token);
}

/**
 * Login complet via l'UI (pour tester le flux de connexion lui-même).
 */
export async function loginViaUI(
  page: Page,
  email = ADMIN_EMAIL,
  password = ADMIN_PASSWORD,
): Promise<void> {
  await page.goto("/");
  // Attendre le formulaire de login
  await page.waitForSelector('[data-testid="login-email"], input[type="email"]', { timeout: 10_000 });

  const emailInput    = page.locator('input[type="email"]').first();
  const passwordInput = page.locator('input[type="password"]').first();
  const submitBtn     = page.locator('button[type="submit"]').first();

  await emailInput.fill(email);
  await passwordInput.fill(password);
  await submitBtn.click();

  // Attendre la redirection vers le dashboard
  await page.waitForURL(/\/(dashboard|app)/, { timeout: 15_000 });
}

// ── API helpers ───────────────────────────────────────────────────────────────

export async function apiRequest(
  path: string,
  options: RequestInit = {},
  token?: string,
): Promise<Response> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return fetch(`${API_URL}${path}`, { ...options, headers });
}

/**
 * Crée un produit test via l'API.
 */
export async function createTestProduct(
  token: string,
  overrides: Record<string, unknown> = {},
): Promise<{ id: number; name: string }> {
  const resp = await apiRequest(
    "/api/v1/products",
    {
      method: "POST",
      body: JSON.stringify({
        name: "Produit E2E Test",
        price: 29.99,
        stock_qty: 10,
        category: "Test",
        ...overrides,
      }),
    },
    token,
  );
  if (!resp.ok) throw new Error(`createTestProduct failed: ${resp.status}`);
  return resp.json();
}

/**
 * Supprime un produit test via l'API (nettoyage).
 */
export async function deleteTestProduct(token: string, productId: number): Promise<void> {
  await apiRequest(`/api/v1/products/${productId}`, { method: "DELETE" }, token);
}

// ── Wait helpers ──────────────────────────────────────────────────────────────

/**
 * Attend qu'un toast/notification disparaisse (utile après une action).
 */
export async function waitForToast(page: Page, textContains?: string): Promise<void> {
  if (textContains) {
    await expect(page.locator(`text=${textContains}`)).toBeVisible({ timeout: 8_000 });
  } else {
    await page.waitForSelector('[role="status"], [data-sonner-toast]', { timeout: 8_000 });
  }
}

/**
 * Attend que le spinner de chargement disparaisse.
 */
export async function waitForLoadingDone(page: Page): Promise<void> {
  await page.waitForFunction(() => {
    const spinners = document.querySelectorAll('[data-loading="true"], .animate-spin');
    return spinners.length === 0;
  }, { timeout: 10_000 });
}

// ── Webhook simulator ─────────────────────────────────────────────────────────

/**
 * Simule un webhook WhatsApp entrant (message texte client).
 */
export async function simulateWhatsAppMessage(
  storeWebhookToken: string,
  phoneNumber: string,
  messageText: string,
): Promise<Response> {
  const payload = {
    object: "whatsapp_business_account",
    entry: [{
      id: "1234567890",
      changes: [{
        value: {
          messaging_product: "whatsapp",
          metadata: { phone_number_id: "1234567890" },
          messages: [{
            id: `msg_e2e_${Date.now()}`,
            from: phoneNumber,
            timestamp: Math.floor(Date.now() / 1000).toString(),
            type: "text",
            text: { body: messageText },
          }],
          contacts: [{
            profile: { name: "Client E2E" },
            wa_id: phoneNumber,
          }],
        },
        field: "messages",
      }],
    }],
  };

  return fetch(`${API_URL}/api/v1/whatsapp/webhook`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Hub-Signature-256": `sha256=test_signature_${storeWebhookToken}`,
    },
    body: JSON.stringify(payload),
  });
}
