from pathlib import Path

from miel_mcp import parsers
from miel_mcp.client import nombre_seguro, normalizar

FIXTURES = Path(__file__).parent / "fixtures"


def leer(nombre: str) -> str:
    return (FIXTURES / nombre).read_text(encoding="utf-8")


def test_materias():
    materias = parsers.parse_materias(leer("interno.html"))
    assert [m.id for m in materias] == ["900001", "900002", "900003"]
    tuto, ia, ingles = materias
    assert tuto.oculta and not ia.oculta
    assert ia.nombre == "Inteligencia Artificial"
    assert ia.detalle == "3664 - Com: 01-3900 - Alumno/a"
    assert ingles.foro_sin_leer == 8
    assert "Evaluación" in ingles.herramientas


def test_archivos():
    archivos = parsers.parse_archivos(leer("contenidos.html"))
    assert [a.id for a in archivos] == ["100001", "100002", "100003", "100004"]

    programa = archivos[0]
    assert programa.nombre == "Programa"
    assert programa.carpeta == "Presentación de la Materia"
    assert programa.seccion == "Programa"
    assert programa.fecha == "17/08/2026"
    assert programa.tamanio == "418 KB"
    assert programa.nombre_archivo == "Programa-2026.pdf"
    assert not programa.es_enlace

    podcast = archivos[2]
    assert podcast.es_enlace
    assert podcast.carpeta == "Contenidos"
    assert podcast.seccion == "Unidad 1"
    assert podcast.descripcion == "Podcast sobre innovación."
    assert podcast.url.startswith("https://soundcloud.com/")

    assert archivos[3].tipo_lectura == "Complementaria"


def test_archivos_vacio():
    assert parsers.parse_archivos("<main><p>No se encontraron archivos en este curso.</p></main>") == []


def test_temas_foro():
    general, tp = parsers.parse_temas_foro(leer("temas.html"))
    assert general.id == "500001"
    assert general.titulo == "General"
    assert general.mensajes == 8
    assert general.ultimo_mensaje == "16/10/2026 11:18:44"
    assert general.sin_leer == 6
    assert general.estado == "Tema abierto"
    assert tp.mensajes == 1 and tp.sin_leer == 0 and tp.estado == "Tema cerrado"


def test_mensajes_foro():
    primero, respuesta = parsers.parse_mensajes_foro(leer("tema.html"))
    assert primero.id == "700001" and primero.respuesta_a is None
    assert primero.autor == "DOCENTE, EJEMPLO"
    assert primero.rol == "Docente (com 25-6200)"
    assert primero.fecha == "13/08/2026 21:57:22"
    assert "Bienvenidos a la materia." in primero.texto
    assert primero.enlaces == ["https://ejemplo.com/material"]
    assert respuesta.respuesta_a == "700001"


def test_pagina_login():
    html = '<form action="https://miel.unlam.edu.ar/principal/event/login/" method="post"></form>'
    assert parsers.es_pagina_login(html)
    assert not parsers.es_pagina_login(leer("interno.html"))


def test_utilidades():
    assert normalizar("Inglés III") == "ingles iii"
    assert nombre_seguro('a:b/c?.') == "a_b_c_"
