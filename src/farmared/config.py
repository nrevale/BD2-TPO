"""Configuración leída de variables de entorno.

Los defaults sirven para correr Python desde el host contra el `docker compose`
(puertos publicados en localhost). Dentro del contenedor `app` las variables
las fija `docker-compose.yml` con los nombres de servicio (`mongo`, `neo4j`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    mongo_uri: str
    mongo_db: str
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str


def cargar_config() -> Config:
    return Config(
        # directConnection: desde el host el miembro del replica set se llama "mongo",
        # que no resuelve fuera de la red de Docker.
        mongo_uri=os.environ.get("MONGO_URI", "mongodb://localhost:27017/?directConnection=true"),
        mongo_db=os.environ.get("MONGO_DB", "farmared"),
        neo4j_uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.environ.get("NEO4J_USER", "neo4j"),
        neo4j_password=os.environ.get("NEO4J_PASSWORD", "farmared123"),
    )
