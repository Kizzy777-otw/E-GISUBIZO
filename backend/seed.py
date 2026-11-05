"""Initial diagnostic content and pilot inventory."""

from hashlib import sha256
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import DiagnosticTree, HardwareUnit, User, utc_now


DIAGNOSTIC_TREES: tuple[dict, ...] = (
    {
        "slug": "biogas-low-flame",
        "appliance_type": "biogas",
        "version": 1,
        "active": True,
        "content": {
            "title": "Umuriro wa biogaz ni muke",
            "subtitle": "Biogas flame is weak",
            "start_node": "water_check",
            "nodes": {
                "water_check": {
                    "type": "question",
                    "icon": "💧",
                    "question": "Ese amazi ari mu muyoboro wa gaz?",
                    "translation": "Is there water in the gas line?",
                    "answers": [
                        {"id": "yes", "label": "Yego / Yes", "next": "drain_water"},
                        {"id": "no", "label": "Oya / No", "next": "feed_check"},
                    ],
                },
                "drain_water": {
                    "type": "resolution",
                    "icon": "🚰",
                    "title": "Kuramo amazi mu muyoboro",
                    "translation": "Drain the water from the gas line",
                    "instructions": [
                        {"icon": "⛔", "text": "Banza uzimye umuriro kandi wirinde urumuri cyangwa itabi hafi ya gaz."},
                        {"icon": "🔧", "text": "Fungura umuyoboro wo gusohora amazi niba uzi neza uko ukora."},
                        {"icon": "🧑‍🔧", "text": "Niba utizeye cyangwa ikibazo gikomeje, saba umutekinisiye."},
                    ],
                },
                "feed_check": {
                    "type": "question",
                    "icon": "🍋",
                    "question": "Waba warashyizemo indyo nyinshi cyangwa ibintu birimo aside nk’indimu?",
                    "translation": "Was it overfed or recently fed acidic/citrus waste?",
                    "answers": [
                        {"id": "yes", "label": "Yego / Yes", "next": "pause_feeding"},
                        {"id": "no", "label": "Oya / No", "next": "bag_check"},
                    ],
                },
                "pause_feeding": {
                    "type": "resolution",
                    "icon": "🌱",
                    "title": "Hagarika kongeramo indyo by’agateganyo",
                    "translation": "Pause feeding and add water",
                    "instructions": [
                        {"icon": "⏸️", "text": "Hagarika kongeramo indyo mu gihe gito."},
                        {"icon": "💧", "text": "Ongeramo amazi asukuye gusa ku rugero usanzwe ukoresha."},
                        {"icon": "⚠️", "text": "Ntukoreshe aside cyangwa imiti. Niba ikibazo gikomeje, saba umutekinisiye."},
                    ],
                },
                "bag_check": {
                    "type": "question",
                    "icon": "🎈",
                    "question": "Umufuka wa digesiteri urabyimbye cyangwa warafashe umwuka?",
                    "translation": "Is the digester bag inflated?",
                    "answers": [
                        {"id": "yes", "label": "Yego / Yes", "next": "gas_obstruction"},
                        {"id": "no", "label": "Oya, waragabanutse / No, deflated", "next": "possible_leak"},
                    ],
                },
                "gas_obstruction": {
                    "type": "ticket",
                    "icon": "🧑‍🔧",
                    "title": "Hakenewe umutekinisiye",
                    "translation": "Possible gas-line obstruction or pressure-valve fault",
                    "fault_code": "BIO_GAS_LINE_PRESSURE",
                    "fault_category": "Biogas line or pressure valve",
                    "priority": "High",
                    "instructions": ["Ntukagerageze gusenya valve cyangwa gufungura umuyoboro wa gaz."],
                },
                "possible_leak": {
                    "type": "ticket",
                    "icon": "🧑‍🔧",
                    "title": "Hakenewe igenzura ry’umutekinisiye",
                    "translation": "Possible digester gas leak",
                    "fault_code": "BIO_DIGESTER_POSSIBLE_LEAK",
                    "fault_category": "Possible digester leak",
                    "priority": "High",
                    "instructions": ["Ntukagerageze gushakisha aho gaz yacitse ukoresheje urumuri cyangwa gukosora umufuka."],
                },
            },
        },
    },
    {
        "slug": "solar-red-indicator",
        "appliance_type": "solar",
        "version": 1,
        "active": True,
        "content": {
            "title": "Itara rya batiri riraka umutuku",
            "subtitle": "Solar battery or inverter red light",
            "start_node": "panel_check",
            "nodes": {
                "panel_check": {
                    "type": "question",
                    "icon": "☀️",
                    "question": "Ese imirasire y’izuba ibuza igicucu, umukungugu cyangwa ikindi kintu?",
                    "translation": "Is the panel dusty, shaded, or obstructed?",
                    "answers": [
                        {"id": "yes", "label": "Yego / Yes", "next": "clean_panel"},
                        {"id": "no", "label": "Oya / No", "next": "load_check"},
                    ],
                },
                "clean_panel": {
                    "type": "resolution",
                    "icon": "🧹",
                    "title": "Sukura cyangwa ukureho igicucu",
                    "translation": "Clean the panel or remove shading",
                    "instructions": [
                        {"icon": "🔌", "text": "Koresha amazi make n’agatambaro koroshye, kandi wirinde gukandagira kuri panel."},
                        {"icon": "🌳", "text": "Kuraho igicucu gusa niba kubikora ari umutekano."},
                        {"icon": "⚠️", "text": "Ntukore ku nsinga cyangwa ku bikoresho by’amashanyarazi."},
                    ],
                },
                "load_check": {
                    "type": "question",
                    "icon": "🔌",
                    "question": "Hari igikoresho gikoresha umuriro mwinshi wongeyeho vuba aha?",
                    "translation": "Was a high-draw appliance recently added?",
                    "answers": [
                        {"id": "yes", "label": "Yego / Yes", "next": "reduce_load"},
                        {"id": "no", "label": "Oya / No", "next": "battery_led_check"},
                    ],
                },
                "reduce_load": {
                    "type": "resolution",
                    "icon": "🔋",
                    "title": "Gabanya ibikoresho bikoresha umuriro",
                    "translation": "Disconnect the added load and check the fuse",
                    "instructions": [
                        {"icon": "🔌", "text": "Zimya cyangwa ukureho igikoresho gishya ukoresheje uburyo busanzwe bwo kugifungura."},
                        {"icon": "⚠️", "text": "Reba fuse uyireba gusa; ntuyikuremo cyangwa ngo ukore ku nsinga."},
                        {"icon": "🧑‍🔧", "text": "Niba itara ritakize, saba umutekinisiye."},
                    ],
                },
                "battery_led_check": {
                    "type": "question",
                    "icon": "🔴",
                    "question": "Itara rya batiri riracana ritukuye rikazima, cyangwa ntiricana na gato?",
                    "translation": "Is the red battery LED flashing, or is it completely off?",
                    "answers": [
                        {"id": "flashing", "label": "Riracana rikazima / Flashing", "next": "controller_fault"},
                        {"id": "off", "label": "Ntiryaka / Off", "next": "battery_fault"},
                    ],
                },
                "controller_fault": {
                    "type": "ticket",
                    "icon": "🧑‍🔧",
                    "title": "Hakenewe umutekinisiye",
                    "translation": "Possible charge-controller or over-discharge fault",
                    "fault_code": "SOLAR_CONTROLLER_OR_DISCHARGE",
                    "fault_category": "Charge controller or battery over-discharge",
                    "priority": "High",
                    "instructions": ["Ntukingure cyangwa ngo ukore ku bikoresho by’amashanyarazi."],
                },
                "battery_fault": {
                    "type": "ticket",
                    "icon": "🧑‍🔧",
                    "title": "Hakenewe igenzura rya batiri",
                    "translation": "Possible battery degradation or internal fault",
                    "fault_code": "SOLAR_BATTERY_POSSIBLE_FAULT",
                    "fault_category": "Possible battery degradation or internal fault",
                    "priority": "High",
                    "instructions": ["Ntukagerageze gufungura, gusimbuza cyangwa gusana batiri ubwawe."],
                },
            },
        },
    },
)


def seed_initial_data(db: Session) -> None:
    """Insert initial trees, pilot hardware, and only explicitly configured users."""
    # Seed by stable slug/ID so application restarts do not duplicate pilot records.
    for tree_data in DIAGNOSTIC_TREES:
        if db.scalar(select(DiagnosticTree).where(DiagnosticTree.slug == tree_data["slug"])) is None:
            db.add(DiagnosticTree(**tree_data))

    demo_units = (
        ("BIO-RW-0001", "biogas"),
        ("SOL-RW-0001", "solar"),
    )
    for hardware_id, model_type in demo_units:
        if db.get(HardwareUnit, hardware_id) is None:
            db.add(
                HardwareUnit(
                    hardware_id=hardware_id,
                    model_type=model_type,
                    district="Rulindo",
                    sector="Base",
                )
            )

    configured_users = (
        ("technician", "technician", os.getenv("TECHNICIAN_API_TOKEN")),
        ("administrator", "admin", os.getenv("ADMIN_API_TOKEN")),
    )
    for username, role, token in configured_users:
        if not token:
            continue
        token_hash = sha256(token.encode("utf-8")).hexdigest()
        user = db.scalar(select(User).where(User.username == username))
        if user is None:
            user = User(username=username, role=role, token_hash=token_hash)
            db.add(user)
        else:
            user.token_hash = token_hash
        if role == "technician":
            user.district = os.getenv("TECHNICIAN_DISTRICT", "Rulindo")
            user.sector = os.getenv("TECHNICIAN_SECTOR") or None

    db.commit()
