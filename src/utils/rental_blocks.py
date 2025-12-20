from datetime import datetime
from typing import List

from src.models import Segment, SegmentType, RentalBlock

DATE_FMT = "%Y-%m-%d"


def parse_iso_date(value: str) -> datetime:
    # Fallback: attempt to parse date only; if it fails, use today to avoid crash.
    try:
        return datetime.strptime(value, DATE_FMT)
    except Exception:
        return datetime.today()


def build_rental_blocks(segments: List[Segment], traveler_ids: List[str]) -> List[RentalBlock]:
    blocks: List[RentalBlock] = []
    current: List[Segment] = []

    def flush():
        nonlocal current
        if not current:
            return
        first, last = current[0], current[-1]
        pickup_date = first.departure
        dropoff_date = last.arrival or last.departure
        block = RentalBlock(
            pickup_location=first.origin,
            dropoff_location=last.destination,
            pickup_date=pickup_date,
            dropoff_date=dropoff_date,
            traveler_ids=traveler_ids,
            linked_segments=[s.id for s in current],
        )
        blocks.append(block)
        current = []

    for seg in segments:
        if seg.transport != SegmentType.CAR:
            flush()
            continue
        if not current:
            current.append(seg)
        else:
            current.append(seg)
        if not seg.keep_car_until_next:
            flush()

    flush()
    return blocks
