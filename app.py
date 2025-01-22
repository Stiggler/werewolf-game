from flask import Flask, jsonify, request, session, render_template
from game import get_sorted_game_roles, get_players, assign_role, initialize_game


import os
import sqlite3

app = Flask(__name__, template_folder='templates')

# Initialisiere die Datenbank
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
        
        # Tabelle game_roles hinzufügen
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS game_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_name TEXT NOT NULL,
                instance_id INTEGER NOT NULL
            )
        """)

        # Optional: Debugging-Nachricht
        print("Tabelle 'game_roles' erstellt oder existiert bereits.")

    print("Database initialized!")


# Verbindung zur Datenbank abrufen
def get_db_connection():
    conn = sqlite3.connect("players.db")
    conn.row_factory = sqlite3.Row
    return conn

# Dummy-Spielerliste
players = []

# Route: Startseite
@app.route('/')
def home():
    return render_template('index.html')

# Route: Spielerliste abrufen
@app.route('/players', methods=['GET'])
def get_players():
    with get_db_connection() as conn:
        players = conn.execute("SELECT * FROM players").fetchall()
    return jsonify([{"id": row["id"], "name": row["name"], "image": row["image"]} for row in players])



# Route: Spieler zum pool hinzufügen
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




# Route: Bild hochladen
@app.route('/upload_image', methods=['POST'])
def upload_image():
    name = request.form.get('name')
    image = request.files.get('image')
    if not name or not image:
        return jsonify({"error": "Name and image are required"}), 400

    os.makedirs('static', exist_ok=True)
    image_path = f"static/{name}.png"
    image.save(image_path)

    with get_db_connection() as conn:
        result = conn.execute("UPDATE players SET image = ? WHERE name = ?", (image_path, name))
        conn.commit()

        if result.rowcount == 0:
            return jsonify({"error": "Player not found"}), 404

    return jsonify({"message": "Image uploaded successfully", "image": image_path}), 200

@app.route('/playerpool', methods=['GET'])
def get_playerpool():
    with get_db_connection() as conn:
        players = conn.execute("SELECT * FROM playerpool").fetchall()
    return jsonify([{"id": row["id"], "name": row["name"], "image": row["image"]} for row in players])







@app.route('/add_to_players', methods=['POST'])
def add_to_players():
    player_id = request.json.get('id')  # Spieler-ID aus dem Frontend

    if not player_id:
        return jsonify({"error": "Player ID is required"}), 400

    try:
        with get_db_connection() as conn:
            # Spieler aus dem Playerpool abrufen
            player = conn.execute("SELECT * FROM playerpool WHERE id = ?", (player_id,)).fetchone()
            if not player:
                return jsonify({"error": "Player not found in pool"}), 404

            # Spieler zur Players-Tabelle hinzufügen
            conn.execute("INSERT INTO players (name, image) VALUES (?, ?)", (player["name"], player["image"]))
            conn.commit()

        return jsonify({"message": "Player added to game"}), 201
    except Exception as e:
        print(f"Error adding player to players: {str(e)}")
        return jsonify({"error": str(e)}), 500



@app.route('/remove_from_players', methods=['POST'])
def remove_from_players():
    data = request.json
    player_id = data.get('id')
    if not player_id:
        return jsonify({"error": "Player ID is required"}), 400

    try:
        with get_db_connection() as conn:
            result = conn.execute("DELETE FROM players WHERE id = ?", (player_id,))
            conn.commit()

            if result.rowcount == 0:
                return jsonify({"error": "Player not found in active list"}), 404

        return jsonify({"message": "Player removed from game"}), 200
    except Exception as e:
        print(f"Error removing player: {str(e)}")  # Debugging
        return jsonify({"error": str(e)}), 500

#Route, um Spieler aus dem playerpool zu löschen
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

@app.route('/player_count', methods=['GET'])
def player_count():
    try:
        with get_db_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]  # Spieleranzahl aus DB
        return jsonify({"count": count}), 200
    except Exception as e:
        print(f"Fehler beim Abrufen der Spieleranzahl: {e}")
        return jsonify({"error": "Fehler beim Abrufen der Spieleranzahl"}), 500



# Route: Rollen-Auswahlseite
@app.route('/select_roles')
def select_roles():
    return render_template('roles.html')

@app.route('/save_roles', methods=['POST'])
def save_roles():
    try:
        data = request.json
        roles = data.get('roles', [])
        if not roles:
            return jsonify({"error": "Keine Rollen ausgewählt"}), 400

        with get_db_connection() as conn:
            conn.execute("DELETE FROM game_roles")
            # Für Rollen mit Mehrfachvorkommen Instanz-IDs generieren
            role_instances = []
            for role in roles:
                count = roles.count(role)
                for i in range(1, count + 1):
                    role_instances.append((role, i))  # Rolle und Instanz-ID

            conn.executemany(
                "INSERT INTO game_roles (role_name, instance_id) VALUES (?, ?)",
                role_instances
            )
            conn.commit()
        return jsonify({"message": "Rollen erfolgreich gespeichert"}), 200
    except Exception as e:
        print(f"Fehler beim Speichern der Rollen: {e}")
        return jsonify({"error": "Fehler beim Speichern der Rollen"}), 500




@app.route('/load_roles', methods=['GET'])
def load_roles():
    try:
        roles = session.get('selected_roles', [])
        return jsonify({"roles": roles}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/save_selected_roles', methods=['POST'])
def save_selected_roles():
    try:
        data = request.json
        selected_roles = data.get('roles', [])
        if not selected_roles:
            return jsonify({"error": "Keine Rollen ausgewählt"}), 400
        
        with get_db_connection() as conn:
            # Alte Rollen löschen
            conn.execute("DELETE FROM game_roles")
            # Neue Rollen speichern
            conn.executemany("INSERT INTO game_roles (role_name) VALUES (?)", [(role,) for role in selected_roles])
            conn.commit()
        return jsonify({"message": "Rollen erfolgreich gespeichert"}), 200
    except Exception as e:
        print(f"Fehler beim Speichern der Rollen: {e}")
        return jsonify({"error": "Fehler beim Speichern der Rollen"}), 500


@app.route('/get_selected_roles', methods=['GET'])
def get_selected_roles():
    try:
        with get_db_connection() as conn:
            roles = conn.execute("SELECT role_name FROM game_roles").fetchall()
        return jsonify([{"role_name": row["role_name"]} for row in roles])
    except Exception as e:
        print(f"Fehler beim Abrufen der Rollen: {e}")
        return jsonify({"error": "Fehler beim Abrufen der Rollen"}), 500

@app.route('/gameoverview', methods=['GET'])
def gameoverview():
    return render_template('gameoverview.html')

@app.route('/reset_roles', methods=['POST'])
def reset_roles():
    try:
        with get_db_connection() as conn:
            conn.execute("UPDATE players SET role = NULL")
            conn.commit()
        return jsonify({"message": "Alle Rollen wurden zurückgesetzt."}), 200
    except Exception as e:
        print(f"Fehler beim Zurücksetzen der Rollen: {e}")
        return jsonify({"error": "Fehler beim Zurücksetzen der Rollen"}), 500












@app.route('/assign_role', methods=['POST'])
def api_assign_role():
    from game import assign_role
    return assign_role()







@app.route('/initialize_game', methods=['POST'])
def api_initialize_game():
    return jsonify(initialize_game())



if __name__ == '__main__':
    init_db()  # Datenbank initialisieren
    app.run(debug=True)
