# Suite de pruebas del funnel

Un solo comando antes de desplegar:

```bash
./scripts/check.sh            # todo (≈40 s)
./scripts/check.sh --rapido   # sin build ni navegador (≈15 s)
```

Devuelve 0 solo si pasan todas las capas. Si algo falla, dice cuál y **no hay
que desplegar**.

## Por qué estas capas

Cada una caza una clase de fallo que las otras no ven. Las tres del 19/08/2026
son el mejor ejemplo, y cada una tiene hoy su red:

| Fallo que llegó a producción | Lo caza |
|---|---|
| `hideFooterLogo is not defined` — variable usada en otro componente; la página de vídeo caía al montar | render SSR y test de componente |
| `readFormVariant(null)` reventaba el StepForm en los funnels sin test de vídeo | unitario de null-safety |
| El StepForm dejó de pre-rellenarse al venir de la landing (query del arranque obsoleto) | e2e del recorrido |

Ninguna la detectaba el build: son errores de **ejecución**, no de sintaxis.

## Las capas

### 1. Unitarios — `frontend/tests/unit`
Lógica pura en jsdom. Registro de experimentos A/B (qué funnel tiene cuál, sin
solaparse), reparto 50/50, persistencia, `?force_form_variant`, prefill desde la
URL, payload de tracking y la transformación de tema a fondo blanco.

### 2. Componente — `frontend/tests/component`
Renderiza las pantallas de verdad con Testing Library: landing (fondo por
variante), formulario (qué sale en el payload del lead, A/B de WhatsApp de EU),
página de vídeo (logo del footer por variante y por marca) y confirmación.

`ssrRender.test.jsx` pinta **las 4 etapas de los 14 funnels** con el entry de
SSR. No comprueba diseño: comprueba que ninguna pantalla revienta. Es la red más
barata que existe contra los errores de ejecución.

### 3. Backend — `tests/funnels/test_variantes_ab.py`
Que el dato llegue y se guarde donde toca: la variante de la landing en el Lead,
la del vídeo en la Prellamada (columna + payload que se manda al CRM), los
envíos progresivos convergiendo en una sola prellamada y la traducción de slug a
código del CRM.

### 4. E2E — `frontend/tests/e2e`
Navegador real (Chrome del sistema) contra el **bundle compilado**, en
escritorio y en móvil. Un servidor mínimo (`tests/e2e/server.mjs`) genera el
mismo shell HTML que emite Django y sirve `dist`; el backend se simula con
`page.route`, lo que además permite afirmar **qué se envía en cada POST**.

Cubre: recorrido landing → StepForm con prefill, UTMs que sobreviven al salto,
el lead con su variante, la prellamada con la del vídeo, las variantes de diseño
forzadas y `?force_form_variant`.

**Seguridad:** el shell inyecta `__CQX_CALENDAR_ORIGIN__ = ""` igual que Django,
y hay un cortafuegos que aborta toda petición fuera de `localhost` y hace fallar
el test si intenta un POST fuera. Sin eso, el bundle de producción trae horneado
`VITE_CALENDAR_ORIGIN=calendar.conquerx.com` y **las pruebas escribirían en
producción** (pasó el 19/08: 3 leads reales creados desde un banco de pruebas
casero).

## Comandos sueltos

```bash
cd frontend
npm test                  # unitarios + componente + render SSR
npm run test:watch        # en watch mientras desarrollas
npm run test:cov          # con cobertura
npm run test:e2e          # compila y corre el navegador
npx playwright test --ui  # e2e en modo interactivo, para depurar
npx playwright test -g "prefill"   # un solo caso

# backend (necesita el contenedor arriba: docker compose up -d)
docker compose exec django python manage.py test tests
```

## Al añadir un experimento A/B

1. Declararlo en `frontend/src/lib/formVariant.js`, anclado al **slug exacto**
   del funnel (no a marca+región: hay funnels que comparten ambas).
2. Añadir su fila al mapa esperado en `tests/unit/formVariant.test.js`. El test
   comprueba que ningún otro funnel lo hereda por accidente.
3. Si cambia algo visible, añadir el caso a `tests/component` (qué se ve) y a
   `tests/e2e` (qué se envía).
