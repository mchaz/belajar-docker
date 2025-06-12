# order_service/app.py
import sqlite3
import os
import contextlib
import requests # Library untuk membuat HTTP requests
from flask import Flask, request, jsonify

# --- Inisialisasi Aplikasi Flask ---
app = Flask(__name__)
# Explain: Mendefinisikan nama file database KHUSUS untuk layanan pesanan.
DB_NAME = "order_data.db"
# Explain: Membuat path lengkap ke file database di dalam direktori layanan ini.
DB_PATH = os.path.join(os.path.dirname(__file__), DB_NAME)

# --- Konfigurasi URL Provider ---
# Explain: URL tempat layanan User dan Product berjalan.
USER_PROVIDER_URL = os.getenv("USER_PROVIDER_URL", "http://localhost:5001")
PRODUCT_PROVIDER_URL = os.getenv("PRODUCT_PROVIDER_URL", "http://localhost:5002")

# --- Utilitas Database ---
@contextlib.contextmanager
def get_db_connection():
    # Explain: Menghubungkan ke file database spesifik 'order_data.db'.
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Inisialisasi database pesanan (order_data.db) jika belum ada."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Explain: Membuat tabel 'orders' dengan constraint kuantitas > 0.
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    quantity INTEGER NOT NULL CHECK(quantity > 0),
                    total_price REAL NOT NULL,
                    status TEXT DEFAULT 'PENDING'
                )
            ''')
            conn.commit()
        # Explain: Pesan konfirmasi mencantumkan nama DB yang benar.
        print(f"Consumer Pesanan: Database '{DB_NAME}' diinisialisasi.")
    except Exception as e:
        print(f"Consumer Pesanan: Gagal inisialisasi DB '{DB_NAME}' - {e}")
        raise



# --- Fungsi Helper untuk Mengambil Detail dari Provider ---
# Explain: Fungsi ini mirip validate_user, tapi tujuannya mengambil detail
#          lengkap user jika tersedia saat melihat detail order.
def fetch_user_details(user_id):
    """Mengambil detail pengguna dari User Provider."""
    url = f"{USER_PROVIDER_URL}/users/{user_id}"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json() # Kembalikan data user jika sukses
    except requests.exceptions.RequestException as e:
        # Log error tapi jangan gagalkan seluruh request detail order
        status_code = e.response.status_code if hasattr(e, 'response') and e.response is not None else "N/A"
        app.logger.warning(f"Gagal mengambil detail user {user_id} dari {url}. Status: {status_code}. Error: {e}")
        return None # Kembalikan None jika gagal mengambil detail

# Explain: Fungsi ini mirip validate_product, tapi tujuannya mengambil detail
#          lengkap produk jika tersedia saat melihat detail order.
def fetch_product_details(product_id):
    """Mengambil detail produk dari Product Provider."""
    url = f"{PRODUCT_PROVIDER_URL}/products/{product_id}"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json() # Kembalikan data produk jika sukses
    except requests.exceptions.RequestException as e:
        status_code = e.response.status_code if hasattr(e, 'response') and e.response is not None else "N/A"
        app.logger.warning(f"Gagal mengambil detail produk {product_id} dari {url}. Status: {status_code}. Error: {e}")
        return None # Kembalikan None jika gagal mengambil detail

# --- Fungsi Validasi ke Provider ---
# Explain: Fungsi ini memanggil User Provider untuk memeriksa apakah user_id valid.
def validate_user(user_id):
    url = f"{USER_PROVIDER_URL}/users/{user_id}"
    try:
        response = requests.get(url, timeout=5) # Timeout 5 detik
        response.raise_for_status() # Error jika status 4xx atau 5xx
        return response.json(), None # Sukses: kembalikan data user, error = None
    except requests.exceptions.Timeout:
        msg = f"Timeout saat menghubungi User Provider di {url}"
        app.logger.error(msg)
        return None, "Timeout provider pengguna"
    except requests.exceptions.ConnectionError:
        msg = f"Tidak dapat terhubung ke User Provider di {url}"
        app.logger.error(msg)
        return None, "Provider pengguna tidak tersedia"
    except requests.exceptions.RequestException as e:
        status = e.response.status_code if e.response is not None else 503
        detail = "Pengguna tidak ditemukan" if status == 404 else f"Error dari User Provider: {status}"
        app.logger.error(f"Error validasi user {user_id} di {url}: {detail} - {e}")
        return None, detail

# Explain: Fungsi ini memanggil Product Provider untuk memeriksa product_id dan mendapatkan harga.
def validate_product(product_id):
    url = f"{PRODUCT_PROVIDER_URL}/products/{product_id}"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        product_data = response.json()
        if 'price' not in product_data or not isinstance(product_data['price'], (int, float)):
             app.logger.error(f"Respons produk tidak valid dari {url}: {product_data}")
             return None, "Respons produk tidak valid (harga hilang/salah tipe)"
        return product_data, None # Sukses: kembalikan data produk, error = None
    except requests.exceptions.Timeout:
        msg = f"Timeout saat menghubungi Product Provider di {url}"
        app.logger.error(msg)
        return None, "Timeout provider produk"
    except requests.exceptions.ConnectionError:
        msg = f"Tidak dapat terhubung ke Product Provider di {url}"
        app.logger.error(msg)
        return None, "Provider produk tidak tersedia"
    except requests.exceptions.RequestException as e:
        status = e.response.status_code if e.response is not None else 503
        detail = "Produk tidak ditemukan" if status == 404 else f"Error dari Product Provider: {status}"
        app.logger.error(f"Error validasi produk {product_id} di {url}: {detail} - {e}")
        return None, detail

# --- API Endpoint ---

# Endpoint: POST /orders
@app.route('/orders', methods=['POST'])
def create_order():
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
    data = request.get_json()
    user_id = data.get('user_id')
    product_id = data.get('product_id')
    quantity = data.get('quantity')

    if not all([user_id, product_id, quantity]):
        return jsonify({'error': 'user_id, product_id, dan quantity diperlukan'}), 400
    if not isinstance(quantity, int) or quantity <= 0:
        return jsonify({'error': 'Quantity harus berupa bilangan bulat positif'}), 400

    # Explain: Langkah 1 - Panggil User Provider untuk validasi.
    user_data, user_error = validate_user(user_id)
    if user_data is None:
        status_code = 404 if "tidak ditemukan" in user_error else 503
        return jsonify({'error': f'Validasi pengguna gagal: {user_error}'}), status_code

    # Explain: Langkah 2 - Panggil Product Provider untuk validasi.
    product_data, product_error = validate_product(product_id)
    if product_data is None:
        status_code = 404 if "tidak ditemukan" in product_error else (500 if "tidak valid" in product_error else 503)
        return jsonify({'error': f'Validasi produk gagal: {product_error}'}), status_code

    # Explain: Langkah 3 - Hitung total harga jika validasi berhasil.
    total_price = product_data['price'] * quantity

    # Explain: Langkah 4 - Simpan pesanan ke database 'order_data.db'.
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO orders (user_id, product_id, quantity, total_price, status) VALUES (?, ?, ?, ?, ?)",
                (user_id, product_id, quantity, total_price, 'SELESAI') # Status SELESAI setelah valid
            )
            conn.commit()
            order_id = cursor.lastrowid
        return jsonify({
            'id': order_id, 'user_id': user_id, 'product_id': product_id,
            'quantity': quantity, 'total_price': total_price, 'status': 'SELESAI'
        }), 201
    except Exception as e:
        app.logger.error(f"Error saving order: {e}")
        return jsonify({'error': 'Gagal menyimpan pesanan'}), 500
# order_service/app.py
# ... (kode sebelumnya) ...

# Endpoint: GET /orders/<int:order_id>
# Tujuan: Mengambil detail spesifik suatu pesanan beserta detail user & produk (jika memungkinkan).
@app.route('/orders/<int:order_id>', methods=['GET'])
def get_order_details(order_id):
    order_data = None
    try:
        # Explain: Langkah 1 - Ambil data pesanan dasar dari database lokal (order_data.db).
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, user_id, product_id, quantity, total_price, status FROM orders WHERE id = ?",
                (order_id,)
            )
            order_data = cursor.fetchone()

        # Explain: Jika pesanan dengan ID tersebut tidak ditemukan di DB lokal.
        if not order_data:
            return jsonify({"error": "Pesanan tidak ditemukan"}), 404

        # Explain: Konversi data order dasar ke dictionary.
        order_details = dict(order_data)

        # Explain: Langkah 2 - Coba ambil detail pengguna dari User Provider.
        user_details = fetch_user_details(order_data['user_id'])
        if user_details:
            order_details['user_details'] = user_details
        else:
            # Jika gagal ambil detail, tambahkan indikator.
            order_details['user_details'] = {"error": "Gagal mengambil detail pengguna"}

        # Explain: Langkah 3 - Coba ambil detail produk dari Product Provider.
        product_details = fetch_product_details(order_data['product_id'])
        if product_details:
             order_details['product_details'] = product_details
        else:
             # Jika gagal ambil detail, tambahkan indikator.
             order_details['product_details'] = {"error": "Gagal mengambil detail produk"}

        # Explain: Kembalikan gabungan data pesanan, detail user, dan detail produk.
        return jsonify(order_details), 200 # OK

    except Exception as e:
        app.logger.error(f"Error fetching details for order {order_id}: {e}")
        return jsonify({"error": "Kesalahan server internal saat mengambil detail pesanan"}), 500

# --- Menjalankan Aplikasi ---
if __name__ == '__main__':
    init_db() # Inisialisasi DB saat start
    # Explain: Port 5003 untuk layanan pesanan.
    app.run(host='0.0.0.0', port=5003, debug=True)