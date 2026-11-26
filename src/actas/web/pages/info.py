from actas import municipality
from actas.votes import CURRENT, LEGISLATURES, legislature_of_year
from actas.web import routes
from actas.web.fmt import e, rel, slug
from actas.web.template import code_link, mailto, page, version
from actas.web.texts import EMAIL, INFO_PATH, INFO_TITLE, TOWN

GLOSSARY = [
    ("Comprometido", "Lo adjudicado o lo pagado a una entidad en el año (lo mayor de los dos), más las "
                     "subvenciones. Sirve para no contar dos veces un contrato y sus facturas. No es lo que la "
                     "entidad ha cobrado."),
    ("Adjudicado", "Dinero de un contrato que se ha dado a una empresa. Se cobra después, a medida que se hace "
                   "el trabajo y se aprueban sus facturas."),
    ("Pagado", "Facturas y certificaciones de obra que la Junta de Gobierno aprueba pagar."),
    ("Subvención", "Dinero que el Ayuntamiento da a una asociación, club, institución o persona, normalmente "
                   "para una actividad concreta."),
    ("En especie", "Lo que se da sin dinero: uso gratuito de instalaciones o locales municipales, valorado en "
                   "euros. No se suma al dinero comprometido."),
    ("Fianza", "Dinero que se deja como garantía (por ejemplo, para reponer la acera si una obra la estropea) y que "
               "se devuelve si todo va bien. No es un gasto del Ayuntamiento."),
    ("Licitación", "Cuando el Ayuntamiento anuncia que quiere contratar algo y pide ofertas. Todavía no es "
                   "dinero de nadie; no cuenta hasta que se adjudica."),
    ("Expediente", "El número con el que el Ayuntamiento identifica cada asunto (por ejemplo, 1362210J). "
                   "Sirve para buscarlo en el acta."),
    ("Unanimidad", "Todos los concejales y concejalas presentes votan lo mismo."),
    ("Dividido", "En una votación, los concejales y concejalas de un mismo grupo votan cosas distintas en igual "
                 "número."),
    ("Un particular", "Una persona. Por privacidad no se publica su nombre ni la dirección de su vivienda."),
    ("Pendiente de clasificar", "Una entidad de la que no sabemos con seguridad si es empresa o asociación."),
    ("Sin identificar", "Dinero de ayudas a particulares o de asuntos en los que el acta no dice quién lo "
                        "recibe."),
    ("M€", "Millones de euros. 1,5 M€ son 1.500.000 €."),
]


def glossary() -> str:
    items = "".join(f'<dt id="{slug(t)}">{e(t)}</dt><dd>{e(d)}</dd>' for t, d in GLOSSARY)
    return f'<h2 id="glosario">Qué significa cada palabra</h2><dl class="glossary">{items}</dl>'


def code_paragraph() -> str:
    url = municipality.load().code_url
    if not url:
        return ""
    return (f"<p>El código que hace todo esto es libre y está publicado, con los datos de cada acta: "
            f"{code_link(e(url.removeprefix('https://')))}.</p>")


def _year_row(year: int, first: str, second: str) -> str:
    return f'<li><span class="year">{year}</span> {first} · {second}</li>'


def _sources(years: list[int]) -> str:
    town = municipality.load()
    return "".join(_year_row(y, f'<a href="{e(town.jgl_year_url.format(year=y))}" target="_blank" '
                                f'rel="noopener">Junta de Gobierno</a>',
                             f'<a href="{e(town.plenary_year_url.format(year=y))}" target="_blank" '
                             f'rel="noopener">Pleno</a>') for y in years)


def _downloads(path: str, years: list[int]) -> str:
    return "".join(_year_row(y, f'<a href="{e(rel(path, routes.money_csv(y)))}" download>dinero por entidad</a>',
                             f'<a href="{e(rel(path, routes.decisions_csv(y)))}" download>todas las decisiones</a>')
                   for y in years)


VIDEO, POSTER = "presentacion.mp4", "presentacion.jpg"


def tour(path: str, year: int) -> str:
    def link(target: str, label: str) -> str:
        return f'<a href="{e(rel(path, target))}">{label}</a>'

    video, poster = (f"{rel(path, 'static/' + f)}?v={version(f)}" for f in (VIDEO, POSTER))
    items = [(link(routes.home(year), "Dinero"), "a dónde va el dinero, empresa por empresa."),
             (link(routes.entities(), "Empresas y entidades"),
              "los contratos, pagos y subvenciones de cada empresa, asociación o institución."),
             (link(routes.decisions(year), "Decisiones"),
              "cada reunión de la Junta de Gobierno y del Pleno, contada en lenguaje llano y con el enlace al acta."),
             (link(routes.permits(year), "Permisos"), "quién pide licencias de obra y de actividad."),
             (link(routes.votes(legislature_of_year(year)), "Votaciones"), "cómo vota cada grupo en el Pleno."),
             (link(routes.search(), "Buscar"), "una calle, un tema, una empresa o un número de expediente.")]
    rows = "".join(f"<li>{a}: {text}</li>" for a, text in items)
    return f"""<h2 id="que-puedes-hacer">Qué puedes hacer en esta web</h2>
<div class="tour">
<figure class="tour-video">
<video controls preload="none" playsinline poster="{e(poster)}" width="1080" height="1920">
<source src="{e(video)}" type="video/mp4">
<a href="{e(video)}">Descargar el vídeo</a>
</video>
<figcaption>Un recorrido de 30 segundos.</figcaption>
</figure>
<ul class="tour-list">{rows}</ul>
</div>"""


def body(archive) -> str:
    path = INFO_PATH
    years = archive.years
    councillors = sum(LEGISLATURES[CURRENT].values())
    example = municipality.load().unpublished_example
    unpublished = f" (por ejemplo, {e(example)})" if example else ""
    return f"""<h1>{INFO_TITLE}</h1>
<p class="lede">Qué puedes hacer en esta web, de dónde salen sus datos, cómo se resumen y qué límites tienen.</p>
{tour(path, archive.latest.year)}
<h2>Qué es la Junta de Gobierno y qué es el Pleno</h2>
<p>La <b>Junta de Gobierno Local</b> está formada por el alcalde o la alcaldesa y algunos concejales y concejalas del equipo de gobierno. Se reúne casi cada semana y decide la gestión ordinaria: contratos, pagos de facturas, licencias de obra y de actividad, subvenciones y personal.</p>
<p>El <b>Pleno</b> reúne a los {councillors} concejales y concejalas de todos los grupos. Aprueba el presupuesto, las ordenanzas y los préstamos, y debate y vota las mociones de los grupos políticos.</p>
<h2>De dónde salen los datos</h2>
<p>De las actas oficiales de la Junta de Gobierno Local y del Pleno que publica el Ayuntamiento en su web, desde {years[-1]}:</p>
<ul class="year-links">
{_sources(years)}
</ul>
<p>Cada ficha enlaza al PDF oficial, en la página aproximada del asunto: casi siempre es la exacta y, si no, el asunto suele estar en la de al lado.</p>
<h2 id="proceso">Cómo se procesan</h2>
<p>Un modelo de lenguaje (inteligencia artificial) lee cada acta y resume cada asunto en lenguaje llano: qué se decide, cuánto dinero hay y quién aparece. Después, unas reglas automáticas unifican los nombres de las empresas, separan lo que se licita de lo que se adjudica o se paga, y evitan contar dos veces el mismo dinero.</p>
<p>Los nombres de personas no se publican: aparecen como «un particular». Tampoco se publican direcciones de viviendas de particulares.</p>
{code_paragraph()}
<h2>Limitaciones</h2>
<ul>
<li>Algunas actas no están publicadas en la web del Ayuntamiento{unpublished} o están incompletas: sus asuntos no aparecen.</li>
<li>Las actas se publican con uno o dos meses de retraso: las últimas reuniones todavía no están.</li>
<li>Algunas entidades están <a href="#pendiente-de-clasificar">pendientes de clasificar</a> y no cuentan en el total de empresas.</li>
<li>Parte del dinero está <a href="#sin-identificar">sin identificar</a>: el acta no dice quién lo recibe.</li>
<li>La cifra <a href="#comprometido">comprometido</a> no es lo que cada entidad ha cobrado.</li>
<li>Algunas cifras llevan un asterisco (*): es una situación especial, por ejemplo un contrato de varios años, y se explica al lado. En esos contratos marcados se cuenta un solo año; en los demás, lo que dice el acta.</li>
<li id="orden">Dentro de cada reunión, los asuntos no van en el orden del acta. Van primero los de más interés para el vecino, según una nota del 1 al 3 que pone la inteligencia artificial al analizar el acta (3: mucho dinero, deuda, polémica o votación dividida, suelo no urbanizable o empresas conocidas; 2: dinero o un permiso concreto que puede interesar a alguien del pueblo; 1: trámites de rutina). Con la misma nota, va primero el de más dinero (los ingresos, como taquillas o padrones, no cuentan) y luego el que sale antes en el acta. Es un criterio para leer más rápido, no una valoración. Si ves algún error, <a href="#errores">avísanos</a>.</li>
</ul>
{glossary()}
<h2 id="datos">Descargar los datos</h2>
<p>Los mismos datos de esta web, en ficheros CSV que se abren con una hoja de cálculo (Excel, LibreOffice, Google Sheets). Hay dos por año: el dinero por entidad (lo comprometido, adjudicado, pagado y en subvenciones de cada empresa, asociación o institución) y todas las decisiones (fecha, órgano, título, tema, resultado, importe, expediente y enlace al acta).</p>
<ul class="year-links">
{_downloads(path, years)}
</ul>
<p class="hint">Como en la web, sin nombres de personas ni direcciones. Si los usas, cita la fuente: las actas oficiales del Ayuntamiento de {TOWN}.</p>
<h2 id="errores">Avísanos de los errores</h2>
<p>Si ves un dato mal, escríbenos a <a href="{mailto()}">{EMAIL}</a> con el enlace de la ficha.</p>"""


def generate(archive) -> list[tuple[str, str]]:
    return [(INFO_PATH, page(INFO_PATH, INFO_TITLE, body(archive), archive.latest, "info"))]
