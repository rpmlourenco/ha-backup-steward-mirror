"""Receiver policy. Machine details never appear as program constants."""

import copy
import re
import uuid
from pathlib import Path, PurePosixPath

from .keys import public_key

DEFAULTS = {
    "enabled": False,
    "label": "Lisboa",
    "mount": "/media/mirror",
    "uuid": "",
    "port": 2222,
    "min_free_gib": 20,
    "sources": [],
}


def validate(raw):
    if not isinstance(raw, dict) or set(raw) - set(DEFAULTS):
        raise ValueError("Configuração desconhecida.")
    cfg = dict(copy.deepcopy(DEFAULTS), **copy.deepcopy(raw))
    if type(cfg["enabled"]) is not bool:
        raise ValueError("Ativar receção deve ser um interruptor.")
    if not isinstance(cfg["label"], str) or not 1 <= len(cfg["label"]) <= 60:
        raise ValueError("Indica um nome para este destino.")
    path = PurePosixPath(cfg["mount"])
    if (
        len(path.parts) != 3
        or path.parent != PurePosixPath("/media")
        or not re.fullmatch(r"[A-Za-z0-9_-]+", path.name)
        or str(path) != cfg["mount"]
    ):
        raise ValueError("Escolhe um ponto de montagem diretamente em /media.")
    if cfg["uuid"]:
        try:
            uuid.UUID(cfg["uuid"])
        except (ValueError, TypeError, AttributeError):
            raise ValueError("O UUID do destino não é válido.") from None
    for key, lo, hi in (("port", 1, 65535), ("min_free_gib", 1, 100000)):
        if type(cfg[key]) is not int or not lo <= cfg[key] <= hi:
            raise ValueError(f"{key}: escolhe um valor entre {lo} e {hi}.")
    if not isinstance(cfg["sources"], list) or len(cfg["sources"]) > 20:
        raise ValueError("Configura até 20 origens.")
    names = set()
    for item in cfg["sources"]:
        if not isinstance(item, dict) or set(item) != {"name", "public_key"}:
            raise ValueError("Cada origem precisa de nome e chave pública.")
        if (
            not re.fullmatch(r"[a-z][a-z0-9_]{0,23}", item["name"])
            or item["name"] in names
        ):
            raise ValueError("Usa nomes únicos em minúsculas, até 24 caracteres.")
        names.add(item["name"])
        item["public_key"] = public_key(item["public_key"])
    if cfg["enabled"] and (not cfg["uuid"] or not cfg["sources"]):
        raise ValueError(
            "Confirma o UUID e importa as chaves antes de ativar a receção."
        )
    return cfg


def confined_root(cfg, name):
    root = Path(cfg["mount"])
    if root.is_symlink() or not root.is_dir() or root.resolve() != root:
        raise ValueError("O destino não está disponível ou contém links no caminho.")
    child = root / name
    if child.is_symlink() or (child.exists() and child.resolve() != child):
        raise ValueError("A pasta de receção não pode ser um link.")
    return child
