# Guion del video (3:00 a 3:30 min)

Formato: grabación de pantalla + voz en español + **subtítulos en inglés**. Súbanlo a YouTube como "No listado".

Antes de grabar: despliegue con API key (para mostrar la foto), `python -m app.seed --reset`, y la **foto real de un plato** preparado por el equipo (sangrecita con arroz, por ejemplo) **sin personas**. Si filman a una familia, pidan su autorización por escrito; mejor usen solo manos y platos.

| Tiempo | En pantalla | Narración |
|---|---|---|
| 0:00–0:20 | Mercado de Abancay, platos típicos, texto "55.8 %" | "En Apurímac, más de la mitad de los niños de 6 a 35 meses tiene anemia. No es solo un número: afecta su cerebro, su aprendizaje y sus defensas. Y casi siempre empieza en el plato." |
| 0:20–0:35 | Logo de Kallpa | "Les presentamos Kallpa, que en quechua significa *fuerza*. Inteligencia artificial para que las familias y el establecimiento de salud venzan juntos a la anemia." |
| 0:35–1:15 | App familiar: foto del plato → resultado con puntaje, alimentos, hierro y consejos | "Una mamá toma la foto del almuerzo de su hija. La IA reconoce los alimentos y las porciones, y Kallpa calcula el hierro con una tabla de alimentos. Le dice qué tan bueno es el plato y cómo mejorarlo: por ejemplo, que el té quita el hierro o que dos cucharadas de sangrecita hacen la diferencia." |
| 1:15–1:30 | Escribir en quechua "huk tortilla runtu yawarwan" | "También funciona en quechua, y aunque no haya internet para la IA, Kallpa sigue funcionando con su modelo local." |
| 1:30–1:50 | Botón "Sí le di", nota "vomitó un poco", semana y recetas | "Cada día marca si le dio el suplemento. Si hay molestias, lo cuenta, y Kallpa le sugiere recetas con alimentos de la zona según la edad de su niña." |
| 1:50–2:35 | Panel: lista priorizada, leer las razones del #1, alertas, "Planificar ruta" | "En el establecimiento, la enfermera ve a los niños priorizados de 0 a 100 y **por qué**: anemia moderada, cinco días sin suplemento, control vencido. Recibe alertas y, con un clic, arma la ruta de visitas domiciliarias del día, caminando un cuarto menos." |
| 2:35–3:00 | Diagrama C4 + secuencia; `pytest` en verde | "Por dentro, una regla clave: **la IA percibe, el sistema calcula**. El modelo solo reconoce alimentos de un catálogo cerrado; los números salen de una tabla auditable, así nunca inventa cifras. Usamos arquitectura hexagonal, circuit breaker y 42 pruebas automatizadas." |
| 3:00–3:20 | Pantalla de uso responsable + equipo | "Kallpa no diagnostica ni da dosis: eso lo decide el personal de salud. Protege la privacidad: sin DNI, y no guarda fotos con personas. Wawanchikpa kallpan: por la fuerza de nuestros niños." |

## Para sumar en "Presentación e impacto"
- Cifra clara (55.8 %), un plato real y una historia de una familia (puede ser ficticia, aclarándolo).
- Si consiguen la opinión de una enfermera o nutricionista de Abancay (aunque sea por WhatsApp), muéstrenla: suma mucha credibilidad.
