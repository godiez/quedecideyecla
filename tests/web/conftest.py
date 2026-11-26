import json

import pytest

from actas import catalog


def _p(ref, title, category, interest=1, **kw):
    return {"ref": ref, "titulo": title, "categoria": category, "resumen": kw.pop("resumen", f"Resumen de {title}."),
            "entidades": kw.pop("entidades", []), "hay_particulares": kw.pop("hay_particulares", False),
            "importe_eur": kw.pop("importe_eur", None), "importes": kw.pop("importes", []),
            "resultado": kw.pop("resultado", "aprobado"), "expediente": kw.pop("expediente", None),
            "lugar": kw.pop("lugar", None), "interes": interest, **kw}


MINUTES = {
    "2026-01-07_JGL_01": ("JGL", 1, "ordinaria", [
        _p("1", "Pago de facturas de recogida de basura", "pago_factura", 2, importe_eur=50000,
           expediente="1186986R",
           entidades=[{"nombre": "Actúa, Servicios y Medio Ambiente, S.L.", "tipo": "empresa", "rol": "cobra"}]),
        _p("2", "Subvención a la protectora de animales", "subvencion_concedida", 2, importe_eur=4500,
           expediente="1200001A",
           entidades=[{"nombre": "Sociedad Protectora de Animales de Yecla (SPANDY)", "tipo": "asociacion",
                       "rol": "beneficiario"}]),
        _p("3", "Licencia de obra para una nave", "licencia_obra", 1, expediente="1200002B",
           entidades=[{"nombre": "Construcciones Gómez, S.L.", "tipo": "empresa", "rol": "solicita"}]),
        _p("4", "Vivienda en suelo no urbanizable", "suelo_no_urbanizable", 3, hay_particulares=True,
           lugar="C/ Mayor 12", expediente="1200003C",
           entidades=[{"nombre": "particular", "tipo": "particular", "rol": "solicita"}]),
        _p("5", "Comisión de servicios de un policía", "personal", 1, expediente="1200004D"),
    ]),
    "2026-02-03_JGL_07": ("JGL", 7, "extraordinaria y urgente", [
        _p("1", "Reparación de vehículos municipales", "contrato", 2, importe_eur=12000,
           entidades=[{"nombre": "Talleres Pérez C.B.", "rol": "adjudicatario"}]),
        _p("2", "Visita guiada al castillo", "servicios_actividades", 1),
        _p("3", "Aportación al consorcio de vías verdes", "subvencion_concedida", 1, importe_eur=3000,
           importes=[{"entidad": "Consorcio de las Vías Verdes de la Región de Murcia", "concepto": "aportación",
                      "eur": 3000}],
           entidades=[{"nombre": "Consorcio de las Vías Verdes de la Región de Murcia",
                       "tipo": "administracion", "rol": "beneficiario"}]),
    ]),
    "2026-03-02_PLENO_03": ("PLENO", 3, "ordinaria", [
        _p("1", "Préstamo de 349.077 euros para la obra del edificio Cazadores", "presupuesto_hacienda", 3,
           importe_eur=349077, expediente="1362210J"),
        _p("2", "Moción equivocada", "mocion_politica", 2),
        _p("3", "Aprobación del acta anterior", "organizacion", 1),
    ]),
}

VOTES = {"PP": {"favor": 9, "contra": 0, "abstencion": 0}, "PSOE": {"favor": 0, "contra": 0, "abstencion": 7},
         "Vox": {"favor": 0, "contra": 3, "abstencion": 0}, "IU-Verdes": {"favor": 0, "contra": 0, "abstencion": 2}}


@pytest.fixture
def mini_analysis(tmp_path):
    a = tmp_path / "analisis" / "2026"
    (a / "json").mkdir(parents=True)
    (a / "txt").mkdir()
    (a / "votos").mkdir()
    for doc, (body, number, kind, points) in MINUTES.items():
        d = {"doc": doc, "organo": body, "sesion": number, "fecha": doc[:10], "tipo_sesion": kind,
             "puntos": points}
        (a / "json" / f"{doc}.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        pages = ["Portada del acta"] + [f"{p['ref']}º.- {p['titulo'].upper()} (Expte. {p['expediente']})"
                                        for p in points]
        (a / "txt" / f"{doc}.txt").write_text("\f".join(pages), encoding="utf-8")
    (a / "votos" / "2026-03-02_PLENO_03.json").write_text(json.dumps({
        "doc": "2026-03-02_PLENO_03", "asistentes": {"PP": 9, "PSOE": 7, "Vox": 3, "IU-Verdes": 2},
        "votaciones": [
            {"punto_idx": 0, "punto_ref": "1", "que": "propuesta", "final": True, "unanimidad": False,
             "votos": VOTES, "resultado": "aprobada"},
            {"punto_idx": 1, "punto_ref": "2", "que": "moción", "final": True, "unanimidad": False,
             "votos": VOTES, "resultado": "aprobada"},
        ]}), encoding="utf-8")
    (a / "revision.json").write_text(json.dumps({
        "2026-03-02_PLENO_03:1": {"estado": "descartado", "cambios": {}, "nota": "", "original": {}},
        "2026-03-02_PLENO_03:2": {"estado": "aprobado", "cambios": {}, "nota": "", "original": {}},
    }), encoding="utf-8")
    (a / "alias.json").write_text("{}", encoding="utf-8")
    db = tmp_path / "actas.sqlite"
    conn = catalog.connect(db)
    for doc, kind, url in [("2026-01-07_JGL_01", "jgl_minutes", "https://yecla.es/actas/ACTA01.pdf"),
                           ("2026-03-02_PLENO_03", "plenary_minutes", "https://yecla.es/actas/PLENO03.pdf")]:
        catalog.upsert(conn, kind, url, doc[:10], int(doc[-2:]), doc, "https://yecla.es/")
        conn.execute("UPDATE minutes SET local_path = ? WHERE url = ?", (f"data/pdfs/x/{doc}.pdf", url))
    conn.commit()
    conn.close()
    return a, db


@pytest.fixture
def archive(mini_analysis):
    from actas.web import model
    a, db = mini_analysis
    return model.build_archive(a.parent, db)


@pytest.fixture
def two_years(mini_analysis):
    a, db = mini_analysis
    b = a.parent / "2022"
    for sub in ("json", "txt", "votos"):
        (b / sub).mkdir(parents=True)
    points = [_p("1", "Pago de la basura de 2022", "pago_factura", 2, importe_eur=30000,
                 entidades=[{"nombre": "Actúa, Servicios y Medio Ambiente, S.L.", "tipo": "empresa", "rol": "cobra"}]),
              _p("2", "Moción sobre el agua", "mocion_politica", 2)]
    for doc, body, pts in [("2022-05-10_JGL_19", "JGL", points[:1]), ("2022-05-30_PLENO_05", "PLENO", points[1:])]:
        d = {"doc": doc, "organo": body, "sesion": int(doc[-2:]), "fecha": doc[:10], "tipo_sesion": "ordinaria",
             "puntos": pts}
        (b / "json" / f"{doc}.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        (b / "txt" / f"{doc}.txt").write_text("Portada\f" + pts[0]["titulo"].upper(), encoding="utf-8")
    old = {"PP": {"favor": 12}, "PSOE": {"contra": 5}, "Cs": {"favor": 2}, "IU-Verdes": {"contra": 2}}
    (b / "votos" / "2022-05-30_PLENO_05.json").write_text(json.dumps({
        "doc": "2022-05-30_PLENO_05", "votaciones": [
            {"punto_idx": 0, "punto_ref": "2", "que": "moción", "final": True, "unanimidad": False,
             "votos": old, "resultado": "aprobada"}]}), encoding="utf-8")
    (b / "alias.json").write_text("{}", encoding="utf-8")
    return a.parent, db
