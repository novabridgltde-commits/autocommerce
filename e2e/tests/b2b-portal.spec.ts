import { test, expect } from '@playwright/test';

test('B2B portal renders and creates an account with mocked API', async ({ page }) => {
  let accounts = [
    {
      id: 1,
      store_id: 1,
      account_type: 'garage',
      name: 'Garage Atlas',
      legal_name: 'Garage Atlas SARL',
      tax_id: 'FR123',
      billing_email: 'atlas@example.com',
      phone: null,
      address: null,
      status: 'active',
      credit_limit: 5000,
      payment_terms_days: 30,
      metadata_json: null,
      notes: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
  ];

  await page.route('**/api/v1/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ user_id: 7, store_id: 1, role: 'admin', is_active: true, store_name: 'AC' }),
    });
  });

  await page.route('**/api/v1/b2b/dashboard', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ accounts_total: accounts.length, pending_orders: 0, overdue_invoices: 0, credit_exposure: 0 }),
    });
  });

  await page.route('**/api/v1/b2b/accounts', async (route, request) => {
    if (request.method() === 'POST') {
      const payload = JSON.parse(request.postData() || '{}');
      accounts = [
        {
          id: accounts.length + 1,
          store_id: 1,
          account_type: payload.account_type,
          name: payload.name,
          legal_name: payload.legal_name || null,
          tax_id: null,
          billing_email: payload.billing_email || null,
          phone: null,
          address: null,
          status: 'active',
          credit_limit: payload.credit_limit || null,
          payment_terms_days: payload.payment_terms_days || 30,
          metadata_json: null,
          notes: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
        ...accounts,
      ];
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(accounts[0]) });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(accounts) });
  });

  await page.route('**/api/v1/b2b/orders', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });

  await page.route('**/api/v1/b2b/invoices', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });

  await page.goto('/b2b-portal');
  await expect(page.getByRole('heading', { name: /Portail B2B/i })).toBeVisible();
  await expect(page.getByText('Garage Atlas')).toBeVisible();

  await page.getByPlaceholder('Nom du compte').fill('Revendeur Test');
  await page.getByPlaceholder('Email facturation').fill('revendeur@example.com');
  await page.getByRole('button', { name: /Créer le compte/i }).click();

  await expect(page.getByText('Compte entreprise créé.')).toBeVisible();
  await expect(page.getByText('Revendeur Test')).toBeVisible();
});
