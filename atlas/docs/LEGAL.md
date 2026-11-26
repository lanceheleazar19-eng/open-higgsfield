# VISTAN LEGAL — departamento de inteligencia jurídica

`/legal` (menú Inteligencia). Protegido con el mismo PIN y sesión que LIFE OS. Migración 0016 (tablas `lg_*` y columna
`documents.vault`). **Información jurídica, no asesoramiento profesional.**

## Arquitectura (reutiliza VISTAN, sin duplicar)
| Pieza | Reutiliza |
|---|---|
| Texto, chunks y búsqueda semántica/RAG | Gestor documental (`documents`/`doc_chunks`), marcado como bóveda `legal` y filtrado por expediente |
| Búsqueda y lectura web | Buscador y lector del Research Engine, restringidos a dominios oficiales |
| IA | Router del META-BRAIN; **solo modelos locales** salvo autorización expresa en Seguridad |
| Acceso | PIN/sesión de LIFE OS · Auditoría, copias y kill switch de VISTAN |
| Tareas, notificaciones, proyectos, LIFE OS | Recordatorios de plazos y tareas de expediente; alertas; vínculos a Proyectos y a empresas/oportunidades |
| Agentes | `VISTAN LEGAL AGENT` en el registro (colabora con Research, Business, Finance, Memory, Planning, Security) |
| Automatizaciones | Paso `legal_scan` (plazos, contratos y cumplimiento → alertas) |

## Operativo sin credenciales
- Command Center con datos reales y buscador jurídico (detecta jurisdicción y rama y pregunta lo que falta).
- Legal Research Engine: classify → plan → search (solo dominios oficiales) → read → vigencia (API BOE / EUR-Lex) → analyze →
  synthesize → verify (cada norma, artículo y resolución contra la fuente leída). Informe con legislación, jurisprudencia,
  criterios, interpretación, aplicación, riesgos, conclusión y fuentes con fecha de consulta. Reanudable.
- Contract Analyzer: PDF, DOCX, TXT, RTF, ODT; DOC con `textutil` (macOS); escaneados/imágenes con OCR del modelo de visión
  local. Reglas + IA local; riesgos CRÍTICO/ALTO/MEDIO/BAJO con fragmento original validado, consecuencia, recomendación y
  redacción alternativa; contradicciones, información ausente, obligaciones. Comparación visual de versiones.
- Document Studio: 14 tipos de borrador, filtro que elimina datos no aportados (DNI/NIE/CIF, IBAN, email, teléfono, fechas,
  nombres, direcciones) → `[[PENDIENTE: …]]`; guardado automático, versiones, comparación, restaurar, duplicar, comentarios,
  etiquetas, exportación PDF/DOCX.
- Expedientes (número interno, estados, partes, cronología, notas, tareas, plazos, documentos, investigaciones, exportación).
- Riesgos y plazos (VISTAN no calcula plazos: los registras con su regla; los no verificados se señalan), cumplimiento por
  tipo de negocio (confirmadas / potenciales / asesoramiento) con norma y enlace oficial, base de conocimiento (originales vs
  conclusiones de IA), Legal Agent por expediente, informes PDF/DOCX de 7 tipos.
- Integración entre agentes: `POST /api/legal/agent/obligations` (p. ej. VISTAN SHOPIFY → obligaciones, fuentes,
  documentación necesaria, revisión profesional).

## Necesita conexión, instalación o credenciales
| Función | Requisito |
|---|---|
| Investigación, vigencia BOE/EUR-Lex | Internet (sin clave). **No probado contra los servicios reales** en el entorno de desarrollo: se probó con respuestas simuladas |
| OCR de escaneados e imágenes | `ollama pull qwen2.5vl:7b` |
| Archivos .doc antiguos | macOS (`textutil`) o `antiword`; si no, convertir a DOCX |
| Modelos en la nube | Autorización en LEGAL → Seguridad + claves en Configuración → Modelos |
| Aranzadi, vLex, Tirant, La Ley… | Suscripción de pago: **no integradas** y nunca simuladas |
| CENDOJ | Sin API pública: se localizan resoluciones vía poderjudicial.es |
| VISTAN SHOPIFY | El módulo no existe todavía en VISTAN; el punto de integración está preparado |

## Seguridad
Originales cifrados (Fernet) con clave en el Llavero; texto en la base de datos local (protégela con FileVault). Bóveda
aislada de la búsqueda general, del grafo, de los proyectos y del chat; búsqueda, agente y comparación limitados al
expediente. Contenido externo neutralizado ante prompt injection. Eliminación controlada. Registro de actividad.

## Limitaciones
- La calidad del análisis depende del modelo local (7B): por eso las reglas deterministas y la validación de fragmentos.
- La verificación de citas es literal (la norma/artículo aparece en la fuente leída); no sustituye la lectura jurídica.
- La API de datos abiertos del BOE se integró según su documentación pública; si cambia el formato, la vigencia queda como
  «no comprobada» (nunca se asume vigente).
- La lista de cumplimiento es un punto de partida con referencias oficiales; su aplicación concreta requiere revisión.
