from flask import Flask, jsonify, request, render_template
import os
import sqlite3

app = Flask(__name__, template_folder='templates')

# Initialisiere die Datenbank
def init_db():
    with sqlite3.connect("players.db") as conn:
        cursor = conn.cursor()
        # Playerpool-Tabelle
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS playerpool (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                image TEXT
            )
        """)
        # Players-Tabelle
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                image TEXT,
                role TEXT
            )
        """)
        # Game roles Tabelle
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS game_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_name TEXT NOT NULL,
                instance_id INTEGER
            )
        """)
    print("Database initialized!")

# Verbindung zur Datenbank abrufen
def get_db_connection():
    conn = sqlite3.connect("players.db")
    conn.row_factory = sqlite3.Row
    return conn

# Startseite
@app.route('/')
def home():
    return render_template('index.html')

# Spielerpool abrufen
@app.route('/playerpool', methods=['GET'])
def get_playerpool():
    with get_db_connection() as conn:
        players = conn.execute("SELECT * FROM playerpool").fetchall()
    return jsonify([{"id": row["id"], "name": row["name"], "image": row["image"]} for row in players])

# Spieler hinzufügen
@app.route('/add_to_pool', methods=['POST'])
def add_to_pool():
    name = request.form.get('name')
    image = request.files.get('image')

    if not name:
        return jsonify({"error": "Name is required"}), 400

    os.makedirs('static', exist_ok=True)
    image_path = None
    if image:
        image_path = f"static/{name}.png"
        image.save(image_path)

    with get_db_connection() as conn:
        try:
            conn.execute("INSERT INTO playerpool (name, image) VALUES (?, ?)", (name, image_path))
            conn.commit()
        except sqlite3.IntegrityError:
            return jsonify({"error": "Player already exists in the pool"}), 400

    return jsonify({"message": "Player added to pool", "image": image_path}), 201

# Spielerpool löschen
@app.route('/remove_from_pool', methods=['POST'])
def remove_from_pool():
    player_id = request.json.get('id')

    if not player_id:
        return jsonify({"error": "Player ID is required"}), 400

    with get_db_connection() as conn:
        result = conn.execute("DELETE FROM playerpool WHERE id = ?", (player_id,))
        conn.commit()

        if result.rowcount == 0:
            return jsonify({"error": "Player not found in pool"}), 404

    return jsonify({"message": "Player removed from pool"}), 200

# Spieler abrufen
@app.route('/players', methods=['GET'])
def get_players():
    with get_db_connection() as conn:
        players = conn.execute("SELECT * FROM players").fetchall()
    return jsonify([{"id": row["id"], "name": row["name"], "image": row["image"], "role": row["role"]} for row in players])

# Spieler zum aktiven Spiel hinzufügen
@app.route('/add_to_players', methods=['POST'])
def add_to_players():
    player_id = request.json.get('id')

    if not player_id:
        return jsonify({"error": "Player ID is required"}), 400

    with get_db_connection() as conn:
        player = conn.execute("SELECT * FROM playerpool WHERE id = ?", (player_id,)).fetchone()
        if not player:
            return jsonify({"error": "Player not found in pool"}), 404

        conn.execute("INSERT INTO players (name, image) VALUES (?, ?)", (player["name"], player["image"]))
        conn.commit()

    return jsonify({"message": "Player added to game"}), 201

# Spieler aus dem aktiven Spiel entfernen
@app.route('/remove_from_players', methods=['POST'])
def remove_from_players():
    player_id = request.json.get('id')

    if not player_id:
        return jsonify({"error": "Player ID is required"}), 400

    with get_db_connection() as conn:
        result = conn.execute("DELETE FROM players WHERE id = ?", (player_id,))
        conn.commit()

        if result.rowcount == 0:
            return jsonify({"error": "Player not found in game"}), 404

    return jsonify({"message": "Player removed from game"}), 200

# Rollen-Auswahlseite
@app.route('/select_roles', methods=['GET'])
def select_roles():
    return render_template('roles.html')

# Rollen speichern
@app.route('/save_roles', methods=['POST'])
def save_roles():
    try:
        data = request.json
        roles = data.get('roles', [])
        if not roles:
            return jsonify({"error": "Keine Rollen ausgewählt"}), 400

        with get_db_connection() as conn:
            conn.execute("DELETE FROM game_roles")  # Bestehende Rollen löschen

            # Dictionary zur Verfolgung der Häufigkeit bestimmter Rollen
            role_instances = []
            role_count_map = {}

            for role in roles:
                if role not in role_count_map:
                    role_count_map[role] = 0

                if role == "Die Zwei Schwestern":
                    if role_count_map[role] == 0:  # Nur beim ersten Durchlauf hinzufügen
                        role_instances.append((role, 1))
                        role_instances.append((role, 2))
                        role_count_map[role] += 2
                elif role == "Die Drei Brüder":
                    if role_count_map[role] == 0:  # Nur beim ersten Durchlauf hinzufügen
                        role_instances.append((role, 1))
                        role_instances.append((role, 2))
                        role_instances.append((role, 3))
                        role_count_map[role] += 3
                else:
                    # Für alle anderen Rollen normale Verarbeitung
                    role_count_map[role] += 1
                    role_instances.append((role, role_count_map[role]))

            # Einfügen in die Datenbank
            conn.executemany(
                "INSERT INTO game_roles (role_name, instance_id) VALUES (?, ?)",
                role_instances
            )
            conn.commit()

        return jsonify({"message": "Rollen erfolgreich gespeichert"}), 200
    except Exception as e:
        print(f"Fehler beim Speichern der Rollen: {e}")
        return jsonify({"error": "Fehler beim Speichern der Rollen"}), 500



# Rollenübersicht abrufen
@app.route('/get_selected_roles', methods=['GET'])
def get_selected_roles():
    try:
        with get_db_connection() as conn:
            roles = conn.execute("SELECT role_name, instance_id FROM game_roles").fetchall()
        return jsonify([{"role_name": row["role_name"], "instance_id": row["instance_id"]} for row in roles])
    except Exception as e:
        print(f"Fehler beim Abrufen der Rollen: {e}")
        return jsonify({"error": "Fehler beim Abrufen der Rollen"}), 500

@app.route('/player_count', methods=['GET'])
def player_count():
    try:
        with get_db_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
        return jsonify({"count": count}), 200
    except Exception as e:
        return jsonify({"error": "Fehler beim Abrufen der Spieleranzahl"}), 500


# Spielübersichtsseite
@app.route('/gameoverview', methods=['GET'])
def gameoverview():
    return render_template('gameoverview.html')

if __name__ == '__main__':
    init_db()  # Datenbank initialisieren
    app.run(debug=True)
