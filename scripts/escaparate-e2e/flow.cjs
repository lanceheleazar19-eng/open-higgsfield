// End-to-end test for Escaparate against a local Postgres and a fake AI
// platform (mock-platform.cjs). See README.md in this folder.
const { chromium } = require('playwright');
const fs = require('fs');
const log = () => fs.readFileSync(process.env.APP_LOG || 'app.log', 'utf8');
(async () => {
  const b = await chromium.launch();
  const page = await b.newPage({ viewport: { width: 1280, height: 900 } });
  // Fake Vercel Blob: token route and the upload itself.
  await page.route('**/api/blob', r => r.fulfill({ json: { type: 'blob.generate-client-token', clientToken: 'vercel_blob_client_store123_abcdef', pathname: require('path').join(__dirname, 'p.png') } }));
  await page.route(/vercel\.com\/api\/blob/, r => r.fulfill({ json: { url: 'https://store123.public.blob.vercel-storage.com/p.png', downloadUrl: 'x', pathname: require('path').join(__dirname, 'p.png'), contentType: 'image/png', contentDisposition: 'inline' } }));
  await page.route(/example\.com/, r => r.fulfill({ status: 200, contentType: 'image/png', body: fs.readFileSync(require('path').join(__dirname, 'p.png')) }));

  await page.goto('http://localhost:3100/escaparate/crear');
  console.log('at', page.url());
  await page.fill('input[type=email]', 'tienda@example.com');
  await page.check('input[type=checkbox]');
  await page.click('text=Enviarme el código');
  await page.waitForSelector('text=Revisa tu correo');
  const code = log().match(/login code for tienda@example.com: (\d{6})/g).pop().slice(-6);
  await page.fill('input[autocomplete=one-time-code]', '000000' === code ? '111111' : '000000');
  await page.click('button:has-text("Entrar")');
  await page.waitForSelector('text=El código no es correcto');
  console.log('wrong code rejected');
  await page.fill('input[autocomplete=one-time-code]', code);
  await page.click('button:has-text("Entrar")');
  await page.waitForURL('**/escaparate/crear');
  await page.waitForSelector('text=Tienes');
  console.log('banner:', await page.textContent('.esc-banner span'));

  await page.setInputFiles('input[type=file]', require('path').join(__dirname, 'p.png'));
  await page.waitForSelector('text=Foto lista');
  await page.fill('input[placeholder^="Ej.: tarta"]', 'tarta de queso');
  await page.click('button:has-text("Crear 4 fotos")');
  await page.waitForFunction(() => document.querySelectorAll('.esc-result img').length === 3 && document.body.innerText.includes('Te devolvemos'), null, { timeout: 30000 });
  console.log('after images:', await page.textContent('.esc-banner span'));
  await page.click('button:has-text("Crear vídeo")');
  await page.waitForSelector('text=No tienes créditos suficientes');
  console.log('video blocked without enough credits: ok');

  // Simulate a paid Stripe checkout for the 60-credit pack, sent twice.
  const userId = require('child_process').execSync(`psql "${process.env.DATABASE_URL}" -tAc "select id from esc_users"`).toString().trim();
  const Stripe = require('stripe');
  const stripe = new (Stripe.default || Stripe)('sk_test_dummy');
  const payload = JSON.stringify({ id: 'evt_pack_1', object: 'event', type: 'checkout.session.completed', data: { object: { id: 'cs_test_1', object: 'checkout.session', mode: 'payment', payment_status: 'paid', customer: 'cus_test', client_reference_id: userId, metadata: { userId, packId: 'pack60' } } } });
  for (let i = 0; i < 2; i++) {
    const header = stripe.webhooks.generateTestHeaderString({ payload, secret: 'whsec_testsecret' });
    const r = await fetch('http://localhost:3100/api/escaparate/stripe', { method: 'POST', headers: { 'stripe-signature': header, 'content-type': 'application/json' }, body: payload });
    console.log('webhook', i, r.status, await r.text());
  }
  const bad = await fetch('http://localhost:3100/api/escaparate/stripe', { method: 'POST', headers: { 'stripe-signature': 't=1,v1=bad' }, body: payload });
  console.log('forged webhook ->', bad.status);
  // Subscription invoice paid -> monthly credits
  const inv = JSON.stringify({ id: 'evt_inv_1', object: 'event', type: 'invoice.paid', data: { object: { id: 'in_1', object: 'invoice', customer: 'cus_test', parent: { subscription_details: { metadata: { userId, planId: 'comercio' } } } } } });
  const r2 = await fetch('http://localhost:3100/api/escaparate/stripe', { method: 'POST', headers: { 'stripe-signature': stripe.webhooks.generateTestHeaderString({ payload: inv, secret: 'whsec_testsecret' }) }, body: inv });
  console.log('invoice webhook', r2.status);
  const sub = JSON.stringify({ id: 'evt_sub_1', object: 'event', type: 'customer.subscription.created', data: { object: { id: 'sub_1', object: 'subscription', status: 'active', customer: 'cus_test', metadata: { userId, planId: 'comercio' } } } });
  await fetch('http://localhost:3100/api/escaparate/stripe', { method: 'POST', headers: { 'stripe-signature': stripe.webhooks.generateTestHeaderString({ payload: sub, secret: 'whsec_testsecret' }) }, body: sub });

  await page.reload();
  await page.setInputFiles('input[type=file]', require('path').join(__dirname, 'p.png'));
  await page.waitForSelector('text=Foto lista');
  console.log('after purchases:', await page.textContent('.esc-banner span'));
  await page.click('button:has-text("Crear 4 fotos")');
  await page.waitForFunction(() => document.querySelectorAll('.esc-result img').length === 3, null, { timeout: 30000 });
  await page.locator('button:has-text("Crear vídeo")').first().click();
  await page.waitForSelector('video', { timeout: 30000 });
  console.log('after video:', await page.textContent('.esc-banner span'));
  await page.fill('input[placeholder^="Ej.: tarta"]', 'tarta de queso');
  await page.fill('textarea', 'receta de la abuela');
  await page.click('button:has-text("Divertido")');
  await page.click('button:has-text("Escribir con IA")');
  await page.waitForSelector('text=te dejamos un texto de plantilla');
  console.log('copy fallback: ok');
  

  await page.goto('http://localhost:3100/escaparate/creaciones');
  const items = await page.locator('.esc-gallery-item').count();
  console.log('gallery items:', items, 'videos:', await page.locator('.esc-gallery-item video').count());
  await page.locator('button[aria-label="Marcar como favorita"]').first().click();
  await page.waitForSelector('button[aria-label="Quitar de favoritas"]');
  await page.goto('http://localhost:3100/escaparate/creaciones?ver=favoritas');
  console.log('favorites:', await page.locator('.esc-gallery-item').count());
  await page.goto('http://localhost:3100/escaparate/creaciones');
  await page.locator('button[aria-label="Quitar de la galería"]').last().click();
  await page.waitForFunction(n => document.querySelectorAll('.esc-gallery-item').length === n - 1, items);
  console.log('after hide:', await page.locator('.esc-gallery-item').count());
  
  const m = await b.newPage({ viewport: { width: 390, height: 800 } });
  await m.context().addCookies(await page.context().cookies());
  await m.goto('http://localhost:3100/escaparate/creaciones');
  console.log('mobile scrollWidth:', await m.evaluate(() => document.documentElement.scrollWidth));
  

  // Catalogue
  await page.goto('http://localhost:3100/escaparate/catalogo');
  console.log('catalogue:', (await page.locator('.esc-gallery-item').allTextContents()).map(t => t.replace(/\s+/g, ' ').trim()).join(' || '));
  
  await page.locator('a:has-text("Crear contenido")').last().click();
  await page.waitForSelector('text=de tu catálogo');
  console.log('reopened product name:', await page.inputValue('input[placeholder^="Ej.: tarta"]'), '| photo ready:', await page.isVisible('text=Foto lista'));
  // Calendar
  await page.goto('http://localhost:3100/escaparate/calendario');
  console.log('calendar first:', (await page.locator('.esc-timeline-item h3').first().textContent()).trim(), '| items:', await page.locator('.esc-timeline-item').count());
  
  await page.goto('http://localhost:3100/escaparate/crear?ocasion=navidad');
  console.log('occasion banner:', (await page.textContent('.esc-banner-occasion strong')).trim());
  await page.click('button:has-text("Escribir con IA")');
  await page.waitForSelector('text=te dejamos un texto de plantilla');
  console.log('occasion copy title:', (await page.locator('.esc-copy-block').first().textContent()).split('\n')[0]);
  // Upload gate
  const anon = await fetch('http://localhost:3100/api/blob', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ type: 'blob.generate-client-token', payload: { pathname: 'x.png', clientPayload: null, multipart: false } }) });
  console.log('anonymous upload token ->', anon.status);

  await page.goto('http://localhost:3100/escaparate/cuenta');
  
  console.log('ledger:', (await page.textContent('table')).replace(/\s+/g, ' '));
  // Delete account
  await page.goto('http://localhost:3100/escaparate/cuenta');
  await page.click('summary:has-text("Borrar mi cuenta")');
  await page.click('button:has-text("Borrar mi cuenta para siempre")');
  await page.waitForSelector('text=escribe BORRAR');
  console.log('delete without confirm blocked');
  await page.fill('input[name=confirm]', 'borrar');
  await page.click('button:has-text("Borrar mi cuenta para siempre")');
  await page.waitForSelector('text=No hemos podido cancelar tu suscripción');
  console.log('active subscription + Stripe unreachable -> account kept, user told');
  require('child_process').execSync(`psql "${process.env.DATABASE_URL}" -c "update esc_users set subscription_status='canceled'"`);
  await page.fill('input[name=confirm]', 'BORRAR');
  await page.click('button:has-text("Borrar mi cuenta para siempre")');
  await page.waitForSelector('text=Tu cuenta y todos tus datos se han borrado');
  const left = require('child_process').execSync(`psql "${process.env.DATABASE_URL}" -tAc "select (select count(*) from esc_users)||'/'||(select count(*) from esc_products)||'/'||(select count(*) from esc_generations)||'/'||(select count(*) from esc_sessions)"`).toString().trim();
  console.log('after delete users/products/generations/sessions:', left);
  await b.close();
})().catch(e => { console.error('FAIL', e.message); process.exit(1); });
