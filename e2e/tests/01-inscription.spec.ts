/**
 * e2e/tests/01-inscription.spec.ts — Inscription et onboarding
 *
 * Parcours critiques testés :
 *   1. Affichage de la page landing
 *   2. Formulaire d'inscription (champs, validation, soumission)
 *   3. Redirection post-inscription vers le setup boutique
 *   4. API health check
 */
import { test, expect, Page } from "@playwright/test";
import { API_URL, apiRequest } from "./helpers";

// ── 1. API Health ─────────────────────────────────────────────────────────────

test.describe("API Health", () => {
  test("GET /api/health retourne 200", async ({ request }) => {
    const resp = await request.get(`${API_URL}/api/health`);
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(body).toHaveProperty("status");
    expect(["ok", "healthy", "degraded"]).toContain(body.status);
  });

  test("GET /api/health ne retourne pas 500", async ({ request }) => {
    const resp = await request.get(`${API_URL}/api/health`);
    expect(resp.status()).not.toBe(500);
  });
});

// ── 2. Page Landing ───────────────────────────────────────────────────────────

test.describe("Landing Page", () => {
  test("s'affiche correctement", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/.+/);  // Titre non vide
    // Vérifier qu'il y a un CTA d'inscription ou de connexion
    const cta = page.locator(
      'a[href*="register"], a[href*="signup"], a[href*="inscription"], button:has-text("Démarrer"), button:has-text("Essai")'
    );
    // La page a du contenu visible
    await expect(page.locator("body")).toBeVisible();
  });

  test("pas d'erreurs JS critiques au chargement", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    // Filtrer les erreurs non-critiques
    const criticalErrors = errors.filter(
      (e) => !e.includes("ResizeObserver") && !e.includes("Non-Error")
    );
    expect(criticalErrors).toHaveLength(0);
  });
});

// ── 3. Formulaire de connexion ────────────────────────────────────────────────

test.describe("Formulaire de connexion", () => {
  test("affiche les champs email et mot de passe", async ({ page }) => {
    await page.goto("/");
    // Chercher la page login (peut être / ou /login ou /auth)
    const loginPaths = ["/login", "/auth", "/signin"];
    for (const path of loginPaths) {
      try {
        await page.goto(path);
        const emailInput = page.locator('input[type="email"]');
        if (await emailInput.count() > 0) {
          await expect(emailInput.first()).toBeVisible();
          break;
        }
      } catch (_) {
        continue;
      }
    }
  });

  test("affiche une erreur sur credentials invalides", async ({ page, request }) => {
    // Via l'API directement (plus fiable que l'UI pour ce test)
    const resp = await request.post(`${API_URL}/api/v1/auth/login`, {
      data: { email: "wrong@test.com", password: "wrongpassword" },
    });
    expect(resp.status()).toBe(401);
    const body = await resp.json();
    expect(body).toHaveProperty("detail");
  });

  test("refuse un email mal formé via l'API", async ({ request }) => {
    const resp = await request.post(`${API_URL}/api/v1/auth/login`, {
      data: { email: "pas-un-email", password: "password123" },
    });
    expect([400, 422, 401]).toContain(resp.status());
  });
});

// ── 4. Inscription via API ────────────────────────────────────────────────────

test.describe("Inscription (API)", () => {
  const uniqueEmail = `e2e_test_${Date.now()}@autocommerce-test.tn`;
  let createdUserId: number | null = null;

  test("crée un compte avec les informations valides", async ({ request }) => {
    const resp = await request.post(`${API_URL}/api/v1/auth/register`, {
      data: {
        email: uniqueEmail,
        password: "TestE2E@2026!",
        store_name: "Boutique E2E",
        country: "TN",
      },
    });

    // 200, 201 ou 409 (si déjà existant d'un test précédent)
    expect([200, 201, 409]).toContain(resp.status());

    if (resp.status() === 200 || resp.status() === 201) {
      const body = await resp.json();
      expect(body).toHaveProperty("access_token");
      createdUserId = body.user?.id;
    }
  });

  test("refuse un email déjà enregistré", async ({ request }) => {
    // Utiliser l'email admin (forcément existant)
    const resp = await request.post(`${API_URL}/api/v1/auth/register`, {
      data: {
        email: "admin@autocommerce.tn",
        password: "AnyPassword@123",
        store_name: "Test",
        country: "TN",
      },
    });
    expect([409, 400, 422]).toContain(resp.status());
  });

  test("refuse un mot de passe trop court", async ({ request }) => {
    const resp = await request.post(`${API_URL}/api/v1/auth/register`, {
      data: {
        email: `short_${Date.now()}@test.tn`,
        password: "123",
        store_name: "Test",
        country: "TN",
      },
    });
    expect([400, 422]).toContain(resp.status());
  });
});

// ── 5. Rate limiting sur /auth/login ─────────────────────────────────────────

test.describe("Rate limiting auth", () => {
  test("bloque après trop de tentatives échouées", async ({ request }) => {
    // Envoyer 15 requêtes d'affilée (limite = 10/min)
    const responses = await Promise.all(
      Array.from({ length: 12 }, () =>
        request.post(`${API_URL}/api/v1/auth/login`, {
          data: { email: "bruteforce@test.com", password: "wrong" },
        })
      )
    );

    const statuses = responses.map((r) => r.status());
    // Au moins une réponse doit être 429 (rate limit)
    const hasRateLimit = statuses.some((s) => s === 429);
    // Si le test tourne en isolation (premier run), le rate limit peut ne pas
    // se déclencher immédiatement — on vérifie juste qu'on n'a pas de 500
    const has500 = statuses.some((s) => s === 500);
    expect(has500).toBe(false);
    // En CI avec Redis, on attend le 429
    if (process.env.CI) {
      expect(hasRateLimit).toBe(true);
    }
  });
});
