# Análisis de actas del Ayuntamiento de Yecla

Instrucciones para todos los años: donde pone `<año>`, el año de las actas que analizas. Hay dos pasadas:
la primera escribe un JSON por acta (`json/`) y la segunda, solo para los Plenos, las votaciones por grupo
(`votos/`, ver «Segunda pasada» al final).

Objetivo: entender qué hay en cada acta para diseñar una web ciudadana, muy sencilla, que explique
qué decide el Ayuntamiento, quién recibe dinero (subvenciones, contratos, pagos) y qué empresas o
instituciones piden permisos especiales (licencias, autorizaciones en suelo no urbanizable, interés
público, ocupación de vía pública, etc.).

Textos: `analisis/<año>/txt/<doc>.txt`, extraídos con `pdftotext -layout`. Las columnas de la cabecera salen
mezcladas y en cada página se repiten el pie "Código Seguro de Verificación" y los bloques "FIRMADO POR":
ignóralos. Las actas escaneadas se leen con `analisis/ocr.sh <doc>` (tesseract) y pueden tener errores de
lectura: si una cifra o un nombre no se lee bien, compruébalo en otra parte del acta y no lo adivines. Lee cada documento ENTERO, por trozos (Read con offset/limit), sin saltarte puntos.

## Privacidad (obligatorio)
- NUNCA escribas el nombre de una persona física particular (vecinos, solicitantes, autónomos,
  trabajadores, opositores, herederos...). Ponla como "particular". Aunque el acta la nombre: la
  anonimización del Ayuntamiento falla a veces ("D. ………." y unas líneas después el nombre completo).
- Sí puedes nombrar: empresas (S.L., S.A., S.Coop., etc.), asociaciones, fundaciones, clubes, peñas,
  cofradías, comunidades de regantes, colegios, administraciones y organismos públicos, partidos y
  grupos municipales, y cargos públicos en el ejercicio de su cargo (alcaldesa, concejales, secretario,
  interventora) SOLO en el campo `votacion`/`debate` si hace falta; mejor por grupo político.
- Comunidades de bienes (C.B.) y sociedades civiles (S.C.) suelen llevar nombres de personas: ponlas
  como "particular (C.B.)" salvo que el nombre sea claramente comercial.
- No copies referencias catastrales, direcciones de viviendas particulares, DNI ni matrículas.
- Hay un control en código: `uv run actas check <año>` da ERROR si un nombre que el acta escribe con
  tratamiento («D. Juan…», «Dña. Ana…») aparece en tus JSON (también en `texto_acta`), o si una entidad tiene
  nombre de persona. No sustituye a estas reglas: un particular descrito sin nombre no lo detecta.

## Salida: un fichero JSON por documento
Escribe `analisis/<año>/json/<doc>.json` (mismo nombre que el .txt) con esta forma:

```json
{
  "doc": "2026-01-07_JGL_01",
  "organo": "JGL",                       // JGL o PLENO
  "sesion": 1,
  "fecha": "2026-01-07",
  "tipo_sesion": "ordinaria",            // ordinaria / extraordinaria / extraordinaria y urgente
  "paginas": 25,
  "resumen": "2-4 frases en lenguaje muy llano: lo más importante que se decidió.",
  "puntos": [
    {
      "ref": "2.3",                      // numeración del acta (punto.subpunto)
      "titulo": "título corto en lenguaje llano (máx. 90 caracteres)",
      "categoria": "subvencion_concedida",
      "resumen": "1-2 frases llanas: qué se decide, para qué y a quién",
      "entidades": [
        {"nombre": "FCC Aqualia, S.A.", "cif": null, "tipo": "empresa", "rol": "cobra"}
      ],
      "hay_particulares": false,         // true si afecta a personas físicas (sin nombrarlas)
      "importe_eur": 16243.77,           // null si no hay; si hay varios, el total y detalle en "importes"
      "importes": [],                    // opcional: [{"concepto": "...", "eur": 123.4, "entidad": "..."}]
      "resultado": "aprobado",           // aprobado / denegado / desestimado / informado / aplazado / retirado / otro
      "votacion": "unanimidad",          // en JGL casi siempre unanimidad; en Pleno detalla por grupos: "a favor PP y Vox; en contra PSOE..."
      "expediente": "1186986R",
      "lugar": null,                     // paraje, polígono/parcela, calle (solo si NO es vivienda particular), pedanía
      "interes": 1                       // 1 rutina, 2 relevante, 3 muy relevante para un vecino (dinero grande, polémica, suelo, empresas conocidas)
    }
  ],
  "notas": "observaciones: calidad del texto, fallos de anonimización (sin nombres), cosas raras"
}
```

Una línea de "liquidación de obligaciones" con muchas facturas: un punto con `importes` detallado
(empresa, concepto, euros) e `importe_eur` = total. Las bonificaciones fiscales a particulares, en un
solo punto por tipo si son muchas.

### Categorías (`categoria`)
- `subvencion_concedida`: el Ayuntamiento da dinero (a asociaciones, clubes, empresas, ONG, becas...).
  Incluye convenios con aportación económica municipal, premios, ayudas.
- `subvencion_recibida`: otra administración (CARM, Estado, UE, Diputación...) da dinero al Ayuntamiento.
- `contrato`: adjudicación, prórroga, modificación, revisión de precios, devolución de fianza de contratos.
- `pago_factura`: liquidación/aprobación de obligaciones, facturas, certificaciones de obra.
- `licencia_obra`: licencias urbanísticas, declaraciones responsables, primera ocupación.
- `licencia_actividad`: licencias de actividad, apertura, ambientales.
- `suelo_no_urbanizable`: autorizaciones excepcionales, interés público, actuaciones en suelo rústico/no urbanizable.
- `urbanismo_planeamiento`: plan general, planes parciales, estudios de detalle, convenios urbanísticos, reparcelaciones.
- `convenio`: convenios sin dinero municipal (o colaboración institucional).
- `personal`: plantilla, oposiciones, nombramientos, retribuciones, comisiones de servicio.
- `fiscal`: bonificaciones, exenciones, devoluciones de impuestos y tasas, precios públicos, ordenanzas fiscales.
- `patrimonio`: compras, ventas, cesiones, donaciones, alquileres de bienes municipales.
- `via_publica_eventos`: ocupación de vía pública, terrazas, ferias, fiestas, cortes de calle, uso de instalaciones.
- `presupuesto_hacienda`: presupuesto, modificaciones de crédito, cuenta general, informes de morosidad/intervención.
- `normativa`: ordenanzas y reglamentos no fiscales.
- `mocion_politica`: mociones, declaraciones institucionales, ruegos y preguntas, debates políticos.
- `organizacion`: actas anteriores, delegaciones, comisiones, calendario de sesiones, nombramientos de representantes.
- `informacion`: "disposiciones y comunicaciones para conocimiento", resoluciones recibidas, dación de cuenta.
- `reclamaciones`: responsabilidad patrimonial, recursos, sanciones, sentencias, expedientes de restauración de legalidad urbanística.
- `servicios_actividades`: programas, cursos y servicios municipales (cultura, deporte, escuelas infantiles,
  juventud, turismo, conciliación, horarios de servicios).
- `medio_ambiente`: arbolado, zonas verdes, agua, vertidos, lodos, plagas, permisos de la CHS.
- `otros`.

## Informe final (tu respuesta, no un fichero)
Máx. 400 palabras: qué tipos de asuntos predominan en tus documentos, los 5-10 asuntos más
relevantes para un vecino (con doc y ref), qué empresas/instituciones aparecen más (recibiendo dinero
o pidiendo permisos), problemas de calidad (texto ilegible, OCR, anonimización fallida: cuántos casos,
sin nombres) y cualquier dato que creas útil para la web. Confirma la lista de JSON escritos.

## Segunda pasada: votaciones del Pleno por grupo político

Para cada punto del Pleno, cuántos concejales de cada grupo votaron a favor, en contra o se
abstuvieron, para hacer gráficas en la web. La fuente es SIEMPRE el texto del acta
(`analisis/<año>/txt/<doc>.txt`), no el campo `votacion` de los JSON, que es un resumen y puede tener
errores. Úsalo solo como pista.

Composición del Pleno: la de `analisis/municipio.json` (`legislaturas`), según la fecha de la sesión
(`inicio`). Usa exactamente esas claves de grupo y solo los grupos de esa legislatura.

El 17-06-2023 hay dos sesiones, una de cada corporación. Para actas anteriores a la primera legislatura de
`municipio.json` hay que añadirla antes allí, con su fecha de inicio, los grupos que diga el acta de la sesión
constitutiva y un color para cada grupo nuevo (`colores_grupos`).

Si en alguna sesión falta alguien, el acta lo dice en la lista de asistentes o en la votación: cuenta solo a
los presentes.

Privacidad: no escribas nombres de concejales ni de nadie. Solo grupos y números.

### Salida: `analisis/<año>/votos/<doc>.json`

```json
{
  "doc": "2026-03-02_PLENO_03",
  "asistentes": {"PP": 9, "PSOE": 7, "Vox": 3, "IU-Verdes": 2},
  "notas": "",
  "votaciones": [
    {
      "punto_idx": 4,                 // posición (desde 0) del punto en la lista "puntos" de json/<doc>.json
      "punto_ref": "5",               // la "ref" de ese punto, para comprobar
      "que": "propuesta",             // propuesta / moción / enmienda de X / dejar sobre la mesa / urgencia / otra
      "final": true,                  // true en la votación que decide el punto; false en enmiendas y previas
      "unanimidad": false,
      "votos": {
        "PP":        {"favor": 9, "contra": 0, "abstencion": 0},
        "PSOE":      {"favor": 0, "contra": 7, "abstencion": 0},
        "Vox":       {"favor": 0, "contra": 0, "abstencion": 3},
        "IU-Verdes": {"favor": 0, "contra": 0, "abstencion": 2}
      },
      "resultado": "aprobada",        // aprobada / rechazada / aprobada con voto de calidad / rechazada con voto de calidad
      "texto_acta": "cita literal corta del acta con el resultado de la votación (máx. 300 caracteres)"
    }
  ]
}
```

Reglas:
- Un registro por cada votación que haya en el acta (enmiendas, "dejar sobre la mesa", urgencia,
  propuesta final...). Los puntos sin votación (dación de cuenta, información, ruegos y preguntas) no
  llevan registro.
- "Por unanimidad": `unanimidad: true` y todos los presentes a favor (según `asistentes` de esa
  sesión o lo que diga el acta si alguien sale de la sala).
- Si el acta da solo totales ("12 votos a favor (PP y Vox)"), reparte por grupo según su tamaño y
  comprueba que la suma cuadra. Si un grupo vota dividido y el acta lo dice, refléjalo.
- La suma de favor + contra + abstención de cada grupo no puede superar sus asistentes.
- Empates: indica si decide el voto de calidad de la Alcaldía (PP).
- Al terminar, valida con `uv run actas check <año>` (ver abajo).

### Informe final de la segunda pasada (tu respuesta)
Máx. 200 palabras: ficheros escritos, número de votaciones por fichero, casos dudosos (y por qué) y
cualquier incoherencia entre el acta y el campo `votacion` del JSON.

## Comprobación al terminar un año

```bash
uv run actas check <año>
```

Comprueba las votaciones (grupos de la legislatura, sumas, que cada votación apunte a su punto) y busca cada
importe en el texto del acta. Escribe, sin versionar, `no_encontrados.json` (importes que no aparecen tal cual:
hay que mirarlos a mano, suelen ser cálculos), `dinero.json` y `resumen.json`. Falla si hay errores en las
votaciones o si un nombre de persona llega a lo que se publica: si es un particular, se corrige en
`revision.json` con una nota que empiece por «Privacidad»; si no lo es (una calle, una obra, un cargo público),
su frase va en `analisis/nombres_revisados.json`.

Las correcciones de una ficha no se hacen en el JSON de la IA, que no se toca: van en
`analisis/<año>/revision.json` (con `uv run actas review --year <año>` o con
`actas.revision.data.save_review`).
