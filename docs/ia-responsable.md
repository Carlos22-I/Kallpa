# Uso responsable de la IA en Kallpa (ficha del sistema)

## 1. Usos previstos y no previstos
- **Previsto:** orientar a las familias sobre alimentación rica en hierro, apoyar la adherencia al suplemento indicado y ayudar al personal de salud a priorizar el seguimiento.
- **No previsto:** diagnosticar anemia, indicar o modificar dosis, reemplazar los controles CRED o el dosaje de hemoglobina, ni evaluar o sancionar a las familias.

## 2. Componentes y datos
| Componente | Recibe | No recibe |
|---|---|---|
| LLM de visión | Foto del plato (sin EXIF) + texto + catálogo de alimentos | Alias, código, sector, datos clínicos |
| Extractor local | Texto | Foto |
| Asistente | Pregunta + base de conocimiento + edad en meses | Nombre, código, estado de Hb |
| Priorización | Datos registrados en el sistema | — (no usa IA generativa) |

## 3. Salvaguardas
| Riesgo | Salvaguarda | Código |
|---|---|---|
| Cifras nutricionales inventadas | El LLM solo elige ids de un catálogo cerrado; el hierro se calcula con una tabla | `nutrition.py`, `to_plate_analysis` |
| Diagnóstico o dosis por la app | El estado de Hb y el esquema los registra solo el personal; el asistente tiene prohibido dosificar | `UpdateChildClinical`, `ASSISTANT_PROMPT`, `conocimiento.md` |
| Exceso de confianza en la foto | Confianza visible; estado "revisar" si es baja; la familia puede describir el plato | `LogMeal`, `familia.js` |
| Personas en la foto | Flag `persona_visible` → la foto no se guarda | `LogMeal` |
| Metadatos (GPS del celular) | Re-codificación sin EXIF | `LocalPhotoStorage` |
| Signos de alarma | El asistente deriva de inmediato al establecimiento | base de conocimiento |
| Caída del proveedor | Circuit breaker + respaldo local | `resilient.py` |
| Decisiones opacas | Prioridad con fórmula pública y razones | `risk.py` |
| Exclusión lingüística | Quechua chanka en texto (sufijos) y en el asistente | `local.py`, prompts |
| Culpabilizar a la familia | Mensajes en positivo ("para mejorar", "¡excelente plato!"); las alertas van al personal, no a terceros | frontend |

## 4. Equidad
- Las familias sin smartphone o con baja alfabetización pueden quedar fuera. Mitigación: uso asistido por el actor social durante la visita y evolución a WhatsApp y audio.
- Sesgo de registro: quien no registra no es "quien está bien". Por eso "sin registros" **suma** prioridad, no la resta.

## 5. Métricas para un piloto
- Concordancia entre los alimentos detectados por la IA y la validación del nutricionista (precisión y recall por alimento).
- Error medio en gramos estimados frente a porciones pesadas.
- Adherencia al suplemento y hemoglobina a 3 y 6 meses (frente a un grupo de comparación).
- % de alertas atendidas en menos de 72 h y equidad por sector.

## 6. Limitaciones
- Valores de hierro referenciales hasta validarlos con la TPCA (CENAN-INS).
- La estimación de gramos por foto es aproximada.
- El puntaje es educativo y no clínico.
