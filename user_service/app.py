# user_service/app.py
import sqlite3
import os
import contextlib
from flask import Flask, request, jsonify

# --- Inisialisasi Aplikasi Flask ---
app = Flask(__name__)
# Explain: Mendefinisikan nama file database KHUSUS untuk layanan pengguna.
DB_NAME = "user_data.db"
# Explain: Membuat path lengkap ke file database di dalam direktori layanan ini.
DB_PATH = os.path.join(os.path.dirname(__file__), DB_NAME)

# --- Utilitas Database ---
@contextlib.contextmanager
def get_db_connection():
    # Explain: Menghubungkan ke file database spesifik 'user_data.db'.
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Inisialisasi database pengguna (user_data.db) jika belum ada."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Explain: Membuat tabel 'users' jika belum ada.
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE
                )
            ''')
            conn.commit()
        # Explain: Pesan konfirmasi mencantumkan nama DB yang benar.
        print(f"Provider Pengguna: Database '{DB_NAME}' diinisialisasi.")
    except Exception as e:
        print(f"Provider Pengguna: Gagal inisialisasi DB '{DB_NAME}' - {e}")
        raise

# --- API Endpoints ---

# Endpoint: POST /users
@app.route('/users', methods=['POST'])
def create_user():
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    if not name or not email:
        return jsonify({"error": "Nama dan email diperlukan"}), 400

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (name, email) VALUES (?, ?)", (name, email))
            conn.commit()
            user_id = cursor.lastrowid
        return jsonify({'id': user_id, 'name': name, 'email': email}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Email sudah ada'}), 409
    except Exception as e:
        app.logger.error(f"Error creating user: {e}")
        return jsonify({'error': 'Kesalahan server internal'}), 500

# Endpoint: GET /users/<int:user_id>
@app.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, email FROM users WHERE id = ?", (user_id,))
            user = cursor.fetchone()
        if user:
            return jsonify(dict(user)), 200
        else:
            return jsonify({'error': 'Pengguna tidak ditemukan'}), 404
    except Exception as e:
        app.logger.error(f"Error fetching user {user_id}: {e}")
        return jsonify({'error': 'Kesalahan server internal'}), 500

# --- Menjalankan Aplikasi ---
if __name__ == '__main__':
    init_db() # Inisialisasi DB saat start
    # Explain: host='0.0.0.0' agar bisa diakses dari layanan lain di mesin yang sama.
    #          Port 5001 untuk layanan pengguna.
    app.run(host='0.0.0.0', port=5001, debug=True)