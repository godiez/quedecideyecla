# Qué decide el Ayuntamiento (Yecla)

Web que explica, en lenguaje sencillo, qué decide el Ayuntamiento de Yecla: en qué se gasta el dinero, qué
contrata, qué subvenciones da, qué permisos concede y qué se vota en el Pleno. Todo sale de las actas
oficiales de la Junta de Gobierno Local y del Pleno que el Ayuntamiento publica en
[yecla.es](https://yecla.es/).

La web: **https://godiez.github.io/quedecideyecla/**

Es una iniciativa personal y sin ánimo de lucro. **No es una web oficial** ni tiene relación con el
Ayuntamiento ni con ningún partido político. Los resúmenes se hacen de forma automática y pueden tener
errores: ante cualquier duda vale el acta oficial, que cada ficha enlaza. Si ves un error, escribe a
quedecideyecla@gmail.com.

## Cómo se hace

1. **Descarga:** se registran las actas publicadas en yecla.es y se descargan los PDF.
2. **Texto:** se extrae con `pdftotext`; las actas escaneadas se leen con OCR (`analisis/ocr.sh`).
3. **Análisis:** agentes de IA leen cada acta entera y escriben un JSON por acta, siguiendo
   [`analisis/INSTRUCCIONES.md`](analisis/INSTRUCCIONES.md). En los Plenos, además, las votaciones por grupo.
4. **Comprobación:** `actas check` valida las votaciones y busca cada importe en el texto del acta.
5. **Revisión:** las correcciones van en `analisis/<año>/revision.json`, encima de los JSON, sin tocarlos.
6. **Web:** un generador en Python, sin dependencias, crea la web estática y comprueba que no publica datos
   personales (DNI, matrículas, referencias catastrales, teléfonos…).

## Uso

Hace falta [uv](https://docs.astral.sh/uv/). Para el texto de las actas, `pdftotext` (poppler) y, para
las escaneadas, `tesseract` con el idioma español.

```bash
uv sync
uv run actas discover        # registra las actas publicadas (analisis/municipio.json) en data/actas.sqlite
uv run actas fetch           # descarga los PDF a data/pdfs/<jgl|pleno>/<año>/
uv run actas status          # resumen por tipo y año
uv run actas check 2024      # comprueba el análisis de un año
uv run actas web             # genera la web en web/
python3 -m http.server -d web 8010   # y se ve en http://127.0.0.1:8010/
uv run pytest
```

`data/`, el texto de las actas (`analisis/<año>/txt/`) y `web/` no están en el repositorio: se regeneran
con los comandos de arriba.

## Datos

En `analisis/<año>/`:

- `json/<acta>.json`: lo que la IA extrajo de cada acta (asuntos, importes, entidades, resultado).
- `votos/<acta>.json`: votaciones del Pleno por grupo político.
- `revision.json`: correcciones de fichas concretas, con el motivo.
- `alias.json`: nombres de una misma entidad que se unifican y su clase.

Las personas físicas no aparecen con su nombre: salen como «particular». La web tiene además una página
de datos descargables en CSV.

## Para otro municipio

Lo propio de Yecla está en [`analisis/municipio.json`](analisis/municipio.json): el nombre, la web del
Ayuntamiento, las páginas con las actas de cada año, los organismos de la región que cuentan como
administración pública, las legislaturas con sus grupos y concejales, el color de cada grupo y el nombre,
correo y responsable de la web. Para otro pueblo:

1. Cambia `analisis/municipio.json`.
2. Adapta `src/actas/listing.py`, que lee las páginas de actas de yecla.es y los nombres de sus PDF:
   cada ayuntamiento las publica a su manera. Sus pruebas están en `tests/test_listing.py`.
3. Repasa `analisis/INSTRUCCIONES.md`, lo que siguen los agentes de IA al leer las actas.
4. Borra los datos de Yecla (`analisis/<año>/`) y empieza con `actas discover`, `actas fetch` y el análisis.
5. Vuelve a grabar el vídeo de presentación con `uv run video/record.py`, después de `actas web`, y a dibujar
   la imagen que sale al compartir un enlace con `uv run video/preview.py`.

## Licencia

- **Código** (`src/`, `tests/` y los scripts): licencia [MIT](LICENSE). Se puede usar, cambiar y
  redistribuir manteniendo el aviso de autoría.
- **Datos y textos** (`analisis/` y los contenidos de la web): licencia
  [Creative Commons Reconocimiento 4.0](LICENSE-DATOS) (CC BY 4.0). Se pueden reutilizar citando la fuente:
  las actas oficiales del Ayuntamiento de Yecla y este proyecto.

Las actas en sí son documentos públicos del Ayuntamiento y no están sujetas a propiedad intelectual.

## Autor

Diego Ibáñez Ortuño · [LinkedIn](https://www.linkedin.com/in/dibanezortuno/) · [X](https://x.com/p4r4bl3)
