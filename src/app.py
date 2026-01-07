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
from src.services.nsga2_solver import solve_nsga2, diagnose_missing  # noqa: E402
from src.utils.autocomplete import search_locations  # noqa: E402
from src.utils.cancel import request_cancel, clear_cancel  # noqa: E402

st.set_page_config(page_title="Planejador de Viagens - Kayak", layout="wide")
st.title("Planejador de Viagens (BR-EUA)")


DEFAULT_LOCATION_CODE = "GYN"


def render_location_picker(container, label: str, key: str, current: str) -> str:
    """Renderiza um selectbox de localidades com busca interna.

    Args:
        container: container Streamlit onde o selectbox será renderizado.
        label: rótulo do campo.
        key: chave base para o estado do widget.
        current: código atual selecionado.

    Returns:
        Código da localidade escolhida.
    """
    options = search_locations("", limit=5000)
    if not options:
        return current.strip().upper()
    display = [f"{o['code']} - {o['city']}/{o['state']} ({o['country']})" for o in options]
    default_index = 0
    target_code = current or DEFAULT_LOCATION_CODE
    if target_code:
        for i, opt in enumerate(options):
            if opt["code"] == target_code:
                default_index = i
                break
    choice = container.selectbox(label, display, index=default_index, key=f"{key}_select")
    idx = display.index(choice)
    return options[idx]["code"]


def init_state():
    """Inicializa chaves do estado da sessão com valores padrão.

    Args:
        None.

    Returns:
        None.
    """
    st.session_state.setdefault("travelers", [])
    st.session_state.setdefault("stops", [])
    st.session_state.setdefault("currency", "BRL")
    st.session_state.setdefault("trip_start_location", DEFAULT_LOCATION_CODE)
    st.session_state.setdefault("trip_end_location", DEFAULT_LOCATION_CODE)
    st.session_state.setdefault("trip_start_date", date.today())
    st.session_state.setdefault("trip_end_date", date.today())
    st.session_state.setdefault("last_search_data", None)
    st.session_state.setdefault("last_nsga_solutions", None)
    st.session_state.setdefault("last_preview_rows", [])


init_state()


def render_trip_constraints():
    """Renderiza os campos de inicio e fim da viagem na interface.

    Args:
        None.

    Returns:
        None.
    """
    st.subheader("Parâmetros da viagem (início/fim)")
    col1, col2 = st.columns(2)
    st.session_state.trip_start_location = render_location_picker(col1, "Local de início da viagem", "trip_start_loc", st.session_state.trip_start_location)
    col2.date_input("Data mínima para início da viagem", key="trip_start_date")
    col3, col4 = st.columns(2)
    st.session_state.trip_end_location = render_location_picker(col3, "Local de término da viagem", "trip_end_loc", st.session_state.trip_end_location)
    col4.date_input("Data máxima para término da viagem", key="trip_end_date")


# def render_travelers():
#     st.subheader("Viajantes")
#     with st.expander("Adicionar viajante"):
#         with st.form("trav_add_form", clear_on_submit=True):
#             name = st.text_input("Nome", key="trav_add_name")
#             age = st.number_input("Idade", min_value=0, max_value=120, value=30, key="trav_add_age")
#             category = st.selectbox("Categoria", ["adult", "child", "infant"], key="trav_add_category")
#             bed_pref = st.selectbox("Preferência de leito", ["any", "double", "queen", "king", "twin"], index=0, key="trav_add_bed")
#             submitted = st.form_submit_button("Salvar viajante", use_container_width=True)
#             if submitted:
#                 st.session_state.travelers.append(
#                     TravelerProfile(
#                         name=name or f"Viajante {len(st.session_state.travelers)+1}",
#                         age=int(age),
#                         category=category,
#                         bed_pref=bed_pref if bed_pref != "any" else None,
#                     )
#                 )
#                 st.success("Viajante adicionado.")
#                 st.rerun()

#     if st.session_state.travelers:
#         rows = [
#             {
#                 "nome": t.name,
#                 "idade": t.age,
#                 "categoria": t.category,
#                 "par": next((p.name for p in st.session_state.travelers if p.id == t.partner_id), "-"),
#                 "leito": t.bed_pref or "-",
#             }
#             for t in st.session_state.travelers
#         ]
#         st.table(rows)

#     if st.session_state.travelers:
#         st.write("Editar/Remover viajante")
#         options = {f"{t.name} ({t.id[:6]})": t for t in st.session_state.travelers}
#         label = st.selectbox("Selecione para editar", list(options.keys()), key="trav_edit_select")
#         selected = options[label]
#         new_name = st.text_input("Nome", value=selected.name, key="trav_edit_name")
#         new_age = st.number_input("Idade", min_value=0, max_value=120, value=selected.age, key="trav_edit_age")
#         new_category = st.selectbox("Categoria", ["adult", "child", "infant"], index=["adult", "child", "infant"].index(selected.category), key="trav_edit_category")
#         new_bed = st.selectbox(
#             "Preferência de leito",
#             ["any", "double", "queen", "king", "twin"],
#             index=0 if not selected.bed_pref else ["any", "double", "queen", "king", "twin"].index(selected.bed_pref),
#             key="trav_edit_bed",
#         )
#         partner_options = ["Nenhum"] + [f"{t.name} ({t.id[:6]})" for t in st.session_state.travelers if t.id != selected.id]
#         current_partner_label = "Nenhum"
#         if selected.partner_id:
#             partner = next((t for t in st.session_state.travelers if t.id == selected.partner_id), None)
#             if partner:
#                 current_partner_label = f"{partner.name} ({partner.id[:6]})"
#         partner_choice = st.selectbox("Forma casal com algum viajante?", partner_options, index=partner_options.index(current_partner_label), key="trav_edit_partner")
#         cols = st.columns(2)
#         if cols[0].button("Salvar alterações", key="trav_edit_save"):
#             selected.name = new_name or selected.name
#             selected.age = int(new_age)
#             selected.category = new_category
#             selected.bed_pref = None if new_bed == "any" else new_bed
#             new_partner_id = None
#             if partner_choice != "Nenhum":
#                 partner = next(t for t in st.session_state.travelers if f"{t.name} ({t.id[:6]})" == partner_choice)
#                 new_partner_id = partner.id
#                 partner.partner_id = selected.id
#             if selected.partner_id and selected.partner_id != new_partner_id:
#                 old_partner = next((t for t in st.session_state.travelers if t.id == selected.partner_id), None)
#                 if old_partner:
#                     old_partner.partner_id = None
#             selected.partner_id = new_partner_id
#             st.success("Viajante atualizado.")
#             st.rerun()
#         if cols[1].button("Remover viajante", key="trav_edit_remove"):
#             st.session_state.travelers = [t for t in st.session_state.travelers if t.id != selected.id]
#             st.warning("Viajante removido.")
#             st.rerun()

def render_travelers():
    """Renderiza a gestão de viajantes com modo rápido ou detalhado.

    Args:
        None.

    Returns:
        None.
    """
    st.subheader("Viajantes")
    
    # Seletor de modo de cadastro
    mode = st.radio(
        "Modo de cadastro", 
        ["Quantidade (Rápido)", "Detalhado (Nome, Idade, Preferências)"], 
        horizontal=True,
        key="traveler_input_mode"
    )
    
    st.markdown("---")

    if mode == "Quantidade (Rápido)":
        col1, col2 = st.columns(2)
        # Inputs numéricos para quantidade
        qtd_adults = col1.number_input("Quantidade de Adultos", min_value=1, value=1, step=1, key="qty_adults")
        qtd_children = col2.number_input("Quantidade de Crianças", min_value=0, value=0, step=1, key="qty_children")
        
        # Botão para confirmar a alteração de quantidade
        # Isso gera os perfis automaticamente
        if st.button("Atualizar Quantidade de Viajantes", key="btn_update_qty") or (len(st.session_state.travelers) == 0):
            new_travelers = []
            # Gera perfis genéricos para Adultos
            for i in range(qtd_adults):
                new_travelers.append(
                    TravelerProfile(
                        name=f"Adulto {i+1}",
                        age=30,
                        category="adult",
                        bed_pref="any"
                    )
                )
            # Gera perfis genéricos para Crianças
            for i in range(qtd_children):
                new_travelers.append(
                    TravelerProfile(
                        name=f"Criança {i+1}",
                        age=10,
                        category="child",
                        bed_pref="any"
                    )
                )
            st.session_state.travelers = new_travelers
            st.success(f"Lista atualizada: {len(new_travelers)} viajantes definidos.")
            st.rerun()
            
        if st.session_state.travelers:
            st.info(f"Viajantes configurados: {len(st.session_state.travelers)} (Perfis gerados automaticamente).")

    else:
        # --- MODO DETALHADO (Lógica Original) ---
        with st.expander("Adicionar viajante manual"):
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
            if label:
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
    """Renderiza o cadastro e a edicao de localidades (stops).

    Args:
        None.

    Returns:
        None.
    """
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
    """Executa a busca usando o payload ja serializado, com cache de 5 minutos.

    Args:
        req_payload: dicionario com dados da viagem, viajantes e stops.

    Returns:
        Dicionario com resultados e metadados prontos para JSON.
    """
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
        flight_sort_criteria=req_payload.get("flight_sort_criteria", "best"),
    )
    result = run_search(req)
    return result.to_jsonable()


def build_request_payload():
    """Monta o payload com dados atuais da sessao para a busca.

    Args:
        None.

    Returns:
        Dicionario com dados da viagem, viajantes e stops.
    """
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
    """Define a moeda fixa da aplicacao na interface.

    Args:
        None.

    Returns:
        None.
    """
    # Kayak .com.br retorna preços em BRL; mantemos moeda fixa
    st.session_state.currency = "BRL"
    st.caption("Moeda fixa: BRL (origem Kayak .com.br)")


def render_search_and_results():
    """Renderiza o bloco de busca, resultados e saidas do solver.

    Args:
        None.

    Returns:
        None.
    """
    st.subheader("Busca")
    render_currency_selector()

    col_sort, _ = st.columns([1, 1])
    with col_sort:
        sort_label = st.radio(
            "Prioridade na busca de voos", 
            ["Melhor Custo-Benefício", "Menor Preço", "Menor Duração"], 
            horizontal=True,
            key="flight_sort_radio"
        )
    
    sort_map = {
        "Melhor Custo-Benefício": "best",
        "Menor Preço": "price",
        "Menor Duração": "duration"
    }
    selected_sort = sort_map[sort_label]

    col_search, col_cancel = st.columns([1, 1])
    with col_search:
        search_clicked = st.button("Buscar opções")
    with col_cancel:
        cancel_clicked = st.button("Cancelar busca")

    if cancel_clicked:
        request_cancel()
        st.warning("Cancelamento solicitado. A busca sera interrompida assim que possivel.")

    if search_clicked:
        clear_cancel()
        payload = build_request_payload()
        # Injeta a escolha no payload
        payload["flight_sort_criteria"] = selected_sort
        st.session_state.last_solver_preference = selected_sort
        # Pré-visualiza combinações sem chamar scrapers (rápido)

        preview_req = SearchRequest(
            segments=[],
            stops=[
                Stop(
                    location=s["location"],
                    constraint_type=s["constraint_type"],
                    window_start=s.get("window_start"),
                    window_end=s.get("window_end"),
                    min_days=s.get("min_days"),
                    id=s.get("id"),
                )
                for s in payload["stops"]
            ],
            travelers=[
                TravelerProfile(
                    name=t["name"],
                    age=t["age"],
                    category=t["category"],
                    partner_id=t.get("partner_id"),
                    bed_pref=t.get("bed_pref"),
                    id=t.get("id"),
                )
                for t in payload["travelers"]
            ],
            currency=payload["currency"],
            max_items=payload["max_items"],
            trip_start_location=payload["trip_start_location"],
            trip_start_date=payload["trip_start_date"],
            trip_end_location=payload["trip_end_location"],
            trip_end_date=payload["trip_end_date"],
            flight_sort_criteria=selected_sort,
        )
        preview = run_search(preview_req, include_scrapers=False)
        scenarios_preview = preview.meta.get("scenarios", [])
        if scenarios_preview:
            st.write("Combinações a serem buscadas:")
            rows = []
            for sc in scenarios_preview:
                stays = sc.get("stays", [])
                per_city = []
                for stay in stays:
                    if stay.get("type") != "main":
                        continue
                    checkin = (stay.get("checkin") or "").split("T")[0]
                    checkout = (stay.get("checkout") or "").split("T")[0]
                    per_city.append(f"{stay.get('location')} ({checkin} -> {checkout})")
                rows.append(
                    {
                        "ordem": " -> ".join([payload["trip_start_location"]] + sc["order"] + [payload["trip_end_location"]]),
                        "datas": " | ".join(per_city),
                        "viável": sc["is_feasible"],
                        "Excede a data fim (dias)": sc["overrun_days"],
                    }
                )
            st.table(rows)
            st.session_state.last_preview_rows = rows
        else:
            st.session_state.last_preview_rows = []
        with st.spinner("Encontrando voos, carros e hospedagem..."):
            data = cached_search(payload)
        nsga_solutions = solve_nsga2(
            data,
            preference=selected_sort,
            max_solutions=config.NSGA_MAX_SOLUTIONS,
        )
        if not nsga_solutions:
            missing = diagnose_missing(data)
            data.setdefault("meta", {})["solver_status"] = {
                "status": "no_solution",
                "reason": "faltam voos, hoteis ou carros para o itinerario completo",
                "missing": missing,
            }
        else:
            data.setdefault("meta", {})["solver_status"] = {
                "status": "ok",
                "reason": None,
                "missing": [],
            }
        st.session_state.last_search_data = data
        st.session_state.last_nsga_solutions = nsga_solutions
        st.success("Busca finalizada.")

    data = st.session_state.last_search_data
    nsga_solutions = st.session_state.last_nsga_solutions
    if data:
        with st.expander("JSON enviado ao solver", expanded=False):
            st.json(data)
            st.download_button(
                label="Baixar JSON",
                file_name="resultados_viagem.json",
                mime="application/json",
                data=json.dumps(data, ensure_ascii=False, indent=2),
            )

    def _format_date(value: str) -> str:
        """Extrai a parte de data (YYYY-MM-DD) de um datetime ISO.

        Args:
            value: string ISO de data/hora.

        Returns:
            String apenas com a data.
        """
        return (value or "").split("T")[0]

    def _format_itinerary(sol: dict) -> List[str]:
        """Formata uma solucao em linhas legiveis por ordem temporal.

        Args:
            sol: dicionario com selecoes do solver.

        Returns:
            Lista de strings descritivas do itinerario.
        """
        events = []
        for flight in sol["selections"].get("flights", []):
            leg = flight.get("leg", {})
            events.append(
                {
                    "when": leg.get("departure", ""),
                    "text": (
                        f"Voo {leg.get('origin')} -> {leg.get('destination')} "
                        f"| Data: {_format_date(leg.get('departure'))} "
                        f"| Horario: {flight.get('details', {}).get('times', '-') or '-'} "
                        f"| Companhia: {flight.get('provider') or '-'} "
                        f"| Preco: {flight.get('price')} {flight.get('currency')}"
                    ),
                }
            )
        for stay in sol["selections"].get("hotels", []):
            events.append(
                {
                    "when": stay.get("checkin", ""),
                    "text": (
                        f"Hotel em {stay.get('city')} "
                        f"| {stay.get('name')} "
                        f"| {_format_date(stay.get('checkin'))} -> {_format_date(stay.get('checkout'))} "
                        f"| Noites: {stay.get('nights')} "
                        f"| Preco: {stay.get('price_total')} {stay.get('currency')}"
                    ),
                }
            )
        for car in sol["selections"].get("cars", []):
            block = car.get("rental_block", {})
            fuel_cost = (car.get("details") or {}).get("fuel_cost")
            events.append(
                {
                    "when": block.get("pickup_date", ""),
                    "text": (
                        f"Carro {block.get('pickup')} -> {block.get('dropoff')} "
                        f"| {_format_date(block.get('pickup_date'))} -> {_format_date(block.get('dropoff_date'))} "
                        f"| {car.get('name')} "
                        f"| Agencia: {car.get('details', {}).get('agency', '-') or '-'} "
                        f"| Locacao: {car.get('price_total')} {car.get('currency')} "
                        f"| Combustivel: {fuel_cost} {car.get('currency')}"
                    ),
                }
            )
        events_sorted = sorted(events, key=lambda e: e["when"])
        return [e["text"] for e in events_sorted]

    if nsga_solutions:
        st.subheader("Melhores solucoes (NSGA-II)")
        preference = st.session_state.get("last_solver_preference", "best")
        if preference == "price":
            ordered_solutions = sorted(
                nsga_solutions,
                key=lambda s: (s["objectives"]["cost_total"], s["objectives"]["flight_duration_hours"]),
            )
        elif preference == "duration":
            ordered_solutions = sorted(
                nsga_solutions,
                key=lambda s: (s["objectives"]["flight_duration_hours"], s["objectives"]["cost_total"]),
            )
        else:
            weight_cost = getattr(config, "NSGA_WEIGHT_COST", 0.5)
            weight_duration = getattr(config, "NSGA_WEIGHT_DURATION", 0.5)
            min_cost = min(s["objectives"]["cost_total"] for s in nsga_solutions)
            max_cost = max(s["objectives"]["cost_total"] for s in nsga_solutions)
            min_dur = min(s["objectives"]["flight_duration_hours"] for s in nsga_solutions)
            max_dur = max(s["objectives"]["flight_duration_hours"] for s in nsga_solutions)

            def _score(sol: dict) -> float:
                cost = sol["objectives"]["cost_total"]
                dur = sol["objectives"]["flight_duration_hours"]
                norm_cost = 0.0 if max_cost == min_cost else (cost - min_cost) / (max_cost - min_cost)
                norm_dur = 0.0 if max_dur == min_dur else (dur - min_dur) / (max_dur - min_dur)
                return (weight_cost * norm_cost) + (weight_duration * norm_dur)

            ordered_solutions = sorted(nsga_solutions, key=_score)

        for idx, sol in enumerate(ordered_solutions, start=1):
            st.markdown(
                f"**Solucao {idx}** | Custo: {sol['objectives']['cost_total']} | Duracao: {sol['objectives']['flight_duration_hours']}h"
            )
            for line in _format_itinerary(sol):
                st.write(f"- {line}")

        with st.expander("JSON das solucoes (NSGA-II)"):
            st.json(ordered_solutions)
            st.download_button(
                label="Baixar solucoes (NSGA-II)",
                file_name="solucoes_nsga2.json",
                mime="application/json",
                data=json.dumps(ordered_solutions, ensure_ascii=False, indent=2),
            )
    elif data is not None:
        st.warning("Nenhum itinerario completo disponivel (faltam voos, hoteis ou carros).")
        missing = data.get("meta", {}).get("solver_status", {}).get("missing", [])
        if missing:
            st.write("Faltas por combinacao:")
            for item in missing:
                order = " -> ".join(item.get("order") or [])
                if item.get("missing_legs"):
                    legs_text = "; ".join(
                        [
                            f"{leg['origin']} -> {leg['destination']} em {leg['date']}"
                            for leg in item["missing_legs"]
                        ]
                    )
                    st.write(f"- {order} | Pernas sem transporte: {legs_text}")
                if item.get("missing_hotels"):
                    hotels_text = "; ".join(
                        [
                            f"{stay['location']} ({stay['checkin']} -> {stay['checkout']})"
                            for stay in item["missing_hotels"]
                        ]
                    )
                    st.write(f"- {order} | Estadas sem hotel: {hotels_text}")


render_trip_constraints()
render_travelers()
render_stops()
render_search_and_results()
