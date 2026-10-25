"""Parsers del HTML de MIeL. Funciones puras: reciben HTML y devuelven datos."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from bs4 import BeautifulSoup, Tag


def _text(el: Tag | None) -> str:
    if el is None:
        return ""
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()


def _own_text(el: Tag) -> str:
    """Texto directo del elemento, sin el de sus hijos (iconos, descripciones ocultas)."""
    parts = [s for s in el.find_all(string=True, recursive=False)]
    return re.sub(r"\s+", " ", " ".join(parts)).replace("\xa0", " ").strip()


@dataclass
class Materia:
    id: str
    nombre: str
    detalle: str
    oculta: bool
    herramientas: list[str] = field(default_factory=list)
    foro_sin_leer: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Archivo:
    id: str
    nombre: str
    carpeta: str
    seccion: str
    descripcion: str
    tipo_lectura: str
    fecha: str
    tamanio: str
    es_enlace: bool
    url: str
    nombre_archivo: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TemaForo:
    id: str
    titulo: str
    descripcion: str
    mensajes: int
    ultimo_mensaje: str
    sin_leer: int
    estado: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MensajeForo:
    id: str
    respuesta_a: str | None
    autor: str
    rol: str
    fecha: str
    texto: str
    enlaces: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def es_pagina_login(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    return soup.select_one('form[action*="/principal/event/login/"]') is not None


def parse_materias(html: str) -> list[Materia]:
    soup = BeautifulSoup(html, "html.parser")
    materias = []
    for bloque in soup.select(".materia-bloque[data-id]"):
        desc = bloque.select_one(".materia-descripcion")
        detalle_el = desc.select_one(".materia-titulo + div") if desc else None
        herramientas = []
        sin_leer = 0
        for a in bloque.select(".materia-herramientas a"):
            nombre = _text(a.select_one("div"))
            if nombre:
                herramientas.append(nombre)
            badge = a.select_one(".w3-badge")
            if nombre == "Foro" and badge and _text(badge).isdigit():
                sin_leer = int(_text(badge))
        materias.append(
            Materia(
                id=bloque["data-id"],
                nombre=_text(bloque.select_one(".materia-titulo")),
                detalle=_text(detalle_el),
                oculta="materia-bloque-oculta" in bloque.get("class", []),
                herramientas=herramientas,
                foro_sin_leer=sin_leer,
            )
        )
    return materias


_ID_RE = re.compile(r"/id/(\d+)")


def parse_archivos(html: str) -> list[Archivo]:
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one("main") or soup
    archivos = []
    for table in root.select("table"):
        contenido = table.find_parent(class_="w3-accordion-content")
        carpeta = ""
        if contenido is not None:
            boton = contenido.find_previous_sibling(class_="desplegarModulo")
            carpeta = _text(boton.select_one("span")) if boton else ""

        seccion = ""
        for parte in table.find_all(["thead", "tbody"], recursive=False):
            if parte.name == "thead":
                th = parte.select_one("th")
                seccion = _own_text(th) if th else ""
                continue
            for tr in parte.find_all("tr", recursive=False):
                tds = tr.find_all("td", recursive=False)
                link = tr.select_one("a.btnDescargar") or tr.select_one("a[href]")
                if len(tds) < 6 or link is None:
                    continue
                href = link.get("href", "")
                es_enlace = "descargarElemento" not in href
                m = _ID_RE.search(href)
                archivo_id = m.group(1) if m else link.get("data-id-archivo", "")
                titulo = link.get("title", "")
                nombre_archivo = (
                    titulo.removeprefix("Descargar ").strip() if not es_enlace else ""
                )
                archivos.append(
                    Archivo(
                        id=archivo_id,
                        nombre=_own_text(tds[1]),
                        carpeta=carpeta,
                        seccion=seccion,
                        descripcion=_text(tds[1].select_one("div")),
                        tipo_lectura=_text(tds[2]),
                        fecha=_text(tds[3]),
                        tamanio=_text(tds[4]),
                        es_enlace=es_enlace,
                        url=href,
                        nombre_archivo=nombre_archivo,
                    )
                )
    return archivos


_TEMA_RE = re.compile(r"/tema/(\d+)")
_CANT_RE = re.compile(r"(\d+)\s+mensajes?")
_ULTIMO_RE = re.compile(r"Último mensaje\s+([\d/]+\s+[\d:]+)")


def parse_temas_foro(html: str) -> list[TemaForo]:
    soup = BeautifulSoup(html, "html.parser")
    temas = []
    for tema in soup.select(".foro-tema"):
        a = tema.select_one("a[href*='/tema/']")
        if a is None:
            continue
        m = _TEMA_RE.search(a["href"])
        info = _text(tema.select_one(".w3-text-grey"))
        cant = _CANT_RE.search(info)
        ultimo = _ULTIMO_RE.search(info)
        badge = tema.select_one(".badge-icono")
        icono = tema.select_one(".foro-icono")
        temas.append(
            TemaForo(
                id=m.group(1) if m else "",
                titulo=_text(tema.select_one("strong")),
                descripcion=_text(tema.select_one(".w3-padding-4")),
                mensajes=int(cant.group(1)) if cant else 0,
                ultimo_mensaje=ultimo.group(1) if ultimo else "",
                sin_leer=int(_text(badge)) if badge and _text(badge).isdigit() else 0,
                estado=icono.get("title", "") if icono else "",
            )
        )
    return temas


def parse_mensajes_foro(html: str) -> list[MensajeForo]:
    soup = BeautifulSoup(html, "html.parser")
    mensajes = []
    for li in soup.select("li.foro-mensaje"):
        mid = li.get("id", "").removeprefix("idMensaje-")
        padre = li.get("data-idmensajepadre")
        info = li.select_one("div[style*='width:250px']")
        grises = [_text(d) for d in info.select(".w3-text-gray")] if info else []
        fecha = next((g for g in grises if g.startswith("Enviado el")), "")
        rol = next((g for g in grises if not g.startswith("Enviado el")), "")
        contenido = li.select_one(".foro-contenido-mensaje")
        texto = contenido.get_text("\n", strip=True) if contenido else ""
        enlaces = [a["href"] for a in contenido.select("a[href]")] if contenido else []
        mensajes.append(
            MensajeForo(
                id=mid,
                respuesta_a=padre if padre and padre != mid else None,
                autor=_text(info.select_one("strong")) if info else "",
                rol=rol,
                fecha=fecha.removeprefix("Enviado el").strip(),
                texto=texto,
                enlaces=enlaces,
            )
        )
    return mensajes
