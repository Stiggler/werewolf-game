from flask import Flask, jsonify, request, render_template, redirect, url_for
import os
import sqlite3
import json

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
                status TEXT                       
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
        # Thief cards Tabelle
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS thief_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_name TEXT NOT NULL
            )
        """)
        # Game state Tabelle
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS game_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                player_id INTEGER,
                role_id INTEGER,
                attribute_name TEXT NOT NULL,
                value TEXT,
                FOREIGN KEY (player_id) REFERENCES players (id),
                FOREIGN KEY (role_id) REFERENCES game_roles (id)
            )
        """)
                # Rollen aus JSON
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS base_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_name TEXT NOT NULL UNIQUE,
                first_night INTEGER,
                night_order INTEGER,
                description TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS role_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                role_name TEXT NOT NULL,
                player_id INTEGER NOT NULL,
                target_id INTEGER,
                action_name TEXT NOT NULL,
                result TEXT,
                new_role TEXT,
                player_status TEXT DEFAULT 'lebendig',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (player_id) REFERENCES players (id),
                FOREIGN KEY (target_id) REFERENCES players (id)
            )
        """)
        # Spalte `in_love` hinzufügen, falls sie fehlt
        try:
            cursor.execute("ALTER TABLE players ADD COLUMN in_love BOOLEAN DEFAULT FALSE")
        except sqlite3.OperationalError:
            print("Spalte `in_love` existiert bereits.")

    print("Datenbank initialisiert.")



# Verbindung zur Datenbank abrufen
def get_db_connection():
    conn = sqlite3.connect("players.db")
    conn.row_factory = sqlite3.Row  # Ermöglicht den Zugriff auf Spaltennamen
    return conn


def clear_role_actions():
    """Löscht alle Einträge aus der Tabelle role_actions."""
    with get_db_connection() as conn:
        conn.execute("DELETE FROM role_actions")
        conn.commit()
    print("Tabelle role_actions wurde geleert.")

def reset_player_status():
    """Setzt den Status aller Spieler auf lebendig."""
    with get_db_connection() as conn:
        conn.execute("UPDATE players SET status = 'lebendig'")
        conn.commit()
    print("Spielerstatus wurde zurückgesetzt.")


def update_player_status(player_id, new_status):
    """Aktualisiert den Status eines Spielers."""
    with get_db_connection() as conn:
        conn.execute("""
            UPDATE players
            SET status = ?
            WHERE id = ?
        """, (new_status, player_id))
        conn.commit()
    print(f"Status von Spieler {player_id} auf {new_status} gesetzt.")



# Rollen sortieren nach 'first_night'
def get_sorted_roles():
    """Holt die Rollen aus der JSON-Datei und sortiert sie basierend auf 'first_night'."""
    with open("static/rollen/roles.json", "r", encoding="utf-8") as file:
        roles_data = json.load(file)

    # Sortieren basierend auf 'first_night', Rollen ohne 'first_night' ans Ende
    sorted_roles = sorted(roles_data, key=lambda x: x.get("first_night", float("inf")))
    return sorted_roles

# Spieler und Rollen kombinieren
def get_players_with_roles():
    """Holt Spieler aus der Datenbank und ergänzt Attribute wie 'in_love'."""
    with get_db_connection() as conn:
        players = conn.execute("""
            SELECT 
                p.id, 
                p.name, 
                p.image, 
                p.role AS current_role, 
                p.status, 
                p.in_love,  -- Spalte 'in_love' hinzufügen
                (SELECT role_name FROM role_actions WHERE player_id = p.id ORDER BY timestamp ASC LIMIT 1) AS original_role
            FROM players p
        """).fetchall()

    return [
        {
            "id": player["id"],
            "name": player["name"],
            "image": player["image"],
            "current_role": player["current_role"],
            "status": player["status"],
            "in_love": player["in_love"],  # Attribut 'in_love' hinzufügen
            "original_role": player["original_role"],
            "original_role_image": f"/static/rollen/{player['original_role'].lower().replace(' ', '_')}.png" if player["original_role"] else None
        }
        for player in players
    ]









    # Spieler nach der Rollenreihenfolge sortieren
    detailed_players.sort(key=lambda x: x["first_night"])
    return detailed_players

# Rollenaktionen speichern
def save_role_action(game_id, role_name, player_id, target_id, action_name, result, new_role=None, player_status=None):
    """Speichert die Aktion einer Rolle sowie den Status des Spielers in der Tabelle role_actions."""
    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO role_actions (game_id, role_name, player_id, target_id, action_name, result, new_role, player_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (game_id, role_name, player_id, target_id, action_name, result, new_role, player_status))
        conn.commit()

# Spielattribute speichern
def save_game_attribute(game_id, attribute_name, value, player_id=None, role_id=None):
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO game_state (game_id, player_id, role_id, attribute_name, value)
            VALUES (?, ?, ?, ?, ?)
            """,
            (game_id, player_id, role_id, attribute_name, value)
        )
        conn.commit()

# Spielattribute abrufen
def get_game_attribute(game_id, attribute_name):
    with get_db_connection() as conn:
        result = conn.execute(
            """
            SELECT value FROM game_state
            WHERE game_id = ? AND attribute_name = ?
            """,
            (game_id, attribute_name)
        ).fetchone()
        return result["value"] if result else None




def sync_base_roles():
    """Synchronisiert die Rollen aus der JSON-Datei mit der Tabelle base_roles."""
    with sqlite3.connect("players.db") as conn:
        cursor = conn.cursor()
        
        # Erstelle die Tabelle, falls sie nicht existiert
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS base_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_name TEXT NOT NULL UNIQUE,
                first_night INTEGER,
                night_order INTEGER,
                description TEXT
            )
        """)
        
        # Rollen aus der JSON-Datei laden
        with open("static/rollen/roles.json", "r", encoding="utf-8") as file:
            roles_data = json.load(file)

        # Synchronisation: Einfügen oder Aktualisieren
        for role in roles_data:
            cursor.execute("""
                INSERT INTO base_roles (role_name, first_night, night_order, description)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(role_name) DO UPDATE SET
                first_night = excluded.first_night,
                night_order = excluded.night_order,
                description = excluded.description
            """, (
                role["Rolle"],
                role.get("first_night"),
                role.get("night_order"),
                role.get("Beschreibung")
            ))
        conn.commit()
        print("Basisrollen erfolgreich synchronisiert!")


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
    players = get_players_with_roles()
    print("Abgerufene Spieler-Daten:", players)  # Debugging-Ausgabe
    return jsonify(players)


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
            conn.execute("DELETE FROM game_roles")

            # Generiere die role_instances mit den richtigen Logiken
            role_instances = []
            instance_id = 1
            processed_roles = []

            for role in roles:
                if role == "Die Zwei Schwestern" and role not in processed_roles:
                    # Füge "Die Zwei Schwestern" zweimal hinzu
                    role_instances.append((role, instance_id))
                    instance_id += 1
                    role_instances.append((role, instance_id))
                    instance_id += 1
                    processed_roles.append(role)
                elif role == "Die Drei Brüder" and role not in processed_roles:
                    # Füge "Die Drei Brüder" dreimal hinzu
                    role_instances.append((role, instance_id))
                    instance_id += 1
                    role_instances.append((role, instance_id))
                    instance_id += 1
                    role_instances.append((role, instance_id))
                    instance_id += 1
                    processed_roles.append(role)
                elif role not in ["Die Zwei Schwestern", "Die Drei Brüder"]:
                    # Füge alle anderen Rollen einmal hinzu
                    role_instances.append((role, instance_id))
                    instance_id += 1

            # Speichere die Rollen in der Datenbank
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
    with get_db_connection() as conn:
        roles = conn.execute("""
            SELECT role_name, COUNT(instance_id) as count
            FROM game_roles
            GROUP BY role_name
        """).fetchall()
        players = conn.execute("SELECT * FROM players").fetchall()

    return render_template('gameoverview.html', roles=roles, players=players)


@app.route('/random_assign_roles', methods=['POST'])
def random_assign_roles():
    try:
        with get_db_connection() as conn:
            # Spieler und Rollen abrufen
            players = conn.execute("SELECT id FROM players").fetchall()
            roles = conn.execute("SELECT role_name, instance_id FROM game_roles").fetchall()

            # Tabelle thief_cards leeren
            conn.execute("DELETE FROM thief_cards")

            # Diebeskarten extrahieren
            import random
            random.shuffle(roles)
            thief_cards = roles[:2]
            remaining_roles = roles[2:]

            # Diebeskarten speichern
            conn.executemany(
                "INSERT INTO thief_cards (role_name) VALUES (?)",
                [(card['role_name'],) for card in thief_cards]
            )

            # Rollen zufällig Spielern zuweisen
            random.shuffle(players)
            assignments = []
            for player, role in zip(players, remaining_roles):
                assignments.append((role['role_name'], player['id']))

            conn.executemany(
                "UPDATE players SET role = ? WHERE id = ?",
                assignments
            )
            conn.commit()

        # JSON-Antwort mit Redirect-Ziel
        return jsonify({"message": "Rollen erfolgreich zugewiesen", "redirect": url_for('game')}), 200
    except Exception as e:
        print(f"Fehler bei der zufälligen Rollenverteilung: {e}")
        return jsonify({"error": "Fehler bei der zufälligen Rollenverteilung"}), 500



@app.route('/get_thief_cards', methods=['GET'])
def get_thief_cards():
    """Gibt die verfügbaren Diebeskarten zurück."""
    with get_db_connection() as conn:
        thief_cards = conn.execute("""
            SELECT role_name FROM thief_cards
        """).fetchall()
    
    # Füge Bildpfade hinzu
    cards_with_images = [
        {
            "role_name": card["role_name"],
            "image_path": f"/static/rollen/{card['role_name'].lower().replace(' ', '_')}.png"
        }
        for card in thief_cards
    ]
    return jsonify({"cards": cards_with_images})


@app.route('/manual_start', methods=['POST'])
def manual_start():
    return jsonify({"message": "Manueller Startmodus ist noch nicht implementiert"})

@app.route('/game', methods=['GET'])
def game():
    try:
        with get_db_connection() as conn:
            # Spieler mit ihren Rollen abrufen
            players = conn.execute("SELECT name, image, role FROM players").fetchall()
            
            # Prüfen, ob die Rolle "Dieb" in game_roles existiert
            dieb_exists = conn.execute(
                "SELECT 1 FROM game_roles WHERE role_name = 'Dieb' LIMIT 1"
            ).fetchone() is not None

            # Verfügbare Diebeskarten nur abrufen, wenn "Dieb" existiert
            thief_cards = []
            if dieb_exists:
                thief_cards = conn.execute("SELECT role_name FROM thief_cards").fetchall()

        return render_template(
            'game.html',
            players=[{"name": p["name"], "image": p["image"], "role": p["role"]} for p in players],
            thief_cards=[{"role_name": t["role_name"]} for t in thief_cards] if dieb_exists else None
        )
    except Exception as e:
        print(f"Fehler in der /game-Route: {e}")
        return "Ein Fehler ist aufgetreten.", 500


@app.route('/start_game', methods=['POST'])
def start_game():
    """Initialisiert das Spiel, setzt alle relevanten Spalten zurück."""
    with get_db_connection() as conn:
        # Tabelle role_actions leeren
        conn.execute("DELETE FROM role_actions")

        # Spielerstatus und Verliebtheitsstatus zurücksetzen
        conn.execute("UPDATE players SET status = 'lebendig', in_love = FALSE")

        conn.commit()

    return jsonify({"message": "Spiel gestartet und Aktionen zurückgesetzt"})







# Route für die erste Nacht

@app.route('/night1')
def night1():
    """Zeigt die Übersicht der Spieler und Rollen für die erste Nacht."""
    players = get_players_with_roles()
    with get_db_connection() as conn:
        thief_player = conn.execute("""
            SELECT id FROM players WHERE role = 'Dieb' LIMIT 1
        """).fetchone()
        thief_player_id = thief_player["id"] if thief_player else None
    return render_template('night1.html', players=players, thief_player_id=thief_player_id or 'null')



@app.route('/next_role', methods=['GET'])
def get_next_role():
    with get_db_connection() as conn:
        # Abrufen der Rollen aus `game_roles` mit den zugehörigen Daten aus `base_roles`
        roles = conn.execute("""
            SELECT gr.role_name, br.first_night
            FROM game_roles gr
            INNER JOIN base_roles br ON gr.role_name = br.role_name
            WHERE br.first_night IS NOT NULL
            ORDER BY br.first_night ASC
        """).fetchall()

    # JSON-Ausgabe der Rollen mit `role_name` und `first_night`
    return jsonify([{"role_name": role["role_name"], "first_night": role["first_night"]} for role in roles])


# Rollenaktionen setzen
@app.route('/set_role_action', methods=['POST'])
def set_role_action():
    data = request.json
    game_id = data.get('game_id')
    role_name = data.get('role_name')
    player_id = data.get('player_id')
    action_name = data.get('action_name')
    new_role = data.get('new_role')

    if not game_id or not role_name or not player_id or not new_role:
        return jsonify({"error": "Fehlende Daten"}), 400

    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO role_actions (game_id, role_name, player_id, action_name, new_role)
            VALUES (?, ?, ?, ?, ?)
        """, (game_id, role_name, player_id, action_name, new_role))

        conn.execute("""
            UPDATE players SET role = ? WHERE id = ?
        """, (new_role, player_id))

        conn.commit()  # Änderungen speichern

    return jsonify({"message": "Aktion erfolgreich gespeichert"}), 200





# Synchronisiere Basisrollen mit JSON
def sync_base_roles():
    """Synchronisiert die Rollen aus der JSON-Datei mit der Tabelle base_roles."""
    with sqlite3.connect("players.db") as conn:
        cursor = conn.cursor()

        # Rollen aus der JSON-Datei laden
        with open("static/rollen/roles.json", "r", encoding="utf-8") as file:
            roles_data = json.load(file)

        # Synchronisation: Einfügen oder Aktualisieren
        for role in roles_data:
            cursor.execute("""
                INSERT INTO base_roles (role_name, first_night, night_order, description)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(role_name) DO UPDATE SET
                first_night = excluded.first_night,
                night_order = excluded.night_order,
                description = excluded.description
            """, (
                role["Rolle"],
                role.get("first_night"),
                role.get("night_order"),
                role.get("Beschreibung")
            ))
        conn.commit()
        print("Basisrollen erfolgreich synchronisiert!")


@app.route('/kill_player', methods=['POST'])
def kill_player():
    """Ändert den Status eines Spielers auf 'tot'."""
    data = request.json
    player_id = data.get('player_id')

    if not player_id:
        return jsonify({"error": "Spieler-ID fehlt"}), 400

    with get_db_connection() as conn:
        conn.execute("""
            UPDATE players SET status = 'tot' WHERE id = ?
        """, (player_id,))
        conn.commit()

    return jsonify({"message": f"Spieler {player_id} wurde getötet."}), 200

@app.route('/amor_action', methods=['POST'])
def amor_action():
    """Markiert zwei Spieler als verliebt."""
    data = request.json
    lover1_id = data.get('lover1_id')
    lover2_id = data.get('lover2_id')

    if not lover1_id or not lover2_id:
        return jsonify({"error": "Spieler-IDs fehlen"}), 400

    with get_db_connection() as conn:
        conn.execute("UPDATE players SET in_love = TRUE WHERE id IN (?, ?)", (lover1_id, lover2_id))
        conn.commit()

    return jsonify({"message": "Die Spieler sind nun verliebt!"}), 200



if __name__ == '__main__':
    init_db()  # Datenbank initialisieren
    sync_base_roles()  # Basisrollen synchronisieren
    app.run(debug=True)

