"""Cliente HTTP para MIeL: login, reintento al vencer la sesión y descargas."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote

import httpx

from . import parsers

BASE_URL = "https://miel.unlam.edu.ar"

# Valores del select "buscarTipo" de la página de contenidos.
TIPOS = {"todos": "0", "teoria": "T", "practicas": "P", "enlaces": "E"}


class MielError(Exception):
    pass


def normalizar(texto: str) -> str:
    """Minúsculas y sin acentos, para comparar nombres de materias."""
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def nombre_seguro(nombre: str) -> str:
    """Nombre válido como archivo/carpeta en Windows."""
    limpio = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", nombre).strip().rstrip(".")
    return limpio[:150] or "sin_nombre"


class MielClient:
    def __init__(self, usuario: str, clave: str, base_url: str = BASE_URL):
        if not usuario or not clave:
            raise MielError(
                "Faltan credenciales: definí MIEL_USUARIO y MIEL_CLAVE "
                "(en el .env o en la config del cliente MCP)."
            )
        self._usuario = usuario
        self._clave = clave
        self._base = base_url.rstrip("/")
        self._http = httpx.Client(
            base_url=self._base,
            follow_redirects=True,
            timeout=30,
            headers={"User-Agent": "miel-mcp/0.1 (+uso personal)"},
        )
        self._logueado = False

    # ---------------------------------------------------------------- sesión

    def login(self) -> None:
        self._http.get("/principal/home/")
        self._http.post(
            "/principal/event/login/",
            data={"usuario": self._usuario, "clave": self._clave, "recordar": "1"},
        )
        if not self._is_logged():
            raise MielError("No se pudo iniciar sesión en MIeL: revisá usuario y clave.")
        self._logueado = True

    def _is_logged(self) -> bool:
        r = self._http.get("/principal/event/isLogged/")
        return r.text.strip() == "1"

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        if not self._logueado:
            self.login()
        r = self._http.request(method, url, **kwargs)
        if self._sesion_vencida(r):
            self.login()
            r = self._http.request(method, url, **kwargs)
        r.raise_for_status()
        return r

    @staticmethod
    def _sesion_vencida(r: httpx.Response) -> bool:
        if "text/html" not in r.headers.get("content-type", ""):
            return False
        return parsers.es_pagina_login(r.text)

    def _html(self, method: str, url: str, **kwargs) -> str:
        return self._request(method, url, **kwargs).text

    # --------------------------------------------------------------- lectura

    def materias(self, incluir_ocultas: bool = False) -> list[parsers.Materia]:
        todas = parsers.parse_materias(self._html("GET", "/principal/interno/"))
        return [m for m in todas if incluir_ocultas or not m.oculta]

    def resolver_materia(self, materia: str) -> parsers.Materia:
        """Acepta el id de comisión o parte del nombre (sin importar acentos)."""
        todas = self.materias(incluir_ocultas=True)
        materia = materia.strip()
        for m in todas:
            if m.id == materia:
                return m
        buscado = normalizar(materia)
        coincidencias = [m for m in todas if buscado in normalizar(m.nombre)]
        if len(coincidencias) == 1:
            return coincidencias[0]
        nombres = ", ".join(f"{m.nombre} ({m.id})" for m in (coincidencias or todas))
        if coincidencias:
            raise MielError(f"'{materia}' es ambiguo. Coincide con: {nombres}")
        raise MielError(f"No encontré la materia '{materia}'. Disponibles: {nombres}")

    def archivos(
        self, comision: str, tipo: str = "todos", buscar: str = ""
    ) -> list[parsers.Archivo]:
        url = f"/contenido/archivos/comision/{comision}"
        if tipo == "todos" and not buscar:
            html = self._html("GET", url)
        else:
            if tipo not in TIPOS:
                raise MielError(f"Tipo inválido '{tipo}'. Opciones: {', '.join(TIPOS)}")
            html = self._html(
                "POST", url, data={"buscarTipo": TIPOS[tipo], "buscarPalabra": buscar}
            )
        return parsers.parse_archivos(html)

    def temas_foro(self, comision: str) -> list[parsers.TemaForo]:
        return parsers.parse_temas_foro(
            self._html("GET", f"/forov2/temas/comision/{comision}")
        )

    def mensajes_foro(self, comision: str, tema: str) -> list[parsers.MensajeForo]:
        return parsers.parse_mensajes_foro(
            self._html("GET", f"/forov2/mensajes/comision/{comision}/tema/{tema}")
        )

    # ------------------------------------------------------------- descargas

    def descargar(self, archivo: parsers.Archivo, destino: Path) -> Path:
        """Descarga un archivo a la carpeta `destino` y devuelve la ruta final."""
        if archivo.es_enlace:
            raise MielError(f"'{archivo.nombre}' es un enlace externo: {archivo.url}")
        r = self._request("GET", archivo.url)
        nombre = _nombre_desde_respuesta(r) or archivo.nombre_archivo or archivo.id
        destino.mkdir(parents=True, exist_ok=True)
        ruta = destino / nombre_seguro(nombre)
        ruta.write_bytes(r.content)
        return ruta

    def close(self) -> None:
        self._http.close()


def _nombre_desde_respuesta(r: httpx.Response) -> str:
    disp = r.headers.get("content-disposition", "")
    m = re.search(r"filename\*=UTF-8''([^;]+)", disp) or re.search(
        r'filename="?([^";]+)"?', disp
    )
    return unquote(m.group(1)) if m else ""
