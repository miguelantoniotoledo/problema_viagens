import json
import sys
from datetime import date
from pathlib import Path
from typing import List

import streamlit as st

# Ensure repo root is on sys.path when running via `streamlit run`
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.models import (  # noqa: E402
    TravelerProfile,
    Segment,
    SegmentType,
    SearchRequest,
)
from src.services.search_coordinator import run_search  # noqa: E402


st.set_page_config(page_title="Planejador de Viagens - Kayak", layout="wide")
st.title("Planejador de Viagens (Mock Kayak)")


def init_state():
    if "travelers" not in st.session_state:
        st.session_state.travelers: List[TravelerProfile] = [
            TravelerProfile(name="Viajante 1", age=30, category="adult")
        ]
    if "segments" not in st.session_state:
        st.session_state.segments: List[Segment] = []
    if "currency" not in st.session_state:
        st.session_state.currency = "USD"


init_state()


def add_traveler():
    with st.expander("Adicionar viajante"):
        name = st.text_input("Nome", key="trav_name")
        age = st.number_input("Idade", min_value=0, max_value=120, value=30, key="trav_age")
        category = st.selectbox("Categoria", ["adult", "child", "infant"], key="trav_category")
        couple_group_id = st.text_input("Grupo de casal (opcional)", key="trav_couple")
        bed_pref = st.selectbox(
            "Preferência de leito", ["any", "double", "queen", "king", "twin"], index=0, key="trav_bed"
        )
        if st.button("Salvar viajante"):
            st.session_state.travelers.append(
                TravelerProfile(
                    name=name or f"Viajante {len(st.session_state.travelers)+1}",
                    age=int(age),
                    category=category,
                    couple_group_id=couple_group_id or None,
                    bed_pref=bed_pref if bed_pref != "any" else None,
                )
            )
            st.success("Viajante adicionado.")


def render_travelers():
    st.subheader("Viajantes (pax global)")
    rows = [
        {
            "nome": t.name,
            "idade": t.age,
            "categoria": t.category,
            "casal": t.couple_group_id or "-",
            "leito": t.bed_pref or "-",
        }
        for t in st.session_state.travelers
    ]
    st.table(rows)
    add_traveler()


def add_segment():
    with st.expander("Adicionar trecho"):
        col1, col2, col3 = st.columns(3)
        origin = col1.text_input("Origem", key="seg_origin")
        destination = col2.text_input("Destino", key="seg_destination")
        transport_str = col3.selectbox("Meio de transporte", [t.value for t in SegmentType], key="seg_transport")
        d1 = col1.date_input("Data de saída", key="seg_departure", value=date.today())
        d2 = col2.date_input("Data de chegada", key="seg_arrival", value=date.today())
        keep_car = False
        if transport_str == SegmentType.CAR.value:
            keep_car = st.checkbox("Manter carro para próximos trechos contíguos?", key="seg_keep_car")
        if st.button("Salvar trecho"):
            st.session_state.segments.append(
                Segment(
                    origin=origin.strip().upper(),
                    destination=destination.strip().upper(),
                    departure=d1.isoformat(),
                    arrival=d2.isoformat(),
                    transport=SegmentType(transport_str),
                    keep_car_until_next=keep_car,
                )
            )
            st.success("Trecho adicionado.")


def render_segments():
    st.subheader("Trechos")
    if st.session_state.segments:
        rows = [
            {
                "id": seg.id[:8],
                "origem": seg.origin,
                "destino": seg.destination,
                "saida": seg.departure,
                "chegada": seg.arrival,
                "meio": seg.transport.value,
                "keep_car": seg.keep_car_until_next,
            }
            for seg in st.session_state.segments
        ]
        st.table(rows)
    add_segment()


@st.cache_data(ttl=300, show_spinner=False)
def cached_search(req_payload: dict):
    travelers = [
        TravelerProfile(
            name=t["name"],
            age=t["age"],
            category=t["category"],
            couple_group_id=t.get("couple_group_id"),
            bed_pref=t.get("bed_pref"),
            id=t.get("id"),
        )
        for t in req_payload["travelers"]
    ]
    segments = [
        Segment(
            origin=s["origin"],
            destination=s["destination"],
            departure=s["departure"],
            arrival=s.get("arrival"),
            transport=SegmentType(s["transport"]),
            keep_car_until_next=s.get("keep_car_until_next", False),
            id=s.get("id"),
        )
        for s in req_payload["segments"]
    ]
    req = SearchRequest(
        segments=segments,
        travelers=travelers,
        currency=req_payload["currency"],
        max_items=req_payload.get("max_items", 40),
    )
    result = run_search(req)
    return result.to_jsonable()


def build_request_payload():
    travelers = [
        {
            "name": t.name,
            "age": t.age,
            "category": t.category,
            "couple_group_id": t.couple_group_id,
            "bed_pref": t.bed_pref,
            "id": t.id,
        }
        for t in st.session_state.travelers
    ]
    segments = [
        {
            "origin": s.origin,
            "destination": s.destination,
            "departure": s.departure,
            "arrival": s.arrival,
            "transport": s.transport.value,
            "keep_car_until_next": s.keep_car_until_next,
            "id": s.id,
        }
        for s in st.session_state.segments
    ]
    currency = st.session_state.currency
    return {"segments": segments, "travelers": travelers, "currency": currency, "max_items": 40}


def render_currency_selector():
    st.session_state.currency = st.selectbox("Moeda alvo", ["USD", "BRL", "EUR"], index=0)


def render_search_and_results():
    st.subheader("Busca")
    render_currency_selector()
    if st.button("Buscar opções"):
        payload = build_request_payload()
        data = cached_search(payload)
        st.success("Busca finalizada (mock).")
        st.json(data)
        st.download_button(
            label="Baixar JSON",
            file_name="resultados_viagem.json",
            mime="application/json",
            data=json.dumps(data, ensure_ascii=False, indent=2),
        )


render_travelers()
render_segments()
render_search_and_results()
