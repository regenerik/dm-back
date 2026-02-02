from flask import Blueprint, jsonify, request
from database import db
from models import User, Sector, UserSectorAccess
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity

permissions_bp = Blueprint("permissions_bp", __name__)


def admin_required():
    dni = get_jwt_identity()
    print("JWT identity:", dni, type(dni))
    if dni is None:
        return False

    # por si viene string
    try:
        dni = int(dni)
    except (TypeError, ValueError):
        return False

    user = User.query.get(dni) or User.query.filter_by(dni=dni).first()
    return bool(user and user.admin is True)


@permissions_bp.route("/users/<int:dni>/permissions", methods=["GET"])
@jwt_required()
def get_user_permissions(dni):
    if not admin_required():
        return jsonify({"error": "Acceso denegado (admin requerido)."}), 403

    user = User.query.get(dni)
    if not user:
        return jsonify({"error": "Usuario no encontrado."}), 404

    sectors = Sector.query.order_by(Sector.id.asc()).all()

    access_rows = UserSectorAccess.query.filter_by(user_dni=dni).all()
    access_map = {a.sector_id: bool(a.enabled) for a in access_rows}

    permissions = []
    for s in sectors:
        enabled = access_map.get(s.id, bool(s.default_enabled))
        permissions.append({
            "key": s.key,
            "label": s.label,
            "description": s.description,
            "enabled": enabled
        })

    return jsonify({"dni": dni, "permissions": permissions}), 200


@permissions_bp.route("/users/<int:dni>/permissions", methods=["PUT"])
@jwt_required()
def update_user_permissions(dni):
    if not admin_required():
        return jsonify({"error": "Acceso denegado (admin requerido)."}), 403

    user = User.query.get(dni)
    if not user:
        return jsonify({"error": "Usuario no encontrado."}), 404

    data = request.get_json(silent=True) or {}
    incoming = data.get("permissions")

    if not isinstance(incoming, list):
        return jsonify({"error": "Formato inválido. Se espera permissions: []"}), 400

    # Armamos mapa key -> enabled
    incoming_map = {}
    for item in incoming:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        enabled = item.get("enabled")
        if isinstance(key, str) and isinstance(enabled, bool):
            incoming_map[key] = enabled

    if not incoming_map:
        return jsonify({"error": "No hay permisos válidos para guardar."}), 400

    # Traemos sectores por key
    sectors = Sector.query.filter(Sector.key.in_(incoming_map.keys())).all()
    sectors_by_key = {s.key: s for s in sectors}

    missing = [k for k in incoming_map.keys() if k not in sectors_by_key]
    if missing:
        return jsonify({"error": f"Keys inexistentes: {missing}"}), 400

    # Traemos accesos existentes del usuario
    existing_rows = UserSectorAccess.query.filter_by(user_dni=dni).all()
    existing_map = {r.sector_id: r for r in existing_rows}

    for key, enabled in incoming_map.items():
        sector = sectors_by_key[key]
        row = existing_map.get(sector.id)

        if row:
            row.enabled = bool(enabled)
        else:
            row = UserSectorAccess(
                user_dni=dni,
                sector_id=sector.id,
                enabled=bool(enabled)
            )
            db.session.add(row)

    db.session.commit()

    # Devolvemos lista de keys habilitadas (opción C que te gustó)
    enabled_keys = [k for k, v in incoming_map.items() if v is True]
    return jsonify({"message": "Permisos actualizados.", "permissions": enabled_keys}), 200
