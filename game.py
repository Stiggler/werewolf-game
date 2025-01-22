from flask import jsonify, request
import json
import sqlite3


def get_db_connection():
    conn = sqlite3.connect("players.db")
    conn.row_factory = sqlite3.Row
    return conn


def get_sorted_game_roles():
    with open("static/rollen/roles.json", "r", encoding="utf-8") as file:
        roles_data = {role["Rolle"]: role for role in json.load(file)}

    with get_db_connection() as conn:
        game_roles = conn.execute("SELECT id, role_name, instance_id FROM game_roles").fetchall()

    sorted_roles = [
        {
            "id": row["id"],
            "Rolle": row["role_name"],
            "instance_id": row["instance_id"],
            **roles_data.get(row["role_name"], {})
        }
        for row in game_roles if row["role_name"] in roles_data
    ]

    sorted_roles.sort(key=lambda x: x["first_night"] or float('inf'))
    return sorted_roles



def get_players():
    with get_db_connection() as conn:
        players = conn.execute("SELECT id, name, image, role FROM players").fetchall()
    return [
        {"id": row["id"], "name": row["name"], "image": row["image"], "role": row["role"]}
        for row in players
    ]



def assign_role():
    data = request.json
    player_id = data.get('player_id')
    role_name = data.get('role_name')
    instance_id = data.get('instance_id')  # Hole die Instanz-ID

    if not player_id or not role_name or not instance_id:
        return jsonify({"error": "player_id, role_name oder instance_id fehlt"}), 400

    try:
        with get_db_connection() as conn:
            # Überprüfen, ob diese Instanz der Rolle bereits vergeben ist
            conn.execute(
                "DELETE FROM players WHERE role = ? AND instance_id = ?",
                (role_name, instance_id)
            )

            # Spielerrolle aktualisieren
            conn.execute(
                "UPDATE players SET role = ?, instance_id = ? WHERE id = ?",
                (role_name, instance_id, player_id)
            )
            conn.commit()

        return jsonify({"message": "Rolle erfolgreich zugewiesen"}), 200
    except Exception as e:
        print(f"Fehler beim Zuweisen der Rolle: {e}")
        return jsonify({"error": str(e)}), 500



def initialize_game():
    try:
        with get_db_connection() as conn:
            conn.execute("UPDATE players SET role = NULL")
            conn.commit()
        return {"message": "Spiel erfolgreich initialisiert."}, 200
    except Exception as e:
        print(f"Fehler beim Initialisieren des Spiels: {e}")
        return {"error": "Fehler beim Initialisieren des Spiels"}, 500
