"""
Bendros vertinimo duomenų struktūros: žurnalo įvykis, atakos intervalas ir rinkinys.

Vienas `Event` atitinka vieną žurnalo eilutę. Adapteriai (AIT, OTRF, EVTX) verčia
žaliuosius duomenis į `Event` sąrašą; `is_attack` ateina iš rinkinio žymių.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field


@dataclass
class Event:
    ts: datetime.datetime
    host: str
    message: str
    program: str = "unknown"
    pid: str = ""
    facility: str = "user"
    severity: str = "info"
    job: str = "syslog"          # pagrindinis kolektoriaus srautas (all.log)
    is_attack: bool = False
    attack_labels: list[str] = field(default_factory=list)
    # Papildomos Loki srauto etiketės (pvz. Windows: channel). Jei netuščia,
    # įkėlimas `message` siunčia kaip žalią eilutę (ne syslog šabloną).
    extra_labels: dict = field(default_factory=dict)


@dataclass
class AttackInterval:
    """Vienos atakos fazės laiko intervalas (iš atakų tvarkaraščio arba žymių)."""
    name: str
    start: datetime.datetime
    end: datetime.datetime
    techniques: list[str] = field(default_factory=list)


@dataclass
class Dataset:
    name: str
    events: list[Event]
    attacks: list[AttackInterval]
    start: datetime.datetime
    end: datetime.datetime

    def sorted_events(self) -> list[Event]:
        return sorted(self.events, key=lambda e: e.ts)
