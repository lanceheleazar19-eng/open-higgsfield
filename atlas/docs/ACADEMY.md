# VISTAN ACADEMY — universidad personal con IA

`/academy` (menú Inteligencia). Mismo PIN y sesión que LIFE OS. Migración 0017.

## Arquitectura (amplía lo existente, sin duplicar)
| Pieza | Reutiliza |
|---|---|
| Asignaturas, lecciones, evaluaciones, regla de dominio | Academia de LIFE OS (`lf_subjects`, `lf_lessons`, `lf_assessments`), ampliadas con categoría, curso, progreso, minutos y criterios |
| Nuevas tablas solo para lo que faltaba | `ac_courses`, `ac_paths`, `ac_concepts` (repetición espaciada), `ac_sessions` (tiempo real), `ac_tutor`, `ac_labs` |
| IA | Router de modelos de VISTAN (fallback, registro de llamadas) |
| Profesores | 12 personas del Learning Agent + Academy Coordinator (no son agentes nuevos del registro) |
| VISTAN CORE / META-BRAIN | Learning Agent con la herramienta `academy.overview` |
| Código | Sandbox aislado del Innovation Lab (ejercicios y tests) |
| Investigación | Research Engine de VISTAN |
| Negociación | Simulador de LIFE OS (4 escenarios de negociación nuevos) |
| Trading | Datos históricos del Trading Desk (solo backtesting) |
| Voz | Motor de voz de VISTAN (reconocimiento y síntesis del navegador; sin grabaciones guardadas) |
| Tareas / calendario, objetivos, proyectos, documentos | Recordatorios de repaso, Objetivos (área «aprendizaje»), cursos vinculados a proyectos, lecciones desde documentos |
| Automatizaciones | Paso `academy_reviews` |

## Operativo (con Ollama)
Command Center con datos reales y CONTINUAR APRENDIZAJE · biblioteca de 9 áreas ampliable · profesor por texto y voz con
10 acciones · Course Builder (editar, reordenar, pausar, eliminar) · Lesson Engine (12 apartados, recuerda dónde te quedaste,
preguntas en mitad de la clase) · exámenes de 6 tipos con criterios definidos · repetición espaciada (consolidar exige ≥3
aciertos espaciados ≥7 días) y refuerzo de errores repetidos · Knowledge Tracker · laboratorios (finanzas, empresa, trading,
programación, negociación, pensamiento crítico) · investigación con material verificado/interpretación/hipótesis/IA ·
itinerarios con desbloqueo por nota · memoria educativa exportable y borrable · gamificación opcional.

## Necesita conexión o instalación
| Función | Requisito |
|---|---|
| Investigación y material con fuentes | Internet (sin clave) |
| Backtesting con símbolos del Trading Desk | Internet (o pegar una serie de precios) |
| Modelos en la nube | Claves en Configuración → Modelos (opcional) |
| Corrección de pronunciación | No disponible: el reconocimiento del navegador no la evalúa |
| Vídeos | VISTAN no recomienda vídeos concretos; ofrece una búsqueda externa |

## Limitaciones
La calidad de las clases depende del modelo (qwen2.5:7b en local); el contenido se marca como generado por IA. Las
preguntas abiertas se corrigen con rúbrica: la IA solo decide si cada criterio se cumple. Los simuladores son modelos
didácticos simplificados y siempre con dinero virtual.
