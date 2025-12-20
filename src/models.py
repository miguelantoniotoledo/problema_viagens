from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional, Dict, Any
import uuid


class SegmentType(str, Enum):
    FLIGHT = "flight"
    CAR = "car"
    BUS = "bus"
    TRAIN = "train"


def make_id() -> str:
    return str(uuid.uuid4())


@dataclass
class TravelerProfile:
    name: str
    age: int
    category: str  # adult/child/infant
    couple_group_id: Optional[str] = None
    bed_pref: Optional[str] = None  # double/queen/king/twin/any
    id: str = field(default_factory=make_id)


@dataclass
class Segment:
    origin: str
    destination: str
    departure: str
    arrival: Optional[str]
    transport: SegmentType
    keep_car_until_next: bool = False
    id: str = field(default_factory=make_id)


@dataclass
class RentalBlock:
    pickup_location: str
    dropoff_location: str
    pickup_date: str
    dropoff_date: str
    traveler_ids: List[str]
    linked_segments: List[str]


@dataclass
class SearchRequest:
    segments: List[Segment]
    travelers: List[TravelerProfile]
    currency: str
    cache_ttl_seconds: int = 300
    max_items: int = 40


@dataclass
class PaginatedResult:
    items: List[Dict[str, Any]]
    total: int


@dataclass
class SearchResponse:
    flights: PaginatedResult
    hotels: PaginatedResult
    cars: PaginatedResult
    meta: Dict[str, Any]

    def to_jsonable(self) -> Dict[str, Any]:
        return {
            "flights": asdict(self.flights),
            "hotels": asdict(self.hotels),
            "cars": asdict(self.cars),
            "meta": self.meta,
        }
