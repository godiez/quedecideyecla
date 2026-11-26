from actas import municipality
from actas.web.fmt import e, rel
from actas.web.template import code_link, mailto, page
from actas.web.texts import EMAIL, INFO_PATH, INFO_TITLE, LEGAL_PATH, LEGAL_TITLE, TOWN, UNOFFICIAL

UPDATED = "23 de noviembre de 2026"
GITHUB_PRIVACY = "https://docs.github.com/es/site-policy/privacy-policies/github-general-privacy-statement"
CC_BY = "https://creativecommons.org/licenses/by/4.0/deed.es"
RESPONSIBLE = municipality.load().responsible


def body() -> str:
    info = rel(LEGAL_PATH, INFO_PATH)
    return f"""<h1>{LEGAL_TITLE}</h1>
<p class="lede">Para qué es esta web, quién la hace, de dónde sale lo que cuenta y qué hacer si algo está mal.</p>
<h2>Para qué es esta web</h2>
<p>Es una iniciativa personal y sin ánimo de lucro. Su único fin es que cualquier vecino pueda saber, de forma sencilla, qué decide el Ayuntamiento de {TOWN}: qué contrata, qué paga, qué subvenciones da y qué se vota en el Pleno.</p>
<p>No está hecha contra nadie: ni contra el Ayuntamiento, ni contra ningún partido político, empresa, asociación o persona.</p>
<h2>Responsable</h2>
<p>{RESPONSIBLE}, a título personal. Contacto: <a href="{mailto()}">{EMAIL}</a>.</p>
<h2>Neutralidad</h2>
<ul>
<li>Cuenta lo que dicen las actas, sin opinar ni valorar. Trata igual a todos los grupos municipales.</li>
<li>Que una empresa o asociación aparezca aquí no significa que haya hecho nada irregular: aparece porque un acta la nombra en una decisión del Ayuntamiento.</li>
<li>No tiene publicidad ni recibe dinero de nadie. {UNOFFICIAL}</li>
</ul>
<h2>De dónde sale la información</h2>
<p>De las actas que el propio Ayuntamiento publica en <a href="{e(municipality.load().council_url)}" target="_blank" rel="noopener">{e(municipality.load().council_domain)}</a>. Los acuerdos y deliberaciones de los organismos públicos no están protegidos por la propiedad intelectual (artículo 13 de la Ley de Propiedad Intelectual), y conocerlos es un derecho de todos (Ley 19/2013, de transparencia).</p>
<p>Esta web no reproduce las actas: resume cada asunto con palabras propias y enlaza al PDF oficial, que es el único documento válido. No usa el escudo, el logotipo ni el diseño del Ayuntamiento.</p>
<h2>Errores y correcciones</h2>
<p>Los resúmenes se hacen de forma automática (<a href="{info}#proceso">{INFO_TITLE.lower()}</a>) y pueden tener errores. Ante cualquier duda, vale lo que dice el acta oficial.</p>
<p>Si ves un error, o si eres una empresa, asociación o persona que aparece y quieres que se corrija algo, escríbenos a <a href="{e(mailto("Corrección"))}">{EMAIL}</a> con el enlace de la ficha. Lo revisaremos y, si hay un error, lo corregiremos lo antes posible.</p>
<h2>Datos personales</h2>
<ul>
<li>No se publican nombres ni direcciones de viviendas de particulares: aparecen como «un particular». Si encuentras un dato tuyo, escríbenos y lo quitaremos.</li>
<li>Esta web no usa cookies ni herramientas de estadística, y no carga nada de otras webs. Solo recuerda en tu navegador, mientras dura la visita, que has cerrado el aviso de arriba.</li>
<li>Está alojada en GitHub Pages, que puede registrar la dirección IP de las visitas por seguridad, según su <a href="{GITHUB_PRIVACY}" target="_blank" rel="noopener">política de privacidad</a>.</li>
<li>Si nos escribes, tu correo solo se usa para contestarte.</li>
</ul>
<h2>Uso de los datos</h2>
<p>Puedes usar los textos y los <a href="{info}#datos">datos descargables</a> citando la fuente: las actas oficiales del Ayuntamiento de {TOWN} y esta web (licencia <a href="{CC_BY}" target="_blank" rel="noopener">Creative Commons Reconocimiento 4.0</a>). {code_link("El código de la web")} es libre, con licencia MIT. Esta web no se hace responsable del uso que otros hagan de esta información. Para cualquier trámite, consulta el acta oficial o al Ayuntamiento.</p>
<p class="hint">Se aplica la ley española. Última actualización: {UPDATED}.</p>"""


def generate(archive) -> list[tuple[str, str]]:
    return [(LEGAL_PATH, page(LEGAL_PATH, LEGAL_TITLE, body(), archive.latest, None))]
