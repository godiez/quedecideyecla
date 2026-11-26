from actas import municipality

TOWN = municipality.load().name
SITE_NAME = municipality.load().site_name
HOME_TITLE = f"¿A dónde va el dinero de {TOWN}?"
EMAIL = municipality.load().email
UNOFFICIAL = f"Esta web no tiene relación con el Ayuntamiento de {TOWN} ni con ningún partido político."
NOTICE = (f"{UNOFFICIAL} Construida a partir de las actas del Ayuntamiento. Puede contener errores. ¿Ves uno? "
          f"Escríbenos a {EMAIL}")
META_DESCRIPTION = f"Qué decide el Ayuntamiento de {TOWN}, explicado a partir de sus actas. {UNOFFICIAL}"
PREVIEW_ALT = f"{SITE_NAME} · {TOWN}. Web no oficial, construida a partir de las actas del Ayuntamiento."
SOURCE = f"Fuente: actas oficiales publicadas en {municipality.load().council_domain}."
INFO_TITLE = "Cómo se ha hecho"
INFO_PATH = "como-se-ha-hecho/"
LEGAL_TITLE = "Aviso legal"
LEGAL_PATH = "aviso-legal/"
MENU = [("money", "Dinero"), ("decisions", "Decisiones"), ("permits", "Permisos"), ("votes", "Votaciones"),
        ("search", "Buscar")]


def section_title(key: str, period) -> str:
    return f"{dict(MENU)[key]} de {period}"

SEARCH_TITLE = "Buscar"
SEARCH_LABEL = "Busca una empresa o asociación, un lugar, un tema o un nº de expediente"
HOME_SEARCH_HINT = "Busca en todas las actas"
