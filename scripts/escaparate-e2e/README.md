# Prueba completa de Escaparate

Recorre la app como un comercio real: registro con código, fotos, devolución de
créditos, pagos de Stripe simulados, vídeo, textos, galería, catálogo,
calendario, subida bloqueada sin sesión y borrado de cuenta.

No gasta dinero ni llama a ninguna IA: usa una plataforma falsa
(`mock-platform.cjs`) y avisos de Stripe firmados con un secreto de prueba.

```bash
# 1. Postgres local con una base vacía
export DATABASE_URL=postgres://usuario:clave@localhost:5432/escaparate_test
pnpm escaparate:migrate

# 2. Plataforma de IA falsa
node scripts/escaparate-e2e/mock-platform.cjs &

# 3. La app, en modo producción
pnpm build
ESCAPARATE_LOG_LOGIN_CODES=1 ESCAPARATE_PLATFORM_KEY=key:secret \
HF_API_BASE_URL=http://localhost:3200 STRIPE_SECRET_KEY=sk_test_dummy \
STRIPE_WEBHOOK_SECRET=whsec_testsecret pnpm start -p 3100 > app.log 2>&1 &

# 4. La prueba (necesita psql en el PATH y PGPASSWORD si hace falta)
APP_LOG=app.log node scripts/escaparate-e2e/flow.cjs
```

La base de datos debe empezar vacía: la prueba borra la cuenta al final.
