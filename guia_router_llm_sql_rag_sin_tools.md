# 🧭 Guía Definitiva (sin Tools): Router LLM → SQL / RAG → Síntesis

> **Objetivo:** Tener en tu front un “assistant” que combine **RAG (vector)** y **SQL real** sobre tu DB **sin usar Tools** de OpenAI.  
> El LLM **solo** decide y redacta; **vos** ejecutás (SQL/RAG) en tu backend.

---

## 0) Conceptos clave, sin vueltas

- **LLM**: el “cerebrito” (modelo) de OpenAI al que llamás por **API**. No ejecuta en tu DB; **escribe texto**.
- **Router**: tu **lógica en backend** que hace la **PASADA 1** al LLM para que **decida** si usar `SQL`, `RAG` o `BOTH` y te devuelva **formato fijo**.
- **Salida estructurada**: molde/plantilla que vos imponés para poder **parsear** (`MODE`, `SQL`, `RAG_QUERY`, `REASON`).
- **RAG**: búsqueda en tu **vector store** (PDFs, docs). **CSV/Sheets → DB** (no vector). Podés subir un **resumen** al vector para contexto.
- **Solo SELECT**: seguridad y determinismo. Usuario DB **read-only**, `READ ONLY`, `statement_timeout`, `LIMIT`, **whitelist** de tablas/columnas.

---

## 1) Paso a paso general (Minuta final de flujo)

1. **Front → Backend**  
   Envía `{ user_text, thread_id? }` a `/chat`.
2. **Backend → LLM (PASADA 1: “router”)**  
   Le mandás:
   - **Prompt del router** (instrucciones + formato obligatorio).
   - **DB_SCHEMA whitelisteado** (JSON con tablas/columnas/relaciones y 2–3 filas de ejemplo).
   - **user_text**.
   <br>El LLM devuelve **formato fijo**:
   ```
   MODE: SQL | RAG | BOTH
   RAG_QUERY: <texto o vacío>
   SQL:
   ```sql
   <solo SELECT válido; si devuelve filas detalladas, con LIMIT 200>
   ```
   REASON: <1–2 líneas>
   ```
3. **Backend ejecuta según MODE**  
   - `SQL`: validás y corrés el SELECT (read-only) → **RESULTADOS_SQL (JSON)**.
   - `RAG`: embedding(query) → similarity search → **RESULTADOS_RAG (chunks)**.
   - `BOTH`: hacés ambas y juntás.
4. **Backend → LLM (PASADA 2: “síntesis”)**  
   Le pasás `RESULTADOS_SQL` y/o `RESULTADOS_RAG`. Pedís **respuesta final** clara (mini tabla + citas).
5. **Backend → Front**  
   Devolvés `texto_final` + (opcional) **tablas**, **citas**, y **traza** (MODE, SQL ejecutado, latencias, filas).

---

## 2) Prompt del **router** (PASADA 1) — Plantilla para copiar

**Instrucciones (mensaje de sistema):**
```
Sos un enrutador. Decidís si responder con SQL, con RAG o con ambos.

REGLAS:
- Usá SOLO las tablas/columnas del SCHEMA permitido (abajo).
- Si el pedido requiere números exactos, filtros, agregaciones o joins → devolvé MODE: SQL y escribí un SELECT válido (sin DML/DDL, sin ';', sin comentarios). Si devolvés filas detalladas, agregá LIMIT 200.
- Si el pedido es conceptual/explicativo (definiciones, políticas) → devolvé MODE: RAG y una RAG_QUERY clara.
- Si necesita texto + números → MODE: BOTH (incluir RAG_QUERY y SQL).
- Nombres de tabla/columna EXACTOS, según el SCHEMA.
- FORMATO OBLIGATORIO (sin nada fuera del molde):

MODE: <SQL|RAG|BOTH>
RAG_QUERY: <texto o vacío>
SQL:
```sql
<solo SELECT válido; si son filas detalladas, con LIMIT 200>
```
REASON: <1-2 líneas>
```
```

**SCHEMA (pegá tu JSON whitelisteado):**
```json
{
  "tables": {
    "estaciones": {
      "columns": {
        "id": "int (PK)",
        "tiene_full": "boolean (o texto: 'si'|'no')"
      },
      "description": "Estaciones de servicio (puestos de gasolina)"
    },
    "empleados": {
      "columns": {
        "id": "int (PK)",
        "estacion_id": "int (FK -> estaciones.id)"
      },
      "description": "Empleados; cada empleado pertenece a una estación"
    }
  },
  "relationships": [
    "empleados.estacion_id -> estaciones.id (N:1)"
  ],
  "synonyms": {
    "puesto de gasolina": "estaciones",
    "usuarios": "empleados",
    ""tiene full"": "estaciones.tiene_full"
  },
  "rules": [
    "Solo SELECT",
    "JOINs explícitos en FKs",
    "Si 'tiene_full' es booleano: TRUE/FALSE; si es texto: 'si'/'no'",
    "LIMIT cuando devuelvas filas"
  ],
  "examples": {
    "estaciones": [
      {"id": 101, "tiene_full": "si"},
      {"id": 102, "tiene_full": "no"}
    ],
    "empleados": [
      {"id": 1, "estacion_id": 101},
      {"id": 2, "estacion_id": 101},
      {"id": 3, "estacion_id": 102}
    ]
  }
}
```

**Mensaje del usuario (ejemplo):**
```
Devolveme la cantidad de empleados que trabajen en un puesto de gasolina con "tiene_full" = si.
```

**Respuesta esperada del LLM (ejemplo):**
```
MODE: SQL
RAG_QUERY:
SQL:
```sql
SELECT COUNT(*) AS cantidad_empleados
FROM empleados e
JOIN estaciones s ON s.id = e.estacion_id
WHERE s.tiene_full IN ('si','sí','true','1');
```
REASON: Es un conteo numérico con join; no requiere texto de RAG.
```

---

## 3) Ejecución en backend (después de PASADA 1)

- **Validador SELECT-only** (ideas rápidas):
  - Rechazar si matchea `UPDATE|DELETE|INSERT|MERGE|ALTER|DROP|TRUNCATE|CREATE|GRANT|COPY|ATTACH|;|--|/*`.
  - Permitir solo `SELECT` (+ `WITH` si querés), **usuario read-only**, `SET TRANSACTION READ ONLY`, `statement_timeout` (5–10s).
  - **Whitelist** de tablas/columnas.
  - Si la consulta devuelve filas detalladas, **agregar LIMIT** si falta.
- **Ejecutar SQL** con SQLAlchemy/psycopg (read-only) → `RESULTADOS_SQL` (JSON).
- **RAG (si aplica)**: embedding(query) → top-k con MMR (opcional) → `RESULTADOS_RAG = [{i,title,page,snippet,url}, ...]`.

> **Sugerencia:** loguear `thread_id`, `MODE`, `SQL`, `duración_ms`, `filas`, `usuario_app`.

---

## 4) Prompt de **síntesis** (PASADA 2) — Plantilla para copiar

**Instrucciones (mensaje de sistema):**
```
Con los RESULTADOS_SQL y/o RESULTADOS_RAG dados, redactá la respuesta final clara y concisa.
- No inventes valores.
- Si hay números de SQL, mostralos de forma directa.
- Si hay RAG, agregá citas como [1], [2] según el índice provisto.
- Si falta info, decilo explícitamente.

DATOS:
RESULTADOS_SQL: <pegá JSON>
RESULTADOS_RAG: <pegá lista de chunks o vacío>
```

**Ejemplo de datos (solo SQL):**
```json
RESULTADOS_SQL: { "cantidad_empleados": 342 }
RESULTADOS_RAG: []
```

**Respuesta final esperable (ejemplo):**
```
La cantidad de empleados que trabajan en estaciones con "tiene_full = sí" es 342.
```

---

## 5) Endpoints mínimos del backend

- `GET /schema` → JSON con **tablas/columnas permitidas**, relaciones y 2–3 ejemplos por tabla.
- `POST /chat` → orquesta:
  1) PASADA 1 (router) → parsea `MODE/SQL/RAG_QUERY`.
  2) Ejecuta SQL y/o RAG → junta `RESULTADOS_*`.
  3) PASADA 2 (síntesis) → genera `texto_final` (y opcional: tabla/citas).
  4) Devuelve a front: `texto_final` + `traza` (MODE, SQL, ms, filas) + (opcional) tabla/citas.
- `POST /ingest` → ingesta:
  - **PDF/Docs** → chunk → **vector**.
  - **CSV/Sheets** → **DB** (y opcional: **doc-resumen** al vector con descripción de columnas).

---

## 6) Seguridad express (SELECT-only)

- Usuario DB **solo lectura** (rol sin permisos de escritura).
- `SET TRANSACTION READ ONLY;`
- `statement_timeout = 5–10s` (o lo que te sirva).
- Rechazar `UPDATE|DELETE|INSERT|MERGE|ALTER|DROP|TRUNCATE|CREATE|GRANT|COPY|ATTACH|;|--|/*`.
- **Whitelist** de tablas/columnas.
- **LIMIT** auto cuando devuelvas filas detalladas.
- Auditoría: guardar **consulta**, **parámetros**, **origen**, **latencia**.

---

## 7) Ejemplos de SQL (variantes)

**Conteo global (texto 'si'/'sí' o truthy):**
```sql
SELECT COUNT(*) AS cantidad_empleados
FROM empleados e
JOIN estaciones s ON s.id = e.estacion_id
WHERE s.tiene_full IN ('si','sí','true','1');
```

**Conteo por estación (top-5):**
```sql
SELECT s.id AS estacion_id, COUNT(*) AS cantidad_empleados
FROM empleados e
JOIN estaciones s ON s.id = e.estacion_id
WHERE s.tiene_full IN ('si','sí','true','1')
GROUP BY s.id
ORDER BY cantidad_empleados DESC
LIMIT 5;
```

**Si 'tiene_full' es boolean:**
```sql
SELECT COUNT(*) AS cantidad_empleados
FROM empleados e
JOIN estaciones s ON s.id = e.estacion_id
WHERE s.tiene_full = TRUE;
```

---

## 8) Checklist de implementación

- [ ] Vector store listo (PDFs/Docs) + endpoint `/ingest`.
- [ ] CSV/Sheets cargan a **DB** (no a vector); opcional: resumen al vector.
- [ ] `GET /schema` devuelve whitelist clara (tablas/cols/relaciones + ejemplos).
- [ ] **PASADA 1 (router)** con molde `MODE/RAG_QUERY/SQL/REASON`.
- [ ] Validador **SELECT-only** + read-only + timeout + LIMIT + whitelist.
- [ ] **PASADA 2 (síntesis)** consume `RESULTADOS_*` y redacta.
- [ ] `/chat` retorna `texto_final` + traza (debug friendly).

---

## 9) TL;DR (hiper corto)

1) **Router (P1)**: el LLM **escribe** si es `SQL`, `RAG` o `BOTH` y, si toca, te da el **SELECT**.  
2) **Vos ejecutás** (SQL/RAG) en tu backend.  
3) **Síntesis (P2)**: le pasás los **resultados crudos** y el LLM redacta **el texto final**.  
4) **Front** muestra: texto + (opcional) tabla/citas + traza.  
**Sin Tools.** El LLM no toca tu DB: vos controlás todo.
