import streamlit as st
import sqlite3
import pandas as pd
import re
from datetime import datetime, timedelta
import io
import base64
from PIL import Image
import urllib.parse

# ==========================================
# 1. SETUP DATABASE & KONFIGURASI APLIKASI
# ==========================================
st.set_page_config(
    page_title="SM Laundry - Kasir & Operasional",
    page_icon="🧺",
    layout="wide"
)

def get_connection():
    return sqlite3.connect('sm_laundry.db', check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Tabel Transaksi
    c.execute('''CREATE TABLE IF NOT EXISTS transaksi 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  kode_nota TEXT UNIQUE,
                  tgl_transaksi TEXT,
                  tgl_estimasi_selesai TEXT,
                  nama TEXT, 
                  no_hp TEXT, 
                  layanan TEXT, 
                  berat REAL, 
                  parfum TEXT, 
                  baju_putih TEXT, 
                  dress_sensitif TEXT, 
                  catatan TEXT, 
                  total INT, 
                  status_bayar TEXT, 
                  bayar_dp INT,
                  sisa INT, 
                  status_laundry TEXT,
                  jumlah_bungkus INT,
                  tgl_selesai TEXT,
                  foto_jemur TEXT,
                  foto_lipat TEXT)''')

    # Migrasi Kolom Transaksi (jika database lama)
    c.execute("PRAGMA table_info(transaksi)")
    cols_t = [col[1] for col in c.fetchall()]
    if 'kode_nota' not in cols_t:
        c.execute("ALTER TABLE transaksi ADD COLUMN kode_nota TEXT")
    if 'tgl_estimasi_selesai' not in cols_t:
        c.execute("ALTER TABLE transaksi ADD COLUMN tgl_estimasi_selesai TEXT")
    if 'foto_jemur' not in cols_t:
        c.execute("ALTER TABLE transaksi ADD COLUMN foto_jemur TEXT")
    if 'foto_lipat' not in cols_t:
        c.execute("ALTER TABLE transaksi ADD COLUMN foto_lipat TEXT")

    # Tabel Master Layanan
    c.execute('''CREATE TABLE IF NOT EXISTS master_layanan 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  kategori TEXT,
                  nama_layanan TEXT, 
                  tipe TEXT,
                  durasi TEXT,
                  durasi_jam INTEGER,
                  harga INTEGER,
                  satuan TEXT)''')

    # Tabel Master Pelanggan
    c.execute('''CREATE TABLE IF NOT EXISTS master_pelanggan 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  nama TEXT, 
                  no_hp TEXT UNIQUE,
                  created_at TEXT)''')

    # Tabel Master Parfum
    c.execute('''CREATE TABLE IF NOT EXISTS master_parfum 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  nama_parfum TEXT UNIQUE)''')

    # Tabel Master User (RBAC Login)
    c.execute('''CREATE TABLE IF NOT EXISTS master_user
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE,
                  password TEXT,
                  nama_user TEXT,
                  role TEXT)''')

    # Seed Data Default User
    c.execute("SELECT COUNT(*) FROM master_user")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO master_user (username, password, nama_user, role) VALUES (?, ?, ?, ?)", [
            ("owner", "adminlaundry", "Pemilik SM Laundry", "owner"),
            ("kasir", "kasirlaundry", "Staf Kasir/Operasional", "pegawai")
        ])

    # Seed Data Default Layanan
    c.execute("SELECT COUNT(*) FROM master_layanan")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO master_layanan (kategori, nama_layanan, tipe, durasi, durasi_jam, harga, satuan) VALUES (?, ?, ?, ?, ?, ?, ?)", [
            ("Cuci Kiloan", "Cuci Komplit", "Biasa", "2 Hari", 48, 7000, "Kg"),
            ("Cuci Kiloan", "Cuci Komplit", "Express", "1 Hari", 24, 10000, "Kg"),
            ("Cuci Kiloan", "Cuci Komplit", "Kilat", "6 Jam", 6, 15000, "Kg"),
            ("Cuci Kiloan", "Setrika Saja", "Biasa", "2 Hari", 48, 5000, "Kg"),
            ("Cuci Satuan", "Bedcover", "Biasa", "3 Hari", 72, 25000, "Pcs"),
        ])

    # Seed Data Default Parfum
    c.execute("SELECT COUNT(*) FROM master_parfum")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO master_parfum (nama_parfum) VALUES (?)", [
            ("Fresh Lavender",), ("Sakura",), ("Ocean Fresh",), ("Tanpa Parfum",)
        ])

    conn.commit()
    conn.close()

init_db()

# Helper Functions
def clean_phone(phone_str):
    if not phone_str:
        return ""
    phone = str(phone_str).strip().replace("-", "").replace(" ", "").replace("+", "")
    if phone.startswith("0"):
        phone = "62" + phone[1:]
    return phone

def generate_kode_nota(tgl_dt):
    yymmdd = tgl_dt.strftime("%y%m%d")
    prefix = f"TRX/{yymmdd}"
    
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT kode_nota FROM transaksi WHERE kode_nota LIKE ? ORDER BY id DESC LIMIT 1", (f"{prefix}%",))
    row = c.fetchone()
    conn.close()

    if row and row[0]:
        last_code = row[0]
        try:
            last_counter = int(last_code[-3:])
            new_counter = last_counter + 1
        except:
            new_counter = 1
    else:
        new_counter = 1

    return f"{prefix}{new_counter:03d}"

def process_img_to_base64(img_file):
    if img_file is not None:
        try:
            image = Image.open(img_file)
            image.thumbnail((800, 800))
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG", quality=70)
            return base64.b64encode(buffered.getvalue()).decode()
        except Exception as e:
            st.error(f"Gagal memproses foto: {e}")
            return None
    return None

def create_wa_link(no_hp, pesan_raw):
    wa_phone = clean_phone(no_hp)
    pesan_encoded = urllib.parse.quote(pesan_raw)
    return f"https://wa.me/{wa_phone}?text={pesan_encoded}"

# JS Script Web Bluetooth Universal
JS_BLUETOOTH_PRINT = """
<script>
async function printBluetooth(rawText) {
    try {
        let device = await navigator.bluetooth.requestDevice({
            acceptAllDevices: true,
            optionalServices: [
                '000018f0-0000-1000-8000-00805f9b34fb',
                'e7810a71-73ae-499d-8c15-faa9aef0c3f2',
                '0000ff00-0000-1000-8000-00805f9b34fb'
            ]
        });

        let server = await device.gatt.connect();
        let services = await server.getPrimaryServices();
        
        if (services.length === 0) {
            alert('Tidak dapat menemukan layanan Bluetooth Printer!');
            return;
        }

        let service = services[0];
        let characteristics = await service.getCharacteristics();
        
        let printChar = null;
        for (let c of characteristics) {
            if (c.properties.write || c.properties.writeWithoutResponse) {
                printChar = c;
                break;
            }
        }

        if (!printChar) {
            alert('Karakteristik write Bluetooth printer tidak ditemukan!');
            return;
        }

        let encoder = new TextEncoder();
        let data = encoder.encode(rawText + "\\n\\n\\n");
        await printChar.writeValue(data);
        alert('✅ Berhasil mengirimkan data ke Bluetooth Printer!');
    } catch (error) {
        console.error(error);
        alert('❌ Gagal mencetak via Bluetooth: ' + error.message);
    }
}
</script>
"""

# ==========================================
# 2. SISTEM AUTHENTICATION (LOGIN/LOGOUT)
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["user_info"] = None

def login_user(username, password):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, username, nama_user, role FROM master_user WHERE username = ? AND password = ?", (username, password))
    user = c.fetchone()
    conn.close()
    return user

def logout_user():
    st.session_state["logged_in"] = False
    st.session_state["user_info"] = None
    st.rerun()

if not st.session_state["logged_in"]:
    st.markdown("<h2 style='text-align: center;'>🧺 LOGIN SM LAUNDRY</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Silakan masukkan Username dan Password Anda</p>", unsafe_allow_html=True)
    
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        with st.form("form_login"):
            username_input = st.text_input("Username")
            password_input = st.text_input("Password", type="password")
            submit_login = st.form_submit_button("🔑 Masuk ke Sistem", type="primary", use_container_width=True)
            
            if submit_login:
                user = login_user(username_input, password_input)
                if user:
                    st.session_state["logged_in"] = True
                    st.session_state["user_info"] = {
                        "id": user[0],
                        "username": user[1],
                        "nama": user[2],
                        "role": user[3]
                    }
                    st.success(f"Selamat datang, {user[2]}!")
                    st.rerun()
                else:
                    st.error("❌ Username atau Password salah. Silakan coba lagi.")
    st.stop()

# ==========================================
# DIALOG PRINT STRUK
# ==========================================
@st.dialog("🖨️ Cetak Nota & Label Laundry", width="large")
def show_print_dialog(trx_id):
    conn = get_connection()
    df_trx = pd.read_sql_query("SELECT * FROM transaksi WHERE id = ?", conn, params=(trx_id,))
    conn.close()

    if df_trx.empty:
        st.error("Data nota tidak ditemukan.")
        return

    trx = df_trx.iloc[0]
    kode_nota = trx['kode_nota'] if trx['kode_nota'] else f"TRX/{trx['id']}"

    tgl_masuk_f = datetime.strptime(trx['tgl_transaksi'], "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y %H:%M") if trx['tgl_transaksi'] else "-"
    tgl_est_f = datetime.strptime(trx['tgl_estimasi_selesai'], "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y %H:%M") if trx['tgl_estimasi_selesai'] else "-"

    tab_cust, tab_tag = st.tabs(["📄 Struk Pelanggan", "🏷️ Label Tempel Produksi"])

    with tab_cust:
        st.caption("Nota Rata Kanan-Kiri untuk Pelanggan")
        
        html_pelanggan = f"""
        <style>
            .nota-box {{
                font-family: 'Courier New', Courier, monospace;
                width: 290px;
                padding: 10px;
                border: 1px dashed #333;
                margin: auto;
                background-color: #fff;
                color: #000;
                font-size: 12px;
            }}
            .row-flex {{ display: flex; justify-content: space-between; margin: 3px 0; }}
            .text-center {{ text-align: center; }}
            .bold {{ font-weight: bold; }}
            .line {{ border-bottom: 1px dashed #000; margin: 6px 0; }}
            .sk-box {{ font-size: 9.5px; margin-top: 6px; text-align: left; line-height: 1.2; }}
            .sk-title {{ font-weight: bold; margin-bottom: 2px; }}
            .sk-list {{ margin: 0; padding-left: 14px; }}
        </style>

        <div class="nota-box">
            <div class="text-center">
                <h3 style="margin: 0; font-size: 16px;">SM LAUNDRY</h3>
                <p style="font-size: 10px; margin: 2px 0;">Jl. Maritim 28 Socah Bangkalan<br>WA: 085257357246</p>
                <div class="line"></div>
            </div>

            <div class="row-flex"><span class="bold">NO NOTA</span><span class="bold">{kode_nota}</span></div>
            <div class="row-flex"><span>Tgl Masuk</span><span>{tgl_masuk_f}</span></div>
            <div class="row-flex"><span class="bold">Est. Selesai</span><span class="bold">{tgl_est_f}</span></div>
            <div class="row-flex"><span>Pelanggan</span><span>{trx['nama']}</span></div>
            <div class="row-flex"><span>No. HP</span><span>{trx['no_hp']}</span></div>
            
            <div class="line"></div>
            <div class="bold">{trx['layanan']}</div>
            <div class="row-flex"><span>Jumlah / Berat</span><span>{trx['berat']}</span></div>
            <div class="row-flex"><span>Pilihan Parfum</span><span>{trx['parfum']}</span></div>
            <div class="row-flex"><span>Catatan Khusus</span><span>{trx['catatan'] if trx['catatan'] else '-'}</span></div>
            
            <div class="line"></div>
            <div class="row-flex"><span class="bold">TOTAL TAGIHAN</span><span class="bold">Rp {trx['total']:,}</span></div>
            <div class="row-flex"><span>Bayar / DP</span><span>Rp {trx['bayar_dp']:,}</span></div>
            <div class="row-flex"><span>Status Bayar</span><span class="bold">{trx['status_bayar']}</span></div>
            <div class="row-flex"><span class="bold">SISA BAYAR</span><span class="bold">Rp {trx['sisa']:,}</span></div>
            <div class="line"></div>

            <div class="sk-box">
                <div class="sk-title">Syarat & Ketentuan SM Laundry:</div>
                <ol class="sk-list">
                    <li>Komplain maksimal 1x24 jam setelah pakaian diambil dengan menyertakan nota ini.</li>
                    <li>Kerusakan/kehilangan akibat kelalaian bawaan (pakaian lapuk, luntur dari bahan) di luar tanggung jawab kami.</li>
                </ol>
            </div>

            <div class="line"></div>
            <div class="text-center" style="font-size: 10px; margin-top: 5px;">
                <p style="margin: 2px 0;">Terima Kasih Atas Kepercayaan Anda!</p>
            </div>
        </div>
        """
        st.components.v1.html(html_pelanggan, height=480, scrolling=True)
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🖨️ Print Struk (Kabel/Biasa)", key="btn_print_cust"):
                st.components.v1.html(
                    f"""<script>
                        var printWindow = window.open('', '', 'width=400,height=600');
                        printWindow.document.write('<html><head><title>Print Struk {kode_nota}</title></head><body>');
                        printWindow.document.write('{html_pelanggan.replace("\n", "")}');
                        printWindow.document.write('</body></html>');
                        printWindow.document.close();
                        printWindow.focus();
                        setTimeout(function() {{ printWindow.print(); printWindow.close(); }}, 250);
                    </script>""", height=0
                )
        with c2:
            raw_bts_text = f"SM LAUNDRY\\nJl. Maritim 28 Socah Bangkalan\\nWA: 085257357246\\n--------------------------------\\nNOTA: {kode_nota}\\nTgl: {tgl_masuk_f}\\nPelanggan: {trx['nama']}\\nHP: {trx['no_hp']}\\n--------------------------------\\n{trx['layanan']}\\nJumlah: {trx['berat']}\\nParfum: {trx['parfum']}\\nCatatan: {trx['catatan'] if trx['catatan'] else '-'}\\n--------------------------------\\nTotal : Rp {trx['total']:,}\\nBayar : Rp {trx['bayar_dp']:,}\\nSisa  : Rp {trx['sisa']:,}\\n--------------------------------\\nTerima Kasih!"
            st.components.v1.html(
                f"""{JS_BLUETOOTH_PRINT}
                <button onclick="printBluetooth('{raw_bts_text}')" style="width:100%; height:40px; background-color:#28a745; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">
                    📱 Print Bluetooth Thermal
                </button>""", height=50
            )

    with tab_tag:
        st.caption("Label Tempel Keranjang / Plastik Pakaian + Checklist Manual Bolpoin")
        
        html_tag = f"""
        <style>
            .tag-box {{
                font-family: 'Courier New', Courier, monospace;
                width: 290px;
                padding: 10px;
                border: 2px solid #000;
                margin: auto;
                background-color: #fff;
                color: #000;
                font-size: 12px;
            }}
            .row-flex {{ display: flex; justify-content: space-between; margin: 4px 0; }}
            .text-center {{ text-align: center; }}
            .bold {{ font-weight: bold; }}
            .line {{ border-bottom: 2px solid #000; margin: 6px 0; }}
            .line-dashed {{ border-bottom: 1px dashed #000; margin: 6px 0; }}
            .check-item {{ display: flex; align-items: center; justify-content: space-between; margin: 3px 0; }}
            .box-check {{ display: inline-block; width: 12px; height: 12px; border: 1.5px solid #000; text-align: center; font-size: 10px; line-height: 10px; }}
        </style>

        <div class="tag-box">
            <div class="text-center">
                <h2 style="margin: 0; font-size: 20px;">{kode_nota}</h2>
                <h3 style="margin: 2px 0; font-size: 15px;">{trx['nama'].upper()}</h3>
            </div>
            <div class="line"></div>

            <div class="row-flex"><span class="bold">⏰ TARGET SELESAI</span><span class="bold">{tgl_est_f}</span></div>
            <div class="row-flex"><span>⚙️ Layanan</span><span class="bold">{trx['layanan']}</span></div>
            <div class="row-flex"><span>⚖️ Jumlah/Berat</span><span class="bold">{trx['berat']}</span></div>
            <div class="row-flex"><span>🌸 Parfum</span><span class="bold">{trx['parfum'].upper()}</span></div>
            
            <div class="line-dashed"></div>
            <div class="bold">🛡️ SAFETY CHECK KASIR:</div>
            <div class="row-flex"><span>• Baju Putih</span><span class="bold">{trx['baju_putih'].upper()}</span></div>
            <div class="row-flex"><span>• Sensitif/Dress</span><span class="bold">{trx['dress_sensitif'].upper()}</span></div>
            
            <div class="line-dashed"></div>
            <div class="bold">📝 CHECKLIST PRODUKSI (BOLPOIN):</div>
            <div class="check-item"><span>[ <span class="box-check"></span> ] Kantong Pakaian Kosong</span><span>(Petugas: ____)</span></div>
            <div class="check-item"><span>[ <span class="box-check"></span> ] Tanpa Pakaian Dalam</span><span>(Petugas: ____)</span></div>
            <div class="check-item"><span>[ <span class="box-check"></span> ] Luntur / Nodanya Aman</span><span>(Petugas: ____)</span></div>
            <div class="check-item"><span>[ <span class="box-check"></span> ] Hitung Jumlah Pcs Lengkap</span><span>(____ Pcs)</span></div>

            <div class="line-dashed"></div>
            <div class="bold">📸 CHECKLIST MEMOTRET (SISTEM):</div>
            <div class="check-item"><span>[ <span class="box-check"></span> ] Foto Saat Dijemur</span><span>(Sudah Upload)</span></div>
            <div class="check-item"><span>[ <span class="box-check"></span> ] Foto Selesai Dilipat</span><span>(Sudah Upload)</span></div>

            <div class="line-dashed"></div>
            <div class="bold">📝 CATATAN KHUSUS:</div>
            <div>{trx['catatan'] if trx['catatan'] else 'TIDAK ADA'}</div>
            
            <div class="line" style="margin-top: 8px;"></div>
            <div class="text-center bold" style="font-size: 10px;">SM LAUNDRY - LABEL TEMPEL CUCI</div>
        </div>
        """
        st.components.v1.html(html_tag, height=520, scrolling=True)
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🖨️ Print Label Tempel", key="btn_print_tag"):
                st.components.v1.html(
                    f"""<script>
                        var printWindow = window.open('', '', 'width=400,height=600');
                        printWindow.document.write('<html><head><title>Print Label {kode_nota}</title></head><body>');
                        printWindow.document.write('{html_tag.replace("\n", "")}');
                        printWindow.document.write('</body></html>');
                        printWindow.document.close();
                        printWindow.focus();
                        setTimeout(function() {{ printWindow.print(); printWindow.close(); }}, 250);
                    </script>""", height=0
                )
        with c2:
            raw_tag_bts = f"LABEL PRODUKSI\\n{kode_nota}\\n{trx['nama'].upper()}\\n--------------------------------\\nTarget : {tgl_est_f}\\nLayanan: {trx['layanan']}\\nJumlah : {trx['berat']}\\nParfum : {trx['parfum'].upper()}\\nCatatan: {trx['catatan'] if trx['catatan'] else 'TIDAK ADA'}\\n--------------------------------\\nSM LAUNDRY"
            st.components.v1.html(
                f"""{JS_BLUETOOTH_PRINT}
                <button onclick="printBluetooth('{raw_tag_bts}')" style="width:100%; height:40px; background-color:#28a745; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">
                    📱 Print Bluetooth Label
                </button>""", height=50
            )

# ==========================================
# 3. HEADER BRANDING & NAVIGASI
# ==========================================
user_info = st.session_state["user_info"]
user_role = user_info["role"]

st.sidebar.markdown(f"👤 **Pengguna:** {user_info['nama']} ({user_role.upper()})")
if st.sidebar.button("🚪 Logout"):
    logout_user()

st.title("🧺 SM LAUNDRY")
st.markdown("**Jl. Maritim 28 Socah Bangkalan** | 📞 **WA:** 085257357246")
st.divider()

if user_role == "owner":
    list_menu = [
        "🏠 Beranda / Dashboard", 
        "🔍 Tracking Nota & Foto Dokumentasi",
        "📝 POS / Kasir Baru", 
        "✏️ Edit / Ubah Nota", 
        "🔄 Papan Status Produksi", 
        "💰 Laporan Keuangan", 
        "👥 Laporan Pelanggan", 
        "⚙️ Pengaturan Master Data"
    ]
else:
    list_menu = [
        "🏠 Beranda / Dashboard", 
        "🔍 Tracking Nota & Foto Dokumentasi",
        "📝 POS / Kasir Baru", 
        "🔄 Papan Status Produksi", 
        "👥 Laporan Pelanggan"
    ]

if "target_page" in st.session_state:
    st.session_state["nav_radio"] = st.session_state["target_page"]
    del st.session_state["target_page"]

if "nav_radio" not in st.session_state or st.session_state["nav_radio"] not in list_menu:
    st.session_state["nav_radio"] = "🏠 Beranda / Dashboard"

menu = st.sidebar.radio(
    "📌 Navigasi Utama",
    options=list_menu,
    key="nav_radio"
)

def navigate_to(page_name):
    if page_name in list_menu:
        st.session_state["target_page"] = page_name

# ==========================================
# MODUL 0: BERANDA / DASHBOARD
# ==========================================
if menu == "🏠 Beranda / Dashboard":
    st.header("🏠 Beranda & Pemantauan Transaksi Hari Ini")
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    conn = get_connection()
    df_all = pd.read_sql_query("SELECT id, kode_nota, tgl_transaksi, tgl_estimasi_selesai, nama, no_hp, layanan, berat, parfum, status_laundry, status_bayar, total, sisa, tgl_selesai FROM transaksi", conn)
    conn.close()

    if not df_all.empty:
        df_today = df_all[df_all['tgl_transaksi'].str.startswith(today_str, na=False)]
        trx_masuk_today = len(df_today)
        omset_today = df_today['total'].sum()
        
        trx_dicuci = len(df_all[df_all['status_laundry'] == 'Dicuci'])
        trx_disetrika = len(df_all[df_all['status_laundry'] == 'Disetrika'])
        
        df_selesai_today = df_all[
            (df_all['status_laundry'].isin(['Selesai', 'Sudah Diambil'])) & 
            (df_all['tgl_selesai'].str.startswith(today_str, na=False))
        ]
        trx_selesai_today = len(df_selesai_today)
    else:
        trx_masuk_today = 0
        omset_today = 0
        trx_dicuci = 0
        trx_disetrika = 0
        trx_selesai_today = 0

    st.caption("💡 *Klik tombol info di bawah untuk langsung menuju halaman detailnya:*")
    
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("📥 Transaksi Hari Ini", f"{trx_masuk_today} Nota")
        if user_role == "owner":
            if st.button("📊 Ke Laporan", key="btn_dash_trx"):
                navigate_to("💰 Laporan Keuangan")
                st.rerun()

    with c2:
        st.metric("🔵 Masih Dicuci", f"{trx_dicuci} Nota")
        if st.button("🔍 Lihat Antrean", key="btn_dash_cuci"):
            navigate_to("🔄 Papan Status Produksi")
            st.rerun()

    with c3:
        st.metric("🟣 Masih Disetrika", f"{trx_disetrika} Nota")
        if st.button("🔍 Lihat Setrika", key="btn_dash_strk"):
            navigate_to("🔄 Papan Status Produksi")
            st.rerun()

    with c4:
        st.metric("🟢 Selesai Hari Ini", f"{trx_selesai_today} Nota")
        if st.button("🔍 Lihat Selesai", key="btn_dash_sls"):
            navigate_to("🔄 Papan Status Produksi")
            st.rerun()

    with c5:
        if user_role == "owner":
            st.metric("💰 Omset Hari Ini", f"Rp {omset_today:,}")
            if st.button("💰 Detail Omset", key="btn_dash_omset"):
                navigate_to("💰 Laporan Keuangan")
                st.rerun()
        else:
            st.metric("🔒 Omset Hari Ini", "Khusus Owner")

    st.markdown("---")

    col_act1, col_act2 = st.columns([1, 2])
    with col_act1:
        if st.button("➕ **Buka Kasir Transaksi Baru**", type="primary", use_container_width=True):
            navigate_to("📝 POS / Kasir Baru")
            st.rerun()

    st.markdown("### 📊 Transaksi Sedang Berlangsung (Aktif)")
    
    if not df_all.empty:
        df_aktif = df_all[df_all['status_laundry'] != 'Sudah Diambil'].copy()
        if df_aktif.empty:
            st.info("🎉 Tidak ada transaksi aktif yang sedang dikerjakan. Semua laundry sudah diambil!")
        else:
            df_aktif['Kode Nota'] = df_aktif.apply(lambda r: r['kode_nota'] if r['kode_nota'] else f"TRX/{r['id']}", axis=1)
            
            df_display = df_aktif[[
                'Kode Nota', 'tgl_transaksi', 'tgl_estimasi_selesai', 
                'nama', 'no_hp', 'layanan', 'berat', 'parfum', 'status_laundry', 'status_bayar', 'sisa'
            ]].rename(columns={
                'tgl_transaksi': 'Tgl Masuk',
                'tgl_estimasi_selesai': 'Target Selesai',
                'nama': 'Pelanggan',
                'no_hp': 'No WA',
                'layanan': 'Layanan',
                'berat': 'Jumlah/Berat',
                'parfum': 'Parfum',
                'status_laundry': 'Status Produksi',
                'status_bayar': 'Status Bayar',
                'sisa': 'Sisa Tagihan'
            })
            
            st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("ℹ️ Belum ada data transaksi.")

# ==========================================
# MODUL TRACKING NOTA & FOTO DOKUMENTASI
# ==========================================
elif menu == "🔍 Tracking Nota & Foto Dokumentasi":
    st.header("🔍 Tracking Laundry & Foto Bukti Pengerjaan")
    
    conn = get_connection()
    df_trx_track = pd.read_sql_query("SELECT * FROM transaksi ORDER BY id DESC", conn)
    conn.close()

    if df_trx_track.empty:
        st.info("ℹ️ Belum ada transaksi yang dapat diteliti.")
    else:
        df_trx_track['kode_tampil'] = df_trx_track.apply(lambda r: r['kode_nota'] if r['kode_nota'] else f"TRX/{r['id']}", axis=1)
        list_options = [f"{row['kode_tampil']} - {row['nama']} ({row['no_hp']})" for _, row in df_trx_track.iterrows()]
        
        selected_opt = st.selectbox("🔎 Cari berdasarkan Kode Nota / Nama Pelanggan:", list_options)
        idx = list_options.index(selected_opt)
        row = df_trx_track.iloc[idx]

        st.subheader(f"📋 Status Pesanan: {row['kode_tampil']}")
        
        col_t1, col_t2, col_t3 = st.columns(3)
        with col_t1:
            st.write(f"👤 **Pelanggan:** {row['nama']}")
            st.write(f"📞 **WhatsApp:** {row['no_hp']}")
        with col_t2:
            st.write(f"⚙️ **Layanan:** {row['layanan']}")
            st.write(f"🔄 **Status Saat Ini:** `{row['status_laundry']}`")
        with col_t3:
            st.write(f"📅 **Tanggal Masuk:** {row['tgl_transaksi']}")
            st.write(f"🎯 **Target Selesai:** {row['tgl_estimasi_selesai']}")

        # **PERBAIKAN: Tombol Kirim Ulang WA Struk**
        pesan_wa_ulang = (
            f"Halo Kak *{row['nama']}*, berikut rincian nota transaksi Anda di *SM Laundry*:\n\n"
            f"🧾 *NOTA LAUNDRY: #{row['kode_tampil']}*\n"
            f"📅 *Tgl Masuk:* {row['tgl_transaksi']}\n"
            f"⏰ *Estimasi Selesai:* {row['tgl_estimasi_selesai']}\n\n"
            f"*Detail Layanan:*\n"
            f"• Layanan: {row['layanan']}\n"
            f"• Jumlah/Berat: {row['berat']}\n"
            f"• Pilihan Parfum: {row['parfum']}\n"
            f"• Catatan: {row['catatan'] if row['catatan'] else '-'}\n\n"
            f"💵 *Total Biaya:* Rp {row['total']:,}\n"
            f"💳 *Status Bayar:* {row['status_bayar']}\n"
            f"💰 *DP/Bayar:* Rp {row['bayar_dp']:,}\n"
            f"⚠️ *SISA BAYAR: Rp {row['sisa']:,}*\n\n"
            f"📍 _SM Laundry - Jl. Maritim 28 Socah Bangkalan_\n"
            f"📞 _WA: 085257357246_\n\n"
            f"Terima kasih!"
        )
        url_wa_ulang = create_wa_link(row['no_hp'], pesan_wa_ulang)
        st.markdown(f"👉 [**📱 KIRIM ULANG NOTA WA KEPADA PELANGGAN**]({url_wa_ulang})")

        st.divider()
        st.subheader("📸 Foto Bukti Proses Produksi")

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            st.markdown("### ☀️ 1. Foto Saat Dijemur")
            if row['foto_jemur']:
                try:
                    st.image(f"data:image/jpeg;base64,{row['foto_jemur']}", caption=f"Bukti Penjemuran Nota {row['kode_tampil']}", use_container_width=True)
                except Exception as e:
                    st.error("Gagal menampilkan foto jemur.")
            else:
                st.info("📷 Foto proses penjemuran belum diunggah oleh staf.")

        with col_f2:
            st.markdown("### 🧺 2. Foto Selesai Dilipat")
            if row['foto_lipat']:
                try:
                    st.image(f"data:image/jpeg;base64,{row['foto_lipat']}", caption=f"Bukti Selesai Lipat Nota {row['kode_tampil']}", use_container_width=True)
                except Exception as e:
                    st.error("Gagal menampilkan foto lipat.")
            else:
                st.info("📷 Foto hasil lipatan/pembungkusan belum diunggah oleh staf.")

# ==========================================
# MODUL 1: POS / KASIR BARU (FIX BUG REFRESH & TOTAL HP)
# ==========================================
elif menu == "📝 POS / Kasir Baru":
    st.header("📝 Transaksi Kasir Baru")

    conn = get_connection()
    df_pelanggan = pd.read_sql_query("SELECT id, nama, no_hp FROM master_pelanggan ORDER BY nama ASC", conn)
    df_layanan = pd.read_sql_query("SELECT * FROM master_layanan ORDER BY kategori, nama_layanan ASC", conn)
    df_parfum = pd.read_sql_query("SELECT * FROM master_parfum ORDER BY nama_parfum ASC", conn)
    conn.close()

    # **PERBAIKAN BUG HP 2: DAFTAR PELANGGAN TAMPIL DENGAN BENAR**
    opsi_pembeli = st.radio(
        "🔍 Pilihan Input Pelanggan:", 
        ["➕ Pelanggan Baru", "🔎 Cari Pelanggan Terdaftar"], 
        horizontal=True,
        key="radio_opsi_pembeli"
    )

    default_nama, default_hp = "", ""

    if opsi_pembeli == "🔎 Cari Pelanggan Terdaftar":
        if not df_pelanggan.empty:
            pelanggan_list = [f"{r['nama']} ({r['no_hp']})" for _, r in df_pelanggan.iterrows()]
            selected_pel_str = st.selectbox("👤 Pilih/Ketik Nama Pelanggan:", options=pelanggan_list, key="sel_pelanggan_registered")
            if selected_pel_str:
                sel_idx = pelanggan_list.index(selected_pel_str)
                default_nama = df_pelanggan.iloc[sel_idx]['nama']
                default_hp = df_pelanggan.iloc[sel_idx]['no_hp']
        else:
            st.warning("⚠️ Belum ada master data pelanggan terdaftar. Silakan pilih 'Pelanggan Baru'.")

    st.markdown("---")
    
    if df_layanan.empty:
        st.warning("⚠️ Belum ada layanan yang didaftarkan. Minta Owner untuk menambahkannya terlebih dahulu.")
    else:
        kategori_list = df_layanan['kategori'].unique().tolist()
        col_kat, col_lay, col_tip = st.columns(3)
        
        with col_kat:
            kat_selected = st.selectbox("📁 Kategori Layanan*", kategori_list, key="kat_pos")
        
        df_filtered_kat = df_layanan[df_layanan['kategori'] == kat_selected]
        with col_lay:
            lay_selected = st.selectbox("🏷️ Nama Layanan*", df_filtered_kat['nama_layanan'].unique().tolist(), key="lay_pos")
            
        df_filtered_lay = df_filtered_kat[df_filtered_kat['nama_layanan'] == lay_selected]
        tipe_options = [f"{row['tipe']} ({row['durasi']}) - Rp {row['harga']:,}/{row['satuan']}" for _, row in df_filtered_lay.iterrows()]
        
        with col_tip:
            tipe_selected_str = st.selectbox("⚡ Tipe Layanan & Durasi*", tipe_options, key="tip_pos")
            
        selected_layanan_data = df_filtered_lay.iloc[tipe_options.index(tipe_selected_str)]
        satuan_text = selected_layanan_data['satuan']
        harga_per_satuan = selected_layanan_data['harga']
        durasi_jam_layanan = int(selected_layanan_data['durasi_jam']) if pd.notnull(selected_layanan_data['durasi_jam']) else 48
        
        nama_layanan_full = f"[{selected_layanan_data['kategori']}] {selected_layanan_data['nama_layanan']} - {selected_layanan_data['tipe']} ({selected_layanan_data['durasi']})"

        waktu_sekarang = datetime.now()
        waktu_estimasi = waktu_sekarang + timedelta(hours=durasi_jam_layanan)
        kode_nota_preview = generate_kode_nota(waktu_sekarang)

        st.info(f"🆔 **No. Nota:** `{kode_nota_preview}` | 📅 **Masuk:** {waktu_sekarang.strftime('%d-%m-%Y %H:%M')} | 🎯 **Target:** {waktu_estimasi.strftime('%d-%m-%Y %H:%M')}")

        list_parfum = df_parfum['nama_parfum'].tolist() if not df_parfum.empty else ["Fresh Lavender", "Tanpa Parfum"]

        # **PERBAIKAN BUG HP 1: DIKELUARKAN DARI FORM SUPAYA DYNAMIC UPDATE (REALTIME TOTAL BIAYA)**
        col1, col2 = st.columns(2)
        with col1:
            nama = st.text_input("Nama Pelanggan*", value=default_nama, key="pos_nama")
            no_hp = st.text_input("No. WhatsApp*", value=default_hp, key="pos_hp")
            berat = st.number_input(f"Jumlah / Berat ({satuan_text})*", min_value=0.1, step=0.1, value=1.0, key="pos_berat")
        with col2:
            parfum = st.selectbox("Pilih Parfum*", list_parfum, key="pos_parfum")
            status_bayar = st.radio("Status Pembayaran*", ["LUNAS", "BELUM BAYAR", "DP"], horizontal=True, key="pos_status_bayar")
            bayar_dp = st.number_input("Nominal DP (Jika DP)", min_value=0, step=1000, value=0, key="pos_dp")

        # HITUNG TOTAL SECARA DYNAMIS REAL-TIME
        total_harga = int(berat * harga_per_satuan)
        dp_val = total_harga if status_bayar == "LUNAS" else (int(bayar_dp) if status_bayar == "DP" else 0)
        sisa_bayar = total_harga - dp_val

        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            chk_underwear = st.checkbox("✅ Bebas pakaian dalam (underwear)", key="pos_chk1")
            chk_kantong = st.checkbox("✅ Kantong pakaian sudah diperiksa", key="pos_chk2")
        with c2:
            baju_putih = st.radio("Ada Baju Putih?", ["Tidak", "Ya"], horizontal=True, key="pos_putih")
            dress_sensitif = st.radio("Ada Dress / Bahan Sensitif?", ["Tidak", "Ya"], horizontal=True, key="pos_dress")

        catatan = st.text_area("Catatan Khusus", key="pos_catatan")

        # INDIKATOR HIGHLIGHT TOTAL BIAYA UNTUK HP
        st.markdown(f"### 💵 **Total Biaya: Rp {total_harga:,}** | **Sisa Bayar: Rp {sisa_bayar:,}**")

        if st.button("💾 **SIMPAN TRANSAKSI BARU**", type="primary", use_container_width=True):
            if not (chk_underwear and chk_kantong):
                st.error("❌ Peringatan Safety: Kasir WAJIB memeriksa pakaian dalam & kantong!")
            elif not nama or not no_hp:
                st.error("❌ Nama & WhatsApp wajib diisi.")
            else:
                tgl_masuk_str = waktu_sekarang.strftime("%Y-%m-%d %H:%M:%S")
                tgl_est_str = waktu_estimasi.strftime("%Y-%m-%d %H:%M:%S")

                conn = get_connection()
                c = conn.cursor()
                c.execute("INSERT OR IGNORE INTO master_pelanggan (nama, no_hp, created_at) VALUES (?, ?, ?)", (nama, no_hp, tgl_masuk_str))
                c.execute("UPDATE master_pelanggan SET nama = ? WHERE no_hp = ?", (nama, no_hp))

                c.execute('''INSERT INTO transaksi 
                             (kode_nota, tgl_transaksi, tgl_estimasi_selesai, nama, no_hp, layanan, berat, parfum, baju_putih, dress_sensitif, catatan, total, status_bayar, bayar_dp, sisa, status_laundry, jumlah_bungkus) 
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                          (kode_nota_preview, tgl_masuk_str, tgl_est_str, nama, no_hp, nama_layanan_full, berat, parfum, baju_putih, dress_sensitif, catatan, total_harga, status_bayar, dp_val, sisa_bayar, "Diterima", 0))
                conn.commit()
                nota_db_id = c.lastrowid
                conn.close()

                st.session_state['last_trx_id'] = nota_db_id
                st.success(f"✅ Transaksi **{kode_nota_preview}** berhasil disimpan!")

                pesan_wa_raw = (
                    f"Halo Kak *{nama}*, terima kasih telah mencuci di *SM Laundry*! ✨\n\n"
                    f"Berikut rincian nota transaksi Anda:\n\n"
                    f"🧾 *NOTA LAUNDRY: #{kode_nota_preview}*\n"
                    f"📅 *Tgl Masuk:* {waktu_sekarang.strftime('%d/%m/%Y %H:%M')}\n"
                    f"⏰ *Estimasi Selesai:* {waktu_estimasi.strftime('%d/%m/%Y %H:%M')}\n\n"
                    f"*Detail Layanan:*\n"
                    f"• Layanan: {nama_layanan_full}\n"
                    f"• Jumlah/Berat: {berat} {satuan_text}\n"
                    f"• Pilihan Parfum: {parfum}\n"
                    f"• Catatan: {catatan if catatan else '-'}\n\n"
                    f"💵 *Total Biaya:* Rp {total_harga:,}\n"
                    f"💳 *Status Bayar:* {status_bayar}\n"
                    f"💰 *DP/Bayar:* Rp {dp_val:,}\n"
                    f"⚠️ *SISA BAYAR: Rp {sisa_bayar:,}*\n\n"
                    f"📍 _SM Laundry - Jl. Maritim 28 Socah Bangkalan_\n"
                    f"📞 _WA: 085257357246_\n\n"
                    f"Terima kasih atas kepercayaan Anda! 🙏"
                )
                url_wa = create_wa_link(no_hp, pesan_wa_raw)
                st.markdown(f"👉 [**📱 KLIK DISINI UNTUK KIRIM STRUK WA PELANGGAN**]({url_wa})")

        if 'last_trx_id' in st.session_state:
            st.divider()
            if st.button("🖨️ Cetak Struk Pelanggan & Label Tempel", type="primary"):
                show_print_dialog(st.session_state['last_trx_id'])

# ==========================================
# MODUL EDIT / UBAH NOTA & KIRIM ULANG WA
# ==========================================
elif menu == "✏️ Edit / Ubah Nota":
    st.header("✏️ Edit & Cetak Ulang / Kirim Ulang WA Nota (Khusus Owner)")

    conn = get_connection()
    df_transaksi = pd.read_sql_query("SELECT * FROM transaksi ORDER BY id DESC", conn)
    conn.close()

    if not df_transaksi.empty:
        df_transaksi['kode_tampil'] = df_transaksi.apply(lambda r: r['kode_nota'] if r['kode_nota'] else f"TRX/{r['id']}", axis=1)
        option_nota = [f"{row['kode_tampil']} - {row['nama']} ({row['tgl_transaksi']})" for _, row in df_transaksi.iterrows()]
        selected_nota_str = st.selectbox("🔍 Pilih Nota:", option_nota)
        
        selected_idx = option_nota.index(selected_nota_str)
        data_nota = df_transaksi.iloc[selected_idx]
        nota_id_selected = int(data_nota['id'])

        # **PERBAIKAN BUG HP 3: DAPAT KIRIM ULANG NOTA WA DARI SINI**
        pesan_wa_edit = (
            f"Halo Kak *{data_nota['nama']}*, berikut update nota transaksi Anda di *SM Laundry*:\n\n"
            f"🧾 *NOTA LAUNDRY: #{data_nota['kode_tampil']}*\n"
            f"📅 *Tgl Masuk:* {data_nota['tgl_transaksi']}\n\n"
            f"*Detail Layanan:*\n"
            f"• Layanan: {data_nota['layanan']}\n"
            f"• Jumlah/Berat: {data_nota['berat']}\n"
            f"• Parfum: {data_nota['parfum']}\n"
            f"• Catatan: {data_nota['catatan'] if data_nota['catatan'] else '-'}\n\n"
            f"💵 *Total Biaya:* Rp {data_nota['total']:,}\n"
            f"💳 *Status Bayar:* {data_nota['status_bayar']}\n"
            f"💰 *DP/Bayar:* Rp {data_nota['bayar_dp']:,}\n"
            f"⚠️ *SISA BAYAR: Rp {data_nota['sisa']:,}*\n\n"
            f"📍 _SM Laundry - Jl. Maritim 28 Socah Bangkalan_\n"
            f"📞 _WA: 085257357246_"
        )
        url_wa_edit = create_wa_link(data_nota['no_hp'], pesan_wa_edit)

        c_act1, c_act2 = st.columns(2)
        with c_act1:
            if st.button("🖨️ Cetak Ulang Struk / Label Nota Ini", use_container_width=True):
                show_print_dialog(nota_id_selected)
        with c_act2:
            st.markdown(f"👉 [**📱 KIRIM ULANG WA NOTA TERBARU**]({url_wa_edit})")

        st.divider()
        with st.form("form_edit_nota"):
            st.subheader(f"🛠️ Edit Data {data_nota['kode_tampil']}")
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                e_nama = st.text_input("Nama Pelanggan", value=data_nota['nama'])
                e_hp = st.text_input("No. WhatsApp", value=data_nota['no_hp'])
                e_layanan = st.text_input("Detail Layanan", value=data_nota['layanan'])
                e_berat = st.number_input("Berat / Jumlah", value=float(data_nota['berat']), min_value=0.1, step=0.1)
            with col_e2:
                e_total = st.number_input("Total (Rp)", value=int(data_nota['total']), step=1000)
                e_status_bayar = st.selectbox("Status Bayar", ["LUNAS", "BELUM BAYAR", "DP"], index=["LUNAS", "BELUM BAYAR", "DP"].index(data_nota['status_bayar']))
                e_bayar_dp = st.number_input("DP Diterima (Rp)", value=int(data_nota['bayar_dp']), step=1000)
                e_status_laundry = st.selectbox("Status Laundry", ["Diterima", "Dicuci", "Disetrika", "Selesai", "Sudah Diambil"], index=["Diterima", "Dicuci", "Disetrika", "Selesai", "Sudah Diambil"].index(data_nota['status_laundry']))

            e_catatan = st.text_area("Catatan Khusus", value=data_nota['catatan'])
            
            e_dp = e_total if e_status_bayar == "LUNAS" else (e_bayar_dp if e_status_bayar == "DP" else 0)
            e_sisa = e_total - e_dp

            if st.form_submit_button("💾 Simpan Perubahan Nota"):
                conn = get_connection()
                c = conn.cursor()
                c.execute('''UPDATE transaksi SET 
                             nama = ?, no_hp = ?, layanan = ?, berat = ?, total = ?, 
                             status_bayar = ?, bayar_dp = ?, sisa = ?, status_laundry = ?, catatan = ? 
                             WHERE id = ?''',
                          (e_nama, e_hp, e_layanan, e_berat, e_total, e_status_bayar, e_dp, e_sisa, e_status_laundry, e_catatan, nota_id_selected))
                conn.commit()
                conn.close()
                st.success("✅ Perubahan Nota berhasil disimpan!")
                st.rerun()

# ==========================================
# MODUL PAPAN PRODUKSI
# ==========================================
elif menu == "🔄 Papan Status Produksi":
    st.header("🔄 Status Produksi Laundry & Dokumentasi Foto")
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM transaksi WHERE status_laundry != 'Sudah Diambil' ORDER BY id ASC", conn)
    conn.close()

    if df.empty:
        st.info("🎉 Antrean laundry bersih!")
    else:
        tab1, tab2, tab3, tab4 = st.tabs(["🟡 Diterima", "🔵 Dicuci (Ambil Foto Jemur)", "🟣 Disetrika (Ambil Foto Lipat)", "🟢 Selesai / Siap Diambil"])

        with tab1:
            for _, row in df[df['status_laundry'] == 'Diterima'].iterrows():
                kd = row['kode_nota'] if row['kode_nota'] else f"TRX/{row['id']}"
                with st.expander(f"Nota {kd} - Kak {row['nama']}"):
                    st.write(f"🏷️ **Layanan:** {row['layanan']} ({row['berat']})")
                    c_btn1, c_btn2 = st.columns(2)
                    with c_btn1:
                        if st.button("Mulai Cuci ➔", key=f"btn_cuci_{row['id']}"):
                            conn = get_connection()
                            c = conn.cursor()
                            c.execute("UPDATE transaksi SET status_laundry = 'Dicuci' WHERE id = ?", (row['id'],))
                            conn.commit()
                            conn.close()
                            st.rerun()
                    with c_btn2:
                        if st.button("🖨️ Print Label Tempel", key=f"btn_p_cuci_{row['id']}"):
                            show_print_dialog(row['id'])

        with tab2:
            for _, row in df[df['status_laundry'] == 'Dicuci'].iterrows():
                kd = row['kode_nota'] if row['kode_nota'] else f"TRX/{row['id']}"
                with st.expander(f"Nota {kd} - Kak {row['nama']}"):
                    st.write(f"🏷️ **Layanan:** {row['layanan']}")
                    
                    st.subheader("📸 Memotret/Upload Saat Pakaian Dijemur")
                    method_j = st.radio("Metode Ambil Foto Jemur:", ["Kamera HP / Web", "Upload File Foto"], key=f"rad_j_{row['id']}", horizontal=True)
                    
                    foto_jemur_file = None
                    if method_j == "Kamera HP / Web":
                        foto_jemur_file = st.camera_input("Ambil Foto Pakaian Dijemur", key=f"cam_j_{row['id']}")
                    else:
                        foto_jemur_file = st.file_uploader("Upload Foto Pakaian Dijemur", type=["jpg", "jpeg", "png"], key=f"upl_j_{row['id']}")

                    if st.button("Lanjut Setrika ➔ (Simpan Foto Jemur)", key=f"btn_strk_{row['id']}"):
                        img_b64_jemur = process_img_to_base64(foto_jemur_file)
                        conn = get_connection()
                        c = conn.cursor()
                        if img_b64_jemur:
                            c.execute("UPDATE transaksi SET status_laundry = 'Disetrika', foto_jemur = ? WHERE id = ?", (img_b64_jemur, row['id']))
                        else:
                            c.execute("UPDATE transaksi SET status_laundry = 'Disetrika' WHERE id = ?", (row['id'],))
                        conn.commit()
                        conn.close()
                        st.success("✅ Foto penjemuran tersimpan permanen & status diperbarui!")
                        st.rerun()

        with tab3:
            for _, row in df[df['status_laundry'] == 'Disetrika'].iterrows():
                kd = row['kode_nota'] if row['kode_nota'] else f"TRX/{row['id']}"
                with st.expander(f"Nota {kd} - Kak {row['nama']}"):
                    with st.form(key=f"form_finish_{row['id']}"):
                        jml_bungkus = st.number_input("Jumlah Bungkusan / Bal", min_value=1, step=1, value=1)
                        
                        st.subheader("📸 Memotret/Upload Setelah Pakaian Dilipat & Terbungkus")
                        method_l = st.radio("Metode Ambil Foto Lipat:", ["Kamera HP / Web", "Upload File Foto"], key=f"rad_l_{row['id']}", horizontal=True)
                        
                        foto_lipat_file = None
                        if method_l == "Kamera HP / Web":
                            foto_lipat_file = st.camera_input("Ambil Foto Pakaian Dilipat/Terbungkus", key=f"cam_l_{row['id']}")
                        else:
                            foto_lipat_file = st.file_uploader("Upload Foto Pakaian Dilipat/Terbungkus", type=["jpg", "jpeg", "png"], key=f"upl_l_{row['id']}")

                        if st.form_submit_button("💾 Selesai & Simpan Data"):
                            img_b64_lipat = process_img_to_base64(foto_lipat_file)
                            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            conn = get_connection()
                            c = conn.cursor()
                            if img_b64_lipat:
                                c.execute("UPDATE transaksi SET status_laundry = 'Selesai', jumlah_bungkus = ?, tgl_selesai = ?, foto_lipat = ? WHERE id = ?", (jml_bungkus, now_str, img_b64_lipat, row['id']))
                            else:
                                c.execute("UPDATE transaksi SET status_laundry = 'Selesai', jumlah_bungkus = ?, tgl_selesai = ? WHERE id = ?", (jml_bungkus, now_str, row['id']))
                            conn.commit()
                            conn.close()

                            st.session_state[f'wa_selesai_{row["id"]}'] = True
                            st.success("✅ Pakaian SELESAI dilipat & tersimpan!")
                            st.rerun()

                    # WA Kirim di luar form agar link dapat diklik langsung di HP
                    pesan_selesai_raw = (
                        f"Halo Kak *{row['nama']}*, laundry Anda sudah *SELESAI* & siap diambil! 🧺✨\n\n"
                        f"🧾 *No. Nota:* #{kd}\n"
                        f"📦 *Jumlah Bungkusan:* {row['jumlah_bungkus'] if row['jumlah_bungkus'] else 1} Bungkusan/Bal\n"
                        f"💰 *Sisa Pembayaran:* Rp {row['sisa']:,}\n\n"
                        f"Silakan datang ke *SM Laundry* untuk pengambilan ya Kak. Terima kasih! 🙏"
                    )
                    url_wa_selesai = create_wa_link(row['no_hp'], pesan_selesai_raw)
                    st.markdown(f"👉 [**📱 KIRIM NOTIFIKASI WA SELESAI KE PELANGGAN**]({url_wa_selesai})")

        with tab4:
            for _, row in df[df['status_laundry'] == 'Selesai'].iterrows():
                kd = row['kode_nota'] if row['kode_nota'] else f"TRX/{row['id']}"
                with st.expander(f"🟢 Nota {kd} - Kak {row['nama']} ({row['jumlah_bungkus']} BUNGKUS)"):
                    pesan_selesai_raw = (
                        f"Halo Kak *{row['nama']}*, mengingatkan kembali laundry Anda sudah *SELESAI* & siap diambil! 🧺✨\n\n"
                        f"🧾 *No. Nota:* #{kd}\n"
                        f"💰 *Sisa Pembayaran:* Rp {row['sisa']:,}\n\n"
                        f"Silakan datang ke *SM Laundry*. Terima kasih!"
                    )
                    url_wa_selesai = create_wa_link(row['no_hp'], pesan_selesai_raw)
                    st.markdown(f"👉 [**📱 KIRIM / RE-SEND WA NOTIFIKASI SELESAI**]({url_wa_selesai})")
                    
                    if st.button("🤝 Diserahkan ke Pelanggan", key=f"btn_ambil_{row['id']}"):
                        conn = get_connection()
                        c = conn.cursor()
                        c.execute("UPDATE transaksi SET status_laundry = 'Sudah Diambil', status_bayar = 'LUNAS', sisa = 0 WHERE id = ?", (row['id'],))
                        conn.commit()
                        conn.close()
                        st.rerun()

# ==========================================
# LAPORAN KEUANGAN (KHUSUS OWNER)
# ==========================================
elif menu == "💰 Laporan Keuangan":
    st.header("💰 Laporan Keuangan & Omset Transaksi (Khusus Owner)")
    
    conn = get_connection()
    df_all = pd.read_sql_query("SELECT id, kode_nota, tgl_transaksi, nama, no_hp, layanan, berat, total, bayar_dp, sisa, status_bayar, status_laundry FROM transaksi ORDER BY id DESC", conn)
    conn.close()

    if df_all.empty:
        st.info("ℹ️ Belum ada data transaksi untuk ditampilkan.")
    else:
        df_all['Kode Nota'] = df_all.apply(lambda r: r['kode_nota'] if r['kode_nota'] else f"TRX/{r['id']}", axis=1)
        df_all['tgl_dt'] = pd.to_datetime(df_all['tgl_transaksi'], errors='coerce')
        
        tab_harian, tab_mingguan, tab_bulanan, tab_semua = st.tabs(["📅 Laporan Harian", "🗓️ Laporan Mingguan", "📆 Laporan Bulanan", "📑 Semua Transaksi"])
        
        now = datetime.now()

        with tab_harian:
            st.subheader("📅 Laporan Keuangan Harian")
            tgl_pilih = st.date_input("Pilih Tanggal:", value=now.date(), key="filter_tgl_harian")
            
            df_harian = df_all[df_all['tgl_dt'].dt.date == tgl_pilih]
            
            omset_harian = df_harian['total'].sum() if not df_harian.empty else 0
            terbayar_harian = df_harian['bayar_dp'].sum() if not df_harian.empty else 0
            piutang_harian = df_harian['sisa'].sum() if not df_harian.empty else 0
            
            col_h1, col_h2, col_h3 = st.columns(3)
            col_h1.metric("💵 Total Omset", f"Rp {omset_harian:,}")
            col_h2.metric("✅ Kas Masuk (Lunas/DP)", f"Rp {terbayar_harian:,}")
            col_h3.metric("⚠️ Sisa Piutang (Belum Bayar)", f"Rp {piutang_harian:,}")
            
            if not df_harian.empty:
                st.dataframe(df_harian[['Kode Nota', 'tgl_transaksi', 'nama', 'layanan', 'berat', 'total', 'status_bayar', 'sisa', 'status_laundry']], use_container_width=True, hide_index=True)
            else:
                st.info("Tidak ada transaksi pada tanggal ini.")

        with tab_mingguan:
            st.subheader("🗓️ Laporan Keuangan Mingguan (7 Hari Terakhir)")
            
            tgl_mulai_minggu = now.date() - timedelta(days=7)
            df_mingguan = df_all[(df_all['tgl_dt'].dt.date >= tgl_mulai_minggu) & (df_all['tgl_dt'].dt.date <= now.date())]
            
            omset_mingguan = df_mingguan['total'].sum() if not df_mingguan.empty else 0
            terbayar_mingguan = df_mingguan['bayar_dp'].sum() if not df_mingguan.empty else 0
            piutang_mingguan = df_mingguan['sisa'].sum() if not df_mingguan.empty else 0
            
            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric("💵 Omset 7 Hari Terakhir", f"Rp {omset_mingguan:,}")
            col_m2.metric("✅ Kas Masuk", f"Rp {terbayar_mingguan:,}")
            col_m3.metric("⚠️ Sisa Piutang", f"Rp {piutang_mingguan:,}")
            
            if not df_mingguan.empty:
                st.dataframe(df_mingguan[['Kode Nota', 'tgl_transaksi', 'nama', 'layanan', 'berat', 'total', 'status_bayar', 'sisa', 'status_laundry']], use_container_width=True, hide_index=True)
            else:
                st.info("Tidak ada transaksi dalam 7 hari terakhir.")

        with tab_bulanan:
            st.subheader("📆 Laporan Keuangan Bulanan")
            
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                bulan_pilih = st.selectbox("Pilih Bulan:", range(1, 13), index=now.month - 1)
            with col_b2:
                tahun_pilih = st.number_input("Pilih Tahun:", min_value=2020, max_value=2030, value=now.year)
                
            df_bulanan = df_all[(df_all['tgl_dt'].dt.month == bulan_pilih) & (df_all['tgl_dt'].dt.year == tahun_pilih)]
            
            omset_bulanan = df_bulanan['total'].sum() if not df_bulanan.empty else 0
            terbayar_bulanan = df_bulanan['bayar_dp'].sum() if not df_bulanan.empty else 0
            piutang_bulanan = df_bulanan['sisa'].sum() if not df_bulanan.empty else 0
            
            col_bm1, col_bm2, col_bm3 = st.columns(3)
            col_bm1.metric(f"💵 Omset Bulan {bulan_pilih}/{tahun_pilih}", f"Rp {omset_bulanan:,}")
            col_bm2.metric("✅ Kas Masuk", f"Rp {terbayar_bulanan:,}")
            col_bm3.metric("⚠️ Sisa Piutang", f"Rp {piutang_bulanan:,}")
            
            if not df_bulanan.empty:
                st.dataframe(df_bulanan[['Kode Nota', 'tgl_transaksi', 'nama', 'layanan', 'berat', 'total', 'status_bayar', 'sisa', 'status_laundry']], use_container_width=True, hide_index=True)
            else:
                st.info(f"Tidak ada transaksi pada bulan {bulan_pilih}/{tahun_pilih}.")

        with tab_semua:
            st.subheader("📑 Keseluruhan Laporan Transaksi")
            st.metric("📈 Total Akumulasi Omset Semua", f"Rp {df_all['total'].sum():,}")
            st.dataframe(df_all[['Kode Nota', 'tgl_transaksi', 'nama', 'layanan', 'berat', 'total', 'status_bayar', 'sisa', 'status_laundry']], use_container_width=True, hide_index=True)

# ==========================================
# LAPORAN PELANGGAN
# ==========================================
elif menu == "👥 Laporan Pelanggan":
    st.header("👥 Kelola Pelanggan & Riwayat Transaksi")
    
    conn = get_connection()
    df_pelanggan = pd.read_sql_query("SELECT * FROM master_pelanggan ORDER BY nama ASC", conn)
    conn.close()

    if df_pelanggan.empty:
        st.info("ℹ️ Belum ada data pelanggan yang terdaftar.")
    else:
        tab_list_pel, tab_hist_pel = st.tabs(["📋 Daftar Master Pelanggan", "📜 Riwayat Transaksi Pelanggan"])
        
        with tab_list_pel:
            st.subheader("📋 Daftar Pelanggan Terdaftar")
            
            for idx, row in df_pelanggan.iterrows():
                pel_id = row['id']
                with st.expander(f"👤 {row['nama']} - 📞 {row['no_hp']} (Terdaftar: {row['created_at']})"):
                    with st.form(key=f"form_edit_pel_{pel_id}"):
                        c1, c2 = st.columns(2)
                        with c1:
                            p_nama = st.text_input("Nama Pelanggan", value=row['nama'])
                        with c2:
                            p_hp = st.text_input("No. WhatsApp", value=row['no_hp'])

                        col_p1, col_p2 = st.columns([1, 1])
                        with col_p1:
                            btn_update_pel = st.form_submit_button("💾 Simpan Perubahan")
                        with col_p2:
                            btn_delete_pel = st.form_submit_button("🗑️ Hapus Pelanggan", type="primary", disabled=(user_role != 'owner'))

                        if btn_update_pel:
                            conn = get_connection()
                            c = conn.cursor()
                            c.execute("UPDATE master_pelanggan SET nama = ?, no_hp = ? WHERE id = ?", (p_nama, p_hp, pel_id))
                            conn.commit()
                            conn.close()
                            st.success(f"✅ Data pelanggan {p_nama} berhasil diperbarui!")
                            st.rerun()

                        if btn_delete_pel:
                            if user_role == 'owner':
                                conn = get_connection()
                                c = conn.cursor()
                                c.execute("DELETE FROM master_pelanggan WHERE id = ?", (pel_id,))
                                conn.commit()
                                conn.close()
                                st.success(f"🗑️ Pelanggan {row['nama']} berhasil dihapus!")
                                st.rerun()
                            else:
                                st.error("❌ Hanya Owner yang diperbolehkan menghapus pelanggan.")

        with tab_hist_pel:
            st.subheader("📜 Cari Riwayat / History Transaksi Pelanggan")
            
            list_pel_options = [f"{row['nama']} ({row['no_hp']})" for _, row in df_pelanggan.iterrows()]
            selected_pel_option = st.selectbox("👤 Pilih Pelanggan:", list_pel_options)
            
            if selected_pel_option:
                sel_idx = list_pel_options.index(selected_pel_option)
                target_hp = df_pelanggan.iloc[sel_idx]['no_hp']
                target_nama = df_pelanggan.iloc[sel_idx]['nama']
                
                conn = get_connection()
                df_history = pd.read_sql_query("SELECT id, kode_nota, tgl_transaksi, layanan, berat, total, status_bayar, sisa, status_laundry FROM transaksi WHERE no_hp = ? ORDER BY id DESC", conn, params=(target_hp,))
                conn.close()
                
                if df_history.empty:
                    st.warning(f"Pelanggan **{target_nama}** belum memiliki riwayat transaksi.")
                else:
                    df_history['Kode Nota'] = df_history.apply(lambda r: r['kode_nota'] if r['kode_nota'] else f"TRX/{r['id']}", axis=1)
                    
                    total_transaksi = len(df_history)
                    total_pembelian = df_history['total'].sum()
                    sisa_piutang = df_history['sisa'].sum()
                    
                    m1, m2, m3 = st.columns(3)
                    m1.metric("📦 Total Transaksi", f"{total_transaksi} Kali")
                    m2.metric("💰 Total Belanja (Pengeluaran)", f"Rp {total_pembelian:,}")
                    m3.metric("⚠️ Sisa Piutang/Tunggakan", f"Rp {sisa_piutang:,}")
                    
                    st.markdown("---")
                    st.markdown(f"#### 📄 Daftar Nota Transaksi Kak {target_nama}:")
                    
                    df_display_hist = df_history[[
                        'Kode Nota', 'tgl_transaksi', 'layanan', 'berat', 'total', 'status_bayar', 'sisa', 'status_laundry'
                    ]].rename(columns={
                        'tgl_transaksi': 'Tanggal Masuk',
                        'layanan': 'Layanan',
                        'berat': 'Jumlah/Berat',
                        'total': 'Total Tagihan',
                        'status_bayar': 'Status Bayar',
                        'sisa': 'Sisa Tagihan',
                        'status_laundry': 'Status Produksi'
                    })
                    
                    st.dataframe(df_display_hist, use_container_width=True, hide_index=True)

# ==========================================
# PENGATURAN MASTER DATA (KHUSUS OWNER)
# ==========================================
elif menu == "⚙️ Pengaturan Master Data":
    st.header("⚙️ Pengaturan Master Data & Akun Pengguna")
    tab_bt, tab_usr, tab_l, tab_p, tab_pel = st.tabs(["🛜 Koneksi Printer Bluetooth", "👥 Kelola Akun Pengguna", "🏷️ Master Layanan", "🌸 Master Parfum", "👥 Master Pelanggan"])

    with tab_bt:
        st.subheader("📱 Pengaturan & Tes Koneksi Printer Thermal Bluetooth")
        st.write("Pastikan **Bluetooth** & **Lokasi (GPS)** pada perangkat HP/Perangkat Kasir Anda aktif. Hubungkan printer thermal via menu di bawah:")
        
        test_bts_data = "SM LAUNDRY TEST PRINTER\\nJl. Maritim 28 Socah Bangkalan\\n--------------------------------\\nKoneksi Bluetooth Berhasil!\\n--------------------------------"
        st.components.v1.html(
            f"""{JS_BLUETOOTH_PRINT}
            <div style="text-align:center; padding: 20px; border: 1px dashed #28a745; border-radius: 10px;">
                <h4>Sambungkan Printer Bluetooth Anda</h4>
                <p style="font-size: 12px; color: #555;">Gunakan Google Chrome / Microsoft Edge di Android / Windows untuk hasil terbaik.</p>
                <button onclick="printBluetooth('{test_bts_data}')" style="padding: 10px 20px; background-color:#28a745; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">
                    🔍 Cari & Tes Print Printer Bluetooth
                </button>
            </div>""", height=180
        )

    with tab_usr:
        st.subheader("➕ Tambah Akun Pengguna / Pegawai Baru")
        
        with st.form("form_add_user", clear_on_submit=True):
            col_u1, col_u2 = st.columns(2)
            with col_u1:
                u_username = st.text_input("Username*", placeholder="Contoh: kasir2 / rina")
                u_password = st.text_input("Password*", type="password")
            with col_u2:
                u_nama = st.text_input("Nama Lengkap Staf*", placeholder="Contoh: Rina M")
                u_role = st.selectbox("Akses Role*", ["pegawai", "owner"])

            if st.form_submit_button("💾 Simpan Pengguna Baru"):
                if not u_username.strip() or not u_password.strip() or not u_nama.strip():
                    st.error("❌ Username, Password, dan Nama Wajib Diisi!")
                else:
                    conn = get_connection()
                    c = conn.cursor()
                    try:
                        c.execute("INSERT INTO master_user (username, password, nama_user, role) VALUES (?, ?, ?, ?)",
                                  (u_username.strip().lower(), u_password.strip(), u_nama.strip(), u_role))
                        conn.commit()
                        st.success(f"✅ Akun {u_nama} ({u_role}) berhasil ditambahkan!")
                    except sqlite3.IntegrityError:
                        st.error("❌ Username tersebut sudah terpakai! Gunakan username lain.")
                    conn.close()
                    st.rerun()

        st.divider()
        st.subheader("📋 Daftar Pengguna Sistem SM Laundry")
        
        conn = get_connection()
        df_users = pd.read_sql_query("SELECT id, username, password, nama_user, role FROM master_user ORDER BY id ASC", conn)
        conn.close()

        if not df_users.empty:
            for idx, u_row in df_users.iterrows():
                u_id = u_row['id']
                with st.expander(f"👤 {u_row['nama_user']} (@{u_row['username']}) - Role: {u_row['role'].upper()}"):
                    with st.form(key=f"form_edit_user_{u_id}"):
                        eu1, eu2 = st.columns(2)
                        with eu1:
                            e_u_nama = st.text_input("Nama Pengguna", value=u_row['nama_user'])
                            e_u_username = st.text_input("Username", value=u_row['username'])
                        with eu2:
                            e_u_password = st.text_input("Password Baru", value=u_row['password'])
                            e_u_role = st.selectbox("Role Akses", ["pegawai", "owner"], index=0 if u_row['role'] == "pegawai" else 1)

                        btn_c1, btn_c2 = st.columns(2)
                        with btn_c1:
                            btn_save_u = st.form_submit_button("💾 Simpan Perubahan Akun")
                        with btn_c2:
                            btn_del_u = st.form_submit_button("🗑️ Hapus Akun Ini", type="primary")

                        if btn_save_u:
                            conn = get_connection()
                            c = conn.cursor()
                            c.execute("UPDATE master_user SET username = ?, password = ?, nama_user = ?, role = ? WHERE id = ?",
                                      (e_u_username.strip().lower(), e_u_password.strip(), e_u_nama.strip(), e_u_role, u_id))
                            conn.commit()
                            conn.close()
                            st.success("✅ Informasi Akun Berhasil Diperbarui!")
                            st.rerun()

                        if btn_del_u:
                            if u_id == st.session_state["user_info"]["id"]:
                                st.error("❌ Anda tidak bisa menghapus akun yang sedang Anda gunakan saat ini!")
                            else:
                                conn = get_connection()
                                c = conn.cursor()
                                c.execute("DELETE FROM master_user WHERE id = ?", (u_id,))
                                conn.commit()
                                conn.close()
                                st.success(f"🗑️ Akun {u_row['nama_user']} telah dihapus!")
                                st.rerun()

    with tab_l:
        st.subheader("➕ Tambah Layanan Baru / Unik")
        
        conn = get_connection()
        df_existing_layanan = pd.read_sql_query("SELECT * FROM master_layanan ORDER BY id DESC", conn)
        existing_kategori = df_existing_layanan['kategori'].unique().tolist() if not df_existing_layanan.empty else ["Cuci Kiloan", "Cuci Satuan"]
        conn.close()

        option_kategori = existing_kategori + ["+ Buat Kategori Baru..."]
        kat_choice = st.selectbox("Pilih Kategori", option_kategori)
        
        if kat_choice == "+ Buat Kategori Baru...":
            kategori_input_val = st.text_input("Kategori Baru*", placeholder="Misal: Sepatu / Karpet / Helm")
        else:
            kategori_input_val = kat_choice

        with st.form("form_tambah_layanan", clear_on_submit=True):
            col_l1, col_l2 = st.columns(2)
            
            with col_l1:
                nama_layanan_input = st.text_input("Nama Layanan*", placeholder="Misal: Cuci Shoes Sneaker / Karpet Masjid")
                tipe_input = st.selectbox("Tipe Layanan*", ["Biasa", "Express", "Kilat", "Super Fast", "Khusus"])

            with col_l2:
                durasi_jam_input = st.number_input("Estimasi Pengerjaan (Jam)*", min_value=1, value=24, step=1)
                durasi_teks_input = st.text_input("Teks Durasi*", value=f"{durasi_jam_input} Jam", placeholder="Misal: 1 Hari / 6 Jam")
                harga_input = st.number_input("Harga per Satuan (Rp)*", min_value=500, value=10000, step=1000)
                satuan_input = st.selectbox("Satuan Hitung*", ["Kg", "Pcs", "Pasang", "Meter", "Lembar", "Set"])

            if st.form_submit_button("💾 Simpan Layanan Baru"):
                final_kategori = kategori_input_val.strip() if kategori_input_val else ""
                
                if not final_kategori or final_kategori == "+ Buat Kategori Baru...":
                    st.error("❌ Nama Kategori Baru wajib diisi!")
                elif not nama_layanan_input.strip():
                    st.error("❌ Nama Layanan wajib diisi!")
                else:
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute('''INSERT INTO master_layanan (kategori, nama_layanan, tipe, durasi, durasi_jam, harga, satuan)
                                 VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                              (final_kategori, nama_layanan_input.strip(), tipe_input, durasi_teks_input.strip(), durasi_jam_input, harga_input, satuan_input))
                    conn.commit()
                    conn.close()
                    st.success(f"✅ Layanan **{nama_layanan_input}** dengan Kategori **{final_kategori}** berhasil ditambahkan!")
                    st.rerun()

        st.divider()
        st.subheader("📋 Daftar Layanan (Kelola / Edit / Hapus)")

        if df_existing_layanan.empty:
            st.info("Belum ada data layanan master.")
        else:
            for idx, row in df_existing_layanan.iterrows():
                id_lay = row['id']
                label_lay = f"[{row['kategori']}] {row['nama_layanan']} - {row['tipe']} ({row['durasi']}) | Rp {row['harga']:,}/{row['satuan']}"
                
                with st.expander(label_lay):
                    with st.form(key=f"form_edit_lay_{id_lay}"):
                        ce1, ce2 = st.columns(2)
                        with ce1:
                            m_kategori = st.text_input("Kategori", value=row['kategori'])
                            m_nama = st.text_input("Nama Layanan", value=row['nama_layanan'])
                            m_tipe = st.text_input("Tipe Layanan", value=row['tipe'])
                        with ce2:
                            m_durasi_jam = st.number_input("Durasi (Jam)", value=int(row['durasi_jam'] if pd.notnull(row['durasi_jam']) else 24), min_value=1)
                            m_durasi_txt = st.text_input("Teks Durasi", value=row['durasi'])
                            m_harga = st.number_input("Harga (Rp)", value=int(row['harga']), step=500)
                            m_satuan = st.text_input("Satuan", value=row['satuan'])

                        col_sub1, col_sub2 = st.columns([1, 1])
                        with col_sub1:
                            btn_update = st.form_submit_button("💾 Simpan Perubahan")
                        with col_sub2:
                            btn_delete = st.form_submit_button("🗑️ Hapus Layanan Ini", type="primary")

                        if btn_update:
                            conn = get_connection()
                            c = conn.cursor()
                            c.execute('''UPDATE master_layanan SET kategori=?, nama_layanan=?, tipe=?, durasi=?, durasi_jam=?, harga=?, satuan=? WHERE id=?''',
                                      (m_kategori, m_nama, m_tipe, m_durasi_txt, m_durasi_jam, m_harga, m_satuan, id_lay))
                            conn.commit()
                            conn.close()
                            st.success("✅ Master layanan berhasil diperbarui!")
                            st.rerun()

                        if btn_delete:
                            conn = get_connection()
                            c = conn.cursor()
                            c.execute("DELETE FROM master_layanan WHERE id=?", (id_lay,))
                            conn.commit()
                            conn.close()
                            st.success("🗑️ Layanan berhasil dihapus!")
                            st.rerun()

    with tab_p:
        st.subheader("🌸 Kelola Master Parfum")
        
        conn = get_connection()
        df_parfum = pd.read_sql_query("SELECT * FROM master_parfum ORDER BY id DESC", conn)
        conn.close()

        with st.form("form_tambah_parfum", clear_on_submit=True):
            new_parfum = st.text_input("Tambah Aromaterapi / Parfum Baru*", placeholder="Misal: Vanilla / Akasia")
            if st.form_submit_button("➕ Tambah Parfum"):
                if new_parfum.strip():
                    conn = get_connection()
                    c = conn.cursor()
                    try:
                        c.execute("INSERT INTO master_parfum (nama_parfum) VALUES (?)", (new_parfum.strip(),))
                        conn.commit()
                        st.success("✅ Varian Parfum baru berhasil disimpan!")
                    except:
                        st.error("❌ Nama Parfum sudah ada!")
                    conn.close()
                    st.rerun()

        st.divider()
        st.write("📋 **Daftar Parfum Saat Ini:**")
        if not df_parfum.empty:
            for _, p_row in df_parfum.iterrows():
                cp1, cp2 = st.columns([3, 1])
                with cp1:
                    st.write(f"• **{p_row['nama_parfum']}**")
                with cp2:
                    if st.button("🗑️ Hapus", key=f"del_prf_{p_row['id']}"):
                        conn = get_connection()
                        c = conn.cursor()
                        c.execute("DELETE FROM master_parfum WHERE id=?", (p_row['id'],))
                        conn.commit()
                        conn.close()
                        st.rerun()

    with tab_pel:
        st.subheader("👥 Edit & Hapus Master Pelanggan")
        
        conn = get_connection()
        df_pel = pd.read_sql_query("SELECT * FROM master_pelanggan ORDER BY nama ASC", conn)
        conn.close()

        if df_pel.empty:
            st.info("Belum ada data pelanggan master.")
        else:
            for idx, p_row in df_pel.iterrows():
                pel_id = p_row['id']
                with st.expander(f"👤 {p_row['nama']} ({p_row['no_hp']})"):
                    with st.form(key=f"form_master_pel_{pel_id}"):
                        c1, c2 = st.columns(2)
                        with c1:
                            m_p_nama = st.text_input("Nama Pelanggan", value=p_row['nama'])
                        with c2:
                            m_p_hp = st.text_input("No. WhatsApp", value=p_row['no_hp'])

                        col_m_p1, col_m_p2 = st.columns([1, 1])
                        with col_m_p1:
                            btn_update_mp = st.form_submit_button("💾 Simpan Perubahan")
                        with col_m_p2:
                            btn_delete_mp = st.form_submit_button("🗑️ Hapus Pelanggan Ini", type="primary")

                        if btn_update_mp:
                            conn = get_connection()
                            c = conn.cursor()
                            c.execute("UPDATE master_pelanggan SET nama = ?, no_hp = ? WHERE id = ?", (m_p_nama, m_p_hp, pel_id))
                            conn.commit()
                            conn.close()
                            st.success("✅ Master data pelanggan berhasil diperbarui!")
                            st.rerun()

                        if btn_delete_mp:
                            conn = get_connection()
                            c = conn.cursor()
                            c.execute("DELETE FROM master_pelanggan WHERE id = ?", (pel_id,))
                            conn.commit()
                            conn.close()
                            st.success("🗑️ Data pelanggan berhasil dihapus!")
                            st.rerun()
