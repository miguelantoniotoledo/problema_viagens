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

from src import config
from src.models import TravelerProfile, Stop, SearchRequest  # noqa: E402
from src.services.search_coordinator import run_search  # noqa: E402
from src.utils.autocomplete import search_locations  # noqa: E402

st.set_page_config(page_title="Planejador de Viagens - Kayak", layout="wide")
st.title("Planejador de Viagens (BR-EUA)")


def render_location_picker(container, label: str, key: str, current: str) -> str:
    """Selectbox único com busca interna (dataset local BR/EUA)."""
    options = search_locations("", limit=5000)
    if not options:
        return current.strip().upper()
    display = [f"{o['code']} - {o['city']}/{o['state']} ({o['country']})" for o in options]
    default_index = 0
    if current:
        for i, opt in enumerate(options):
            if opt["code"] == current:
                default_index = i
                break
    choice = container.selectbox(label, display, index=default_index, key=f"{key}_select")
    idx = display.index(choice)
    return options[idx]["code"]


def init_state():
    """Inicializa chaves do estado da sessão com valores padrão."""
    st.session_state.setdefault("travelers", [])
    st.session_state.setdefault("stops", [])
    st.session_state.setdefault("currency", "USD")
    st.session_state.setdefault("trip_start_location", "")
    st.session_state.setdefault("trip_end_location", "")
    st.session_state.setdefault("trip_start_date", date.today())
    st.session_state.setdefault("trip_end_date", date.today())


init_state()


def render_trip_constraints():
    st.subheader("Parâmetros da viagem (início/fim)")
    col1, col2 = st.columns(2)
    st.session_state.trip_start_location = render_location_picker(col1, "Local de início da viagem", "trip_start_loc", st.session_state.trip_start_location)
    col2.date_input("Data de início", key="trip_start_date")
    col3, col4 = st.columns(2)
    st.session_state.trip_end_location = render_location_picker(col3, "Local de término da viagem", "trip_end_loc", st.session_state.trip_end_location)
    col4.date_input("Data máxima para término da viagem", key="trip_end_date")


def render_travelers():
    st.subheader("Viajantes")
    with st.expander("Adicionar viajante"):
        with st.form("trav_add_form", clear_on_submit=True):
            name = st.text_input("Nome", key="trav_add_name")
            age = st.number_input("Idade", min_value=0, max_value=120, value=30, key="trav_add_age")
            category = st.selectbox("Categoria", ["adult", "child", "infant"], key="trav_add_category")
            bed_pref = st.selectbox("Preferência de leito", ["any", "double", "queen", "king", "twin"], index=0, key="trav_add_bed")
            submitted = st.form_submit_button("Salvar viajante", use_container_width=True)
            if submitted:
                st.session_state.travelers.append(
                    TravelerProfile(
                        name=name or f"Viajante {len(st.session_state.travelers)+1}",
                        age=int(age),
                        category=category,
                        bed_pref=bed_pref if bed_pref != "any" else None,
                    )
                )
                st.success("Viajante adicionado.")
                st.rerun()

    if st.session_state.travelers:
        rows = [
            {
                "nome": t.name,
                "idade": t.age,
                "categoria": t.category,
                "par": next((p.name for p in st.session_state.travelers if p.id == t.partner_id), "-"),
                "leito": t.bed_pref or "-",
            }
            for t in st.session_state.travelers
        ]
        st.table(rows)

    if st.session_state.travelers:
        st.write("Editar/Remover viajante")
        options = {f"{t.name} ({t.id[:6]})": t for t in st.session_state.travelers}
        label = st.selectbox("Selecione para editar", list(options.keys()), key="trav_edit_select")
        selected = options[label]
        new_name = st.text_input("Nome", value=selected.name, key="trav_edit_name")
        new_age = st.number_input("Idade", min_value=0, max_value=120, value=selected.age, key="trav_edit_age")
        new_category = st.selectbox("Categoria", ["adult", "child", "infant"], index=["adult", "child", "infant"].index(selected.category), key="trav_edit_category")
        new_bed = st.selectbox(
            "Preferência de leito",
            ["any", "double", "queen", "king", "twin"],
            index=0 if not selected.bed_pref else ["any", "double", "queen", "king", "twin"].index(selected.bed_pref),
            key="trav_edit_bed",
        )
        partner_options = ["Nenhum"] + [f"{t.name} ({t.id[:6]})" for t in st.session_state.travelers if t.id != selected.id]
        current_partner_label = "Nenhum"
        if selected.partner_id:
            partner = next((t for t in st.session_state.travelers if t.id == selected.partner_id), None)
            if partner:
                current_partner_label = f"{partner.name} ({partner.id[:6]})"
        partner_choice = st.selectbox("Forma casal com algum viajante?", partner_options, index=partner_options.index(current_partner_label), key="trav_edit_partner")
        cols = st.columns(2)
        if cols[0].button("Salvar alterações", key="trav_edit_save"):
            selected.name = new_name or selected.name
            selected.age = int(new_age)
            selected.category = new_category
            selected.bed_pref = None if new_bed == "any" else new_bed
            new_partner_id = None
            if partner_choice != "Nenhum":
                partner = next(t for t in st.session_state.travelers if f"{t.name} ({t.id[:6]})" == partner_choice)
                new_partner_id = partner.id
                partner.partner_id = selected.id
            if selected.partner_id and selected.partner_id != new_partner_id:
                old_partner = next((t for t in st.session_state.travelers if t.id == selected.partner_id), None)
                if old_partner:
                    old_partner.partner_id = None
            selected.partner_id = new_partner_id
            st.success("Viajante atualizado.")
            st.rerun()
        if cols[1].button("Remover viajante", key="trav_edit_remove"):
            st.session_state.travelers = [t for t in st.session_state.travelers if t.id != selected.id]
            st.warning("Viajante removido.")
            st.rerun()


def render_stops():
    st.subheader("Localidades (janela fixa ou dias mínimos)")
    # Cadastro primeiro
    constraint_type = st.radio("Tipo de restrição", ["Janela fixa", "Dias mínimos"], horizontal=True, key="stop_add_constraint")
    with st.form("stop_add_form", clear_on_submit=True):
        location = render_location_picker(st, "Localidade", "stop_add_location", "")
        if constraint_type == "Janela fixa":
            d1 = st.date_input("Início da janela", key="stop_add_start", value=date.today())
            d2 = st.date_input("Fim da janela", key="stop_add_end", value=date.today())
            min_days = None
        else:
            min_days = st.number_input("Dias mínimos de permanência", min_value=1, max_value=90, value=1, key="stop_add_min_days")
            d1 = d2 = date.today()
        submitted = st.form_submit_button("Salvar localidade", use_container_width=True)
        if submitted:
            if not location.strip():
                st.error("Localidade é obrigatória.")
            else:
                st.session_state.stops.append(
                    Stop(
                        location=location.strip().upper(),
                        constraint_type="fixed_window" if constraint_type == "Janela fixa" else "flexible_days",
                        window_start=d1.isoformat() if constraint_type == "Janela fixa" else None,
                        window_end=d2.isoformat() if constraint_type == "Janela fixa" else None,
                        min_days=int(min_days) if constraint_type != "Janela fixa" else None,
                    )
                )
                st.success("Localidade adicionada.")
                st.rerun()

    # Lista e edição depois
    if st.session_state.stops:
        # Validação de dias planejados x dias de viagem
        trip_span = (st.session_state.trip_end_date - st.session_state.trip_start_date).days
        min_days_required = 0
        for s in st.session_state.stops:
            if s.constraint_type == "fixed_window" and s.window_start and s.window_end:
                try:
                    d1 = date.fromisoformat(s.window_start)
                    d2 = date.fromisoformat(s.window_end)
                    min_days_required += max(0, (d2 - d1).days)
                except Exception:
                    pass
            else:
                min_days_required += s.min_days or 0
        if min_days_required > trip_span:
            st.error(f"Os dias mínimos das localidades ({min_days_required}) excedem os dias da viagem ({trip_span}).")

        rows = [
            {
                "id": s.id[:8],
                "local": s.location,
                "tipo": "Janela fixa" if s.constraint_type == "fixed_window" else "Dias mínimos",
                "inicio": s.window_start or "-",
                "fim": s.window_end or "-",
                "min_dias": str(s.min_days or "-"),
            }
            for s in st.session_state.stops
        ]
        st.table(rows)
        st.write("Editar/Remover localidade")
        options = {f"{s.location} ({s.id[:6]})": s for s in st.session_state.stops}
        label = st.selectbox("Selecione para editar", list(options.keys()), key="stop_edit_select")
        selected = options[label]
        constraint_type = st.radio(
            "Tipo de restrição",
            ["Janela fixa", "Dias mínimos"],
            horizontal=True,
            index=0 if selected.constraint_type == "fixed_window" else 1,
            key="stop_edit_constraint",
        )
        location = render_location_picker(st, "Localidade", "stop_edit_location", selected.location)
        if constraint_type == "Janela fixa":
            d1 = st.date_input(
                "Início da janela", key="stop_edit_start", value=date.fromisoformat(selected.window_start or date.today().isoformat())
            )
            d2 = st.date_input(
                "Fim da janela", key="stop_edit_end", value=date.fromisoformat(selected.window_end or date.today().isoformat())
            )
            min_days = None
        else:
            min_days = st.number_input(
                "Dias mínimos de permanência", min_value=1, max_value=90, value=selected.min_days or 1, key="stop_edit_min_days"
            )
            d1 = d2 = date.today()
        cols = st.columns(2)
        if cols[0].button("Salvar localidade", key="stop_edit_save"):
            if not location.strip():
                st.error("Localidade é obrigatória.")
            else:
                selected.location = location.strip().upper()
                selected.constraint_type = "fixed_window" if constraint_type == "Janela fixa" else "flexible_days"
                selected.window_start = d1.isoformat() if constraint_type == "Janela fixa" else None
                selected.window_end = d2.isoformat() if constraint_type == "Janela fixa" else None
                selected.min_days = int(min_days) if constraint_type != "Janela fixa" else None
                st.success("Localidade atualizada.")
                st.rerun()
        if cols[1].button("Remover localidade", key="stop_edit_remove"):
            st.session_state.stops = [s for s in st.session_state.stops if s.id != selected.id]
            st.warning("Localidade removida.")
            st.rerun()


@st.cache_data(ttl=300, show_spinner=False)
def cached_search(req_payload: dict):
    travelers = [
        TravelerProfile(
            name=t["name"],
            age=t["age"],
            category=t["category"],
            partner_id=t.get("partner_id"),
            bed_pref=t.get("bed_pref"),
            id=t.get("id"),
        )
        for t in req_payload["travelers"]
    ]
    stops = [
        Stop(
            location=s["location"],
            constraint_type=s["constraint_type"],
            window_start=s.get("window_start"),
            window_end=s.get("window_end"),
            min_days=s.get("min_days"),
            id=s.get("id"),
        )
        for s in req_payload["stops"]
    ]
    req = SearchRequest(
        segments=[],  # não definimos trechos; o otimizador decidirá
        stops=stops,
        travelers=travelers,
        currency=req_payload["currency"],
        max_items=req_payload.get("max_items", config.DEFAULT_MAX_ITEMS),
        trip_start_location=req_payload.get("trip_start_location"),
        trip_start_date=req_payload.get("trip_start_date"),
        trip_end_location=req_payload.get("trip_end_location"),
        trip_end_date=req_payload.get("trip_end_date"),
    )
    result = run_search(req)
    return result.to_jsonable()


def build_request_payload():
    travelers = [
        {
            "name": t.name,
            "age": t.age,
            "category": t.category,
            "partner_id": t.partner_id,
            "bed_pref": t.bed_pref,
            "id": t.id,
        }
        for t in st.session_state.travelers
    ]
    stops = [
        {
            "location": s.location,
            "constraint_type": s.constraint_type,
            "window_start": s.window_start,
            "window_end": s.window_end,
            "min_days": s.min_days,
            "id": s.id,
        }
        for s in st.session_state.stops
    ]
    currency = st.session_state.currency
    return {
        "stops": stops,
        "travelers": travelers,
        "currency": currency,
        "max_items": config.DEFAULT_MAX_ITEMS,
        "trip_start_location": st.session_state.trip_start_location,
        "trip_start_date": st.session_state.trip_start_date.isoformat() if isinstance(st.session_state.trip_start_date, date) else None,
        "trip_end_location": st.session_state.trip_end_location,
        "trip_end_date": st.session_state.trip_end_date.isoformat() if isinstance(st.session_state.trip_end_date, date) else None,
    }


def render_currency_selector():
    st.session_state.currency = st.selectbox("Moeda alvo", ["USD", "BRL", "EUR"], index=0)


def render_search_and_results():
    st.subheader("Busca")
    render_currency_selector()
    if st.button("Buscar opções"):
        payload = build_request_payload()
        data = cached_search(payload)
        st.success("Busca finalizada (mock).")
        # Mostrar ordens/combinações
        scenarios = data.get("meta", {}).get("scenarios", [])
        if scenarios:
            st.subheader("Combinações de localidades (ordem)")
            trip_start = st.session_state.trip_start_location or "?"
            trip_end = st.session_state.trip_end_location or trip_start
            st.table(
                [
                    {
                        "ordem": " -> ".join([trip_start] + sc["order"] + [trip_end]),
                        "viável": sc["is_feasible"],
                        "overrun_dias": sc["overrun_days"],
                    }
                    for sc in scenarios
                ]
            )
        st.json(data)
        st.download_button(
            label="Baixar JSON",
            file_name="resultados_viagem.json",
            mime="application/json",
            data=json.dumps(data, ensure_ascii=False, indent=2),
        )


render_trip_constraints()
render_travelers()
render_stops()
render_search_and_results()
