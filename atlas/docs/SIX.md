# VISTAN SIX · LIVE EXPERIMENTATION (paper trading autónomo)

> Antes de esta versión **no existía «VISTAN SIX»** en el código: solo el motor de Paper Trading del Trading Desk con dos cuentas.
> Se ha creado como **seis agentes** que operan **exclusivamente** a través de ese motor (`atlas/desk/engine.py`). No hay simulador paralelo, no hay brókers reales y no hay dinero real.

## Agentes
| Agente | Cuenta | Hipótesis | Variantes (timeframe) | Riesgo/op | DD máx | Pérdida diaria máx |
|---|---|---|---|---|---|---|
| ORION | SAFE | Tendencia (cruce EMA + filtro) | 1h | 0,5 % | 8 % | 2 % |
| VEGA | SAFE | Reversión a la media (Bollinger + RSI, **orden limitada**) | 1h | 0,5 % | 8 % | 2 % |
| LYRA | SAFE | RSI + MACD combinados | 4h | 0,5 % | 8 % | 2 % |
| NOVA | EXPERIMENTAL | Ruptura (Donchian) + stop dinámico | 1h / 4h | 1,5 % | 25 % | 6 % |
| RIGEL | EXPERIMENTAL | Momentum + salida por tiempo | 1h / 15m | 1,5 % | 25 % | 6 % |
| ALTAIR | EXPERIMENTAL | Cruces de medias (varios timeframes) | 1h / 4h / 15m | 1,5 % | 25 % | 6 % |

Cada agente tiene una **asignación virtual del 30 %** de su cuenta (100 000 € cada cuenta). Su sub-libro se calcula sobre las posiciones del motor cuya estrategia empieza por `SIX:<agente>:`. Los balances nunca se mezclan ni se reinicializan.

Identificador de estrategia: `SIX:<agente>:<familia>:<tf>:v<n>`. Cada id tiene su propio historial y sus propias métricas.

## Qué hace un ciclo (cada N min, solo con el modo autónomo activado y sin kill switch)
1. Descarga velas reales del Trading Desk y usa **solo velas cerradas**.
2. Bloquea la operación si:
   - hay menos velas de las necesarias;
   - la última vela cerrada es demasiado antigua;
   - no hay precio actual;
   - el precio se desvía más de un 8 % del último cierre.

   Cada caso queda registrado como decisión *descartada*.
3. Gestiona sus posiciones abiertas:
   - salida por señal o por tiempo;
   - stop dinámico que solo se mueve a favor;
   - cancela las órdenes limitadas que no se ejecutan en 3 velas.
4. Evalúa la señal **una sola vez por vela** y sin duplicados (una posición u orden por agente y activo).
5. Dimensiona por riesgo hasta el stop (ATR). La orden se envía con `engine.place_order`, que aplica comisiones, slippage, límites de cuenta y SL/TP configurables.
6. `engine.process` ejecuta las órdenes limitadas y los SL/TP.

## Controles de riesgo
- Los límites de la cuenta del Trading Desk siguen activos. La SAFE ACCOUNT exige stop y aplica sus límites.
- Por agente:
  - **freno por drawdown**: queda detenido hasta que lo reactives;
  - **pausa diaria por pérdida**: descarta nuevas entradas ese día.
- **Parada de emergencia**: desactiva la autonomía, pausa a los seis y, opcionalmente, cancela sus órdenes y cierra sus posiciones.
- **Kill switch** de VISTAN (META-BRAIN): ningún ciclo se ejecuta mientras esté activo.
- Activar el modo autónomo exige escribir `ACTIVAR`. A partir de ahí no se pide permiso por cada operación simulada.

## Evidencia (no se manipula)
- Las operaciones perdedoras nunca se borran. Las métricas salen solo de operaciones cerradas del motor:
  - neto después de costes, rentabilidad, max DD, profit factor, win rate, expectativa (en € y en R);
  - t-estadístico, costes y estabilidad (expectativa de cada mitad).
- Veredicto:

  | Operaciones / resultado | Veredicto |
  |---|---|
  | < 10 | `sin_datos` |
  | < 30 | `insuficiente` |
  | expectativa ≤ 0 o PF < 1 | `sin_ventaja` |
  | resto, sin cumplir lo de abajo | `no_significativa` |
  | t ≥ 2, PF ≥ 1,2 y ambas mitades positivas | `ventaja` |

- Rotación de variantes solo en agentes EXPERIMENTALES, con **≥ 20 operaciones** y expectativa ≤ 0. La evidencia queda registrada.
- Validación histórica: la misma lógica y los mismos costes sobre velas reales (≥ 300):
  - el 70 % inicial es dentro de muestra;
  - el 30 % final es **fuera de muestra**;
  - los parámetros no se optimizan.

## API (`/api/six`)
| Método | Ruta |
|---|---|
| GET | `status` |
| POST | `autonomy` (`{on, confirm}`) |
| PUT | `config` |
| POST | `tick` |
| POST | `emergency` |
| PATCH | `agents/{key}` |
| POST | `agents/{key}/pause` |
| POST | `agents/{key}/resume` |
| POST | `agents/{key}/validate` |
| GET | `agents/{key}/insights` |
| GET | `decisions` |
| GET | `trades` |
| GET | `validations` |

Las comisiones y el slippage se configuran por cuenta (`PATCH /api/desk/accounts/{id}`), también desde el panel.

## Limitaciones
- Necesita conexión a internet para las velas y los precios (Binance para cripto). Sin datos, los agentes no operan y lo registran.
- Acciones y forex intradía requieren una clave de Twelve Data (configurable en el Trading Desk).
- Un ciclo cada pocos minutos no es trading de alta frecuencia. Las ejecuciones son las del motor de paper trading (precio actual + slippage), no un libro de órdenes real.
- Ninguna estrategia se declara rentable sin cumplir los criterios de arriba, tanto en directo (paper) como fuera de muestra.
