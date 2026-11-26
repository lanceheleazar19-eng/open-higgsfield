# VISTAN META-BRAIN — THINK. COORDINATE. VERIFY. EXECUTE.

Capa de coordinación sobre lo que VISTAN ya tenía (Model Router, agentes, memoria, Research Engine, Automatizaciones,
Knowledge/RAG, Model Testing Arena, autorizaciones y auditoría). No duplica bases de datos: añade `mb_runs` (trazas)
y `memory_revisions` (historial), y amplía `memories` con dos tipos (procedimiento, episodio), nivel de acceso y reemplazo.
Interfaz: `/meta` (o pulsa el núcleo central «VISTAN CORE»). En el chat: «piensa a fondo: …».

## Qué funciona sin credenciales (solo con Ollama en tu Mac)
| Función | Estado | Cómo se comprueba |
|---|---|---|
| META-BRAIN (comprender → formular → contexto → especialistas → crítico → investigar → integrar → verificar) | Operativo | tests `test_meta.py`, E2E |
| Intelligent Model Router: inventario real, cadena con fallback, privacidad por contenido, límites, latencia/tokens/coste medidos | Operativo con Ollama | `/api/meta/router` |
| VISTAN Council: especialistas reales del registro, contexto reunido una vez, crítico independiente, verificador sin IA | Operativo | test del consejo |
| Critic Engine: lógica, evidencia, contradicciones, cálculos (recalculados), supuestos, desactualización, inyección, «consenso ≠ verdad» | Operativo | test del consejo e inyección |
| Verificación de soporte textual de cada hecho (E#) | Operativo (mide apoyo documental, no «verdad») | test |
| Memory Intelligence: tipos, duplicados, contradicciones, resolver/fusionar, historial, acceso all/local/private | Operativo | tests de memoria |
| Autonomous Execution: objetivo → plan con pasos reales → autorizaciones → reintentos, checkpoints, cancelación | Operativo | test de ejecución |
| Benchmark Center (17 pruebas, 9 categorías, comprobación automática, VISTAN como concursante) | Operativo | test de benchmark |
| Self-Evaluation (métricas reales y recomendaciones por reglas; nada se aplica solo) | Operativo | test |
| Governance: kill switch global, límites, permisos por agente, auditoría, inyecciones detectadas | Operativo | test del kill switch |
| Multimodal: matriz de capacidades comprobada en el momento | Operativo (vídeo: no disponible) | `/api/meta/multimodal` |

## Qué necesita credenciales o instalación
| Función | Necesita | Dónde se configura |
|---|---|---|
| OpenAI / Anthropic / Google Gemini en el router y el benchmark | API key + modelo | Configuración → Modelos (Llavero) |
| Otros proveedores (Groq, Mistral, OpenRouter, Together, LM Studio…) | URL base compatible con OpenAI + modelo (+ clave) | META-BRAIN → Model Router |
| Coste en $ por llamada | Precios por millón de tokens de cada modelo | Configuración → Modelos |
| Investigación web (modo investigación, crítico que pide investigar) | Internet (buscador sin clave) | — |
| Imágenes | Modelo de visión local (`ollama pull qwen2.5vl:7b`) | Ollama |
| Vídeo, transcripción de archivos de audio | No hay proveedor integrado: no se ofrece | — |

## Privacidad y seguridad
- Datos personales (salud, dinero, vida privada) y agentes sensibles → **solo modelos locales** salvo que lo permitas.
- Recuerdos `local` nunca salen a la nube; `private` nunca entran en el contexto de ninguna IA.
- Contenido externo neutralizado antes de llegar a un modelo generativo; cada detección queda en la auditoría.
- Las claves viven en el Llavero; la API nunca las devuelve.
- Ningún paso puede pagar, comprar, publicar ni enviar mensajes; escribir/ejecutar pide autorización según tu política.
- Nada modifica código de producción ni pesos de modelos.

## Limitaciones honestas
- El consejo con un modelo local de 7B tarda (varias llamadas secuenciales): el límite por defecto es 12 llamadas y 600 s.
- La verificación mide si cada hecho tiene apoyo textual en la evidencia citada; no demuestra que la fuente sea cierta.
- La detección de contradicciones en memoria es por reglas (cifras/negación sobre el mismo tema); la confirmación con IA es opcional y local.
- «Development Lab» no existe en VISTAN: el equivalente es el Prototype Studio del Innovation Lab.
