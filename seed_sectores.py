# seed_sectores.py
from database import db
from models import Sector  # ajustá el import según tu estructura


SECTORES_BASE = [
    {
        "key": "course_creator",
        "label": "Creador de cursos",
        "description": "Herramientas para crear cursos",
        "default_enabled": False,
    },
    {
        "key": "needs_apies",
        "label": "Necesidades Apies",
        "description": "Módulo de necesidades por estación (Apies)",
        "default_enabled": False,
    },
    {
        "key": "chat_data_mentor",
        "label": "Chat Data Mentor",
        "description": "Chat asistido para Data Mentor",
        "default_enabled": False,
    },
    {
        "key": "talent_management",
        "label": "Gestión de talento",
        "description": "Módulo de talento / RRHH",
        "default_enabled": False,
    },
    {
        "key": "presentations",
        "label": "Presentaciones",
        "description": "Generación/gestión de presentaciones",
        "default_enabled": False,
    },
    {
        "key": "recommendations_form",
        "label": "Formulario para recomendaciones",
        "description": "Formulario para capturar recomendaciones",
        "default_enabled": False,
    },
    {
        "key": "admin_settings",
        "label": "Ajustes administrador",
        "description": "Panel de ajustes (igual esto debería depender de admin)",
        "default_enabled": False,
    },
]


def cargar_sectores_iniciales_si_no_existen():
    """
    Crea los sectores base si no existen.
    Es idempotente: podés llamarla siempre en el arranque sin duplicar nada.
    """
    creados = 0
    actualizados = 0

    for s in SECTORES_BASE:
        sector = Sector.query.filter_by(key=s["key"]).first()

        if not sector:
            sector = Sector(
                key=s["key"],
                label=s["label"],
                description=s.get("description", ""),
                default_enabled=bool(s.get("default_enabled", False)),
            )
            db.session.add(sector)
            creados += 1
        else:
            # Si querés que también “sincronice” cambios de label/description por si editás el seed
            changed = False
            if sector.label != s["label"]:
                sector.label = s["label"]
                changed = True
            if (sector.description or "") != (s.get("description", "") or ""):
                sector.description = s.get("description", "")
                changed = True
            if bool(sector.default_enabled) != bool(s.get("default_enabled", False)):
                sector.default_enabled = bool(s.get("default_enabled", False))
                changed = True

            if changed:
                actualizados += 1

    db.session.commit()
    print(f"[SECTORES] creados={creados} actualizados={actualizados} total={len(SECTORES_BASE)}")
