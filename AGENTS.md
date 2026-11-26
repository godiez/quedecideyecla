# Instrucciones para agentes

Proyecto: «Qué decide el Ayuntamiento», una web estática que explica qué decide el Ayuntamiento de Yecla
(dinero, decisiones, permisos y votaciones) a partir de sus actas oficiales. No es oficial ni partidista.

## Cómo está hecho

| Paso | Qué hace | Dónde |
|---|---|---|
| 1. Descarga | Registra las actas de yecla.es y descarga los PDF a `data/` (sin versionar) | `uv run actas discover` / `uv run actas fetch`; `src/actas/` (`listing`, `sync`, `http`, `catalog`) |
| 2. PDF → texto | `pdftotext -layout`; las escaneadas, con OCR | `analisis/ocr.sh <doc>` → `analisis/<año>/txt/` (sin versionar) |
| 3. Texto → JSON | Agentes de IA leen cada acta entera siguiendo unas instrucciones | `analisis/INSTRUCCIONES.md` → `analisis/<año>/json/` y `votos/` |
| 4. Comprobación | Votaciones, importes que no aparecen en el acta, cuentas y totales | `uv run actas check <año>`; `src/actas/checks.py` |
| 5. Revisión | Correcciones por encima de los JSON, sin tocarlos | `analisis/<año>/revision.json`; `uv run actas review --year <año>` |
| 6. Web | Carga los datos, calcula el dinero y los votos y genera `web/` | `uv run actas web`; `src/actas/` (`sources`, `money`, `votes`) y `src/actas/web/` |
| 7. Publicación | Copia pública del código y los datos, y la web en la rama `gh-pages` | `uv run actas publish` (no sube nada) |

Los datos se aplican en este orden: JSON de la IA → `reclasificacion.json` (automático) → `revision.json`
(correcciones). Una entidad se clasifica a mano en `analisis/<año>/alias.json`, dentro de `"_clase"`.

Lo propio del municipio (nombre, web del Ayuntamiento, páginas de actas, organismos regionales,
legislaturas con sus grupos y concejales, colores de los grupos, nombre y correo de la web) está en
`analisis/municipio.json` (`src/actas/municipality.py`), no en el código.

## Comandos

```bash
uv sync
uv run pytest                         # todas las pruebas
uv run actas check 2024               # comprobar un año analizado
uv run actas web                      # generar web/ (pasa el control de privacidad)
python3 -m http.server -d web 8010    # verla en http://127.0.0.1:8010/
```

## Reglas

- **Idioma:** el código (variables, funciones, clases, comentarios y docstrings) va en inglés. Los textos que
  ve el público, las claves de los datos (`importe_eur`, `puntos`…) y las URL van en español.
- **Comentarios:** solo cuando el código no se explica solo (un porqué que no se ve: un fallo del navegador,
  una regla de las actas o de privacidad, un motivo de rendimiento), en una línea si se puede. Nada de
  comentarios ni docstrings que repitan lo que hace el código o lo que dice el nombre.
- **Los JSON de la IA no se modifican.** Cualquier corrección de una ficha va en
  `analisis/<año>/revision.json` (`actas.revision.data.save_review`), con una nota que diga por qué.
- **Privacidad:** nunca se publica el nombre de una persona física particular, su dirección, DNI, matrícula
  ni referencia catastral, ni detalles que la identifiquen (cargo concreto + edad o salud…). Las personas
  físicas salen como «un particular» y no tienen ficha. `actas web` falla si el HTML contiene un DNI, NIE,
  referencia catastral, matrícula, correo o teléfono. `actas check` y `actas publish` fallan si un nombre que el
  acta escribe con tratamiento («D.», «Dña.») llega a lo que se publica, o si una entidad tiene nombre de persona
  (`src/actas/names.py`). Las calles, obras y cargos públicos ya revisados están en
  `analisis/nombres_revisados.json`.
- **Neutralidad:** la web cuenta lo que dicen las actas, sin opinar. Trata igual a todos los grupos
  municipales. Nada debe parecer oficial: el aviso de que no es oficial sale en todas las páginas.
- **Web:** generador en Python sin dependencias externas. Sin recursos de terceros (ni CDN ni fuentes
  externas). Funciona sin JavaScript. Texto base de 17 px o más, zonas táctiles de 44 px y contraste AA.
  Estilo de periódico local, sobrio.
- **Pruebas:** cada cambio de comportamiento lleva su prueba; `uv run pytest` tiene que pasar entero.
- **Commits:** en español, con prefijo (`feat`, `fix`, `datos`, `docs`, `refactor`), añadiendo los archivos
  por su ruta.
