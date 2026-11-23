# Texto para Devpost

> La página del evento parece estar originalmente en inglés y la jueza es internacional: pega la versión en **inglés** en los campos y añade la versión en español al final. En el video, narración en español con **subtítulos en inglés**.

## Campos cortos
- **Project name:** Kallpa — AI against child anemia in the Peruvian Andes
- **Elevator pitch:** Families snap a photo of their child's plate (Spanish or Quechua); AI recognizes Andean foods, iron is computed from a food table, and nurses get explainable priorities and visit routes.
- **Built with:** python, flask, claude, anthropic-api, openai-compatible-api, gemini, sqlite, bm25, leaflet, openstreetmap, javascript, html5, css3, pillow, pytest, docker, render, github-actions
- **Try it out:** `<URL Render>` · `<URL GitHub>` · demo family code: `K-DEMO1` · health panel token: `<token>`
- **Video:** `<URL YouTube>`

---

## Inspiration
In Apurímac, in the Peruvian Andes, **55.8% of children aged 6–35 months had anemia in 2023**, one of the highest rates in Peru, and the trend is rising. Anemia in the first years harms brain development, learning and immunity, sometimes permanently. The causes are everyday ones: too little iron-rich animal food, watery soups instead of thick meals, tea with lunch, and **families giving up the iron supplement** because they forget, the child has side effects, or no one follows up. Nurses learn about it weeks later, at the next check-up.

*Kallpa* means **strength** in Quechua.

## What it does
**For families (mobile web app):**
- Take a photo of the child's plate, or describe it in **Spanish or Quechua** ("huk tortilla runtu yawarwan"). The AI recognizes the foods and portions, and Kallpa computes the **iron content** and a 0–100 "iron plate" score with the reasons and concrete tips ("add 2 spoonfuls of chicken blood or liver", "give tea at least an hour away from lunch").
- Log the **daily iron supplement** and report side effects.
- Get **local recipes** (blood sausage omelet, quinoa with spleen, trout with olluco) chosen for the child's age and the iron still missing today.
- Ask a **bilingual assistant** grounded in validated content. It never gives doses or diagnoses and refers families to the clinic when there are warning signs.

**For the health facility (dashboard):**
- Children **ranked 0–100 with explainable reasons**: hemoglobin status recorded by the clinic, supplement adherence, diet, age, overdue check-ups and side effects.
- **Alerts:** side effects, 3 days without the supplement, severe anemia.
- **Optimized home-visit route** for nurses walking Abancay's steep streets (about 25% less walking in our demo).
- Record lab results and the prescribed scheme, see risk by neighborhood and an adherence trend per child.

## How we built it
- **Hexagonal architecture** (ports & adapters) in Python/Flask with a pure domain, use cases, swappable adapters and a single composition root; 7 ADRs and C4 diagrams.
- **"The LLM perceives, the domain computes":** a multimodal LLM (Claude or any OpenAI-compatible model such as Gemini) may only return ids from a **closed catalog of 42 Andean foods** plus grams. We validate that output and compute iron deterministically from a versioned food table, so the model never invents nutrition numbers.
- **Resilience:** an LLM client (bridge) behind a provider chain with a **circuit breaker**, falling back to our **local Spanish/Quechua food extractor** that handles Quechua suffixes and quantities such as "iskay cucharadas".
- **Assistant:** RAG over a curated knowledge base, with a BM25 fallback.
- **Explainable risk scoring**, an exponential-smoothing adherence trend, an age-aware recipe recommender, and nearest-neighbor + 2-opt routing.
- **Privacy:** family codes instead of national ID numbers, mandatory consent, photos re-encoded without EXIF, and photos showing a person are never stored.
- 42 automated tests running in under a second in CI; Docker; one-click Render deploy.

## Responsible AI
Kallpa **does not diagnose and does not dose**: only health staff record hemoglobin status and the supplement scheme. The model's confidence is always shown. The LLM's role is limited to perception, and every number is traceable to a food table that nutritionists can audit. The priority formula is public. Data is minimized and families give consent. Missing records *increase* priority, so families who log less are not left behind.

## Challenges we ran into
- Preventing hallucinated nutrition values, which led to the closed-catalog design.
- Quechua text: agglutinative suffixes (*yawar-wan* = "with blood").
- Building something nurses would trust: explainability over black-box scores.
- Building without real patient data: a realistic simulation that we clearly label as simulated.

## Accomplishments
A complete working loop: plate → AI → iron → tips → supplement → prioritization → alert → visit route. Clean architecture, 42 tests, bilingual support, and a low-bandwidth design.

## What we learned
In health, the architecture is the safety feature: deciding *what the AI is allowed to decide* mattered more than the model itself.

## What's next
A pilot with a health facility in Abancay, with the food table validated against Peru's official food composition table (CENAN-INS); a WhatsApp channel with voice notes in Quechua; integration with Peru's health information systems; an impact evaluation of adherence and hemoglobin at 3 and 6 months.

*Demo data is simulated; nutrition values are reference values pending validation.*

---

## Versión en español (resumen)
**Kallpa** (fuerza, en quechua) ataca la anemia infantil en Apurímac, que llegó a 55.8 % en niños de 6 a 35 meses en 2023. La familia fotografía o describe (en español o quechua) el plato del niño. La IA reconoce los alimentos de un catálogo cerrado y Kallpa calcula el hierro con una tabla de alimentos, da un puntaje con razones y consejos, registra el suplemento y sugiere recetas locales. El establecimiento de salud ve a los niños priorizados de 0 a 100 con razones explicables, recibe alertas (molestias, 3 días sin suplemento, anemia severa) y planifica la ruta de visitas domiciliarias. Arquitectura hexagonal, circuit breaker con respaldo local, RAG, 42 pruebas. **No diagnostica ni dosifica:** eso lo hace el personal de salud.

## Galería sugerida
1. Portada: logo + "Wawanchikpa kallpan — la fuerza de nuestros niños".
2. Resultado de una foto real de un plato (puntaje, alimentos, consejos).
3. Registro del suplemento + semana.
4. Recetas sugeridas.
5. Panel: lista priorizada con razones.
6. Ruta de visitas + alertas.
7. Diagrama C4 de contenedores y secuencia "Registrar una comida".
