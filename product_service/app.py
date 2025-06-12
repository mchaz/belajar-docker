# product_service/app.py
import sqlite3
import os
import contextlib
from flask import Flask, request, jsonify

# --- Inisialisasi Aplikasi Flask ---
app = Flask(__name__)
# Explain: Mendefinisikan nama file database KHUSUS untuk layanan produk.
DB_NAME = "product_data.db"
# Explain: Membuat path lengkap ke file database di dalam direktori layanan ini.
DB_PATH = os.path.join(os.path.dirname(__file__), DB_NAME)

# --- Utilitas Database ---
@contextlib.contextmanager
def get_db_connection():
    # Explain: Menghubungkan ke file database spesifik 'product_data.db'.
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Inisialisasi database produk (product_data.db) jika belum ada."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Explain: Membuat tabel 'products' dengan constraint harga >= 0.
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    price REAL NOT NULL CHECK(price >= 0)
                )
            ''')
            conn.commit()
        # Explain: Pesan konfirmasi mencantumkan nama DB yang benar.
        print(f"Provider Produk: Database '{DB_NAME}' diinisialisasi.")
    except Exception as e:
        print(f"Provider Produk: Gagal inisialisasi DB '{DB_NAME}' - {e}")
        raise

# --- API Endpoints ---

# Endpoint: POST /products
@app.route('/products', methods=['POST'])
def create_product():
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
    data = request.get_json()
    name = data.get('name')
    price = data.get('price')
    if name is None or price is None:
        return jsonify({"error": "Nama dan harga diperlukan"}), 400
    if not isinstance(price, (int, float)) or price < 0:
        return jsonify({"error": "Harga harus berupa angka non-negatif"}), 400

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO products (name, price) VALUES (?, ?)", (name, price))
            conn.commit()
            product_id = cursor.lastrowid
        return jsonify({'id': product_id, 'name': name, 'price': price}), 201
    except Exception as e:
        app.logger.error(f"Error creating product: {e}")
        return jsonify({'error': f'Kesalahan server internal: {str(e)}'}), 500

# Endpoint: GET /products/<int:product_id>
@app.route('/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, price FROM products WHERE id = ?", (product_id,))
            product = cursor.fetchone()
        if product:
            return jsonify(dict(product)), 200
        else:
            return jsonify({'error': 'Produk tidak ditemukan'}), 404
    except Exception as e:
        app.logger.error(f"Error fetching product {product_id}: {e}")
        return jsonify({'error': 'Kesalahan server internal'}), 500

# --- Menjalankan Aplikasi ---
if __name__ == '__main__':
    init_db() # Inisialisasi DB saat start
    # Explain: Port 5002 untuk layanan produk.
    app.run(host='0.0.0.0', port=5002, debug=True)