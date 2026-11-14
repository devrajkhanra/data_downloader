from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias


class IndexCategory(str, Enum):
    BROAD = "broad_indices"
    SECTORAL = "sectoral_indices"


Candle: TypeAlias = list[str | int | float | None]


@dataclass(frozen=True)
class IndexInstrument:
    name: str
    instrument_key: str
    category: IndexCategory
    slug: str
