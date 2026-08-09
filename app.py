import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import urllib.parse

# 1. CONFIGURACIÓN DE LA BASE DE DATOS
def conectar_db():
conn = sqlite3.connect("sistema_emprendimiento.db", check_same_thread=False)
cursor = conn.cursor()

# Crear tablas si no existen
cursor.execute("""
CREATE TABLE IF NOT EXISTS clientes (
id INTEGER PRIMARY KEY AUTOINCREMENT,
nombre TEXT, telefono TEXT
)""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS productos (
id INTEGER PRIMARY KEY AUTOINCREMENT,
nombre TEXT, stock INTEGER, costo REAL, precio REAL
)""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS ordenes (
id INTEGER PRIMARY KEY AUTOINCREMENT,
cliente_id INTEGER, fecha TEXT, metodo_pago TEXT, total REAL
)""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS detalles_orden (
id INTEGER PRIMARY KEY AUTOINCREMENT,
orden_id INTEGER, producto_id INTEGER, cantidad INTEGER, precio_unitario REAL
)""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS gastos (
id INTEGER PRIMARY KEY AUTOINCREMENT,
tipo TEXT, descripcion TEXT, monto REAL, fecha TEXT
)""")
conn.commit()
return conn

conn = conectar_db()

# 2. INTERFAZ Y ROLES DE USUARIO
st.set_page_config(page_title="EmprendeApp", layout="wide", page_icon="📈")
st.title("🚀 EmprendeApp: Gestión Integral")

# Selección de Rol en la barra lateral
rol = st.sidebar.selectbox("Selecciona tu Rol:", ["👤 Empleado (Ventas)", "👑 Administrador (Dueño)"])

# --- MÓDULO 1: REGISTRO DE VENTAS (Disponible para Empleados y Admin) ---
if rol in ["👤 Empleado (Ventas)", "👑 Administrador (Dueño)"]:
st.header("🛒 Registrar Nueva Venta")

# Sección Cliente
st.subheader("1. Datos del Cliente")
clientes_df = pd.read_sql_query("SELECT * FROM clientes", conn)

col1, col2 = st.columns(2)
with col1:
if not clientes_df.empty:
opciones_clientes = {f"{r['nombre']} ({r['telefono']})": r['id'] for _, r in clientes_df.iterrows()}
cliente_seleccionado = st.selectbox("Seleccionar Cliente Existente", list(opciones_clientes.keys()))
cliente_id = opciones_clientes[cliente_seleccionado]
else:
st.info("No hay clientes registrados.")
cliente_id = None

with col2:
with st.expander("➕ Registrar Nuevo Cliente"):
nuevo_nombre = st.text_input("Nombre Completo")
nuevo_tel = st.text_input("WhatsApp (Ej: 50761234567)")
if st.button("Guardar Cliente"):
if nuevo_nombre and nuevo_tel:
cursor = conn.cursor()
cursor.execute("INSERT INTO clientes (nombre, telefono) VALUES (?, ?)", (nuevo_nombre, nuevo_tel))
conn.commit()
st.success("¡Cliente guardado! Recarga la página.")
else:
st.error("Llena todos los campos.")

# Sección Productos
st.subheader("2. Carrito de Compras")
productos_df = pd.read_sql_query("SELECT * FROM productos WHERE stock > 0", conn)

if productos_df.empty:
st.warning("No hay productos en inventario. El Administrador debe agregarlos.")
elif cliente_id is None:
st.warning("Registra o selecciona un cliente para continuar.")
else:
opciones_prod = {f"{r['nombre']} (Stock: {r['stock']} | ${r['precio']})": r['id'] for _, r in productos_df.iterrows()}
productos_seleccionados = st.multiselect("Selecciona los productos:", list(opciones_prod.keys()))

cantidades = {}
total_venta = 0.0
detalles_items = []

if productos_seleccionados:
for prod in productos_seleccionados:
p_id = opciones_prod[prod]
info_prod = productos_df[productos_df['id'] == p_id].iloc[0]
cant = st.number_input(f"Cantidad para {info_prod['nombre']}", min_value=1, max_value=int(info_prod['stock']), value=1, key=f"cant_{p_id}")
cantidades[p_id] = cant
subtotal = cant * info_prod['precio']
total_venta += subtotal
detalles_items.append((p_id, cant, info_prod['precio'], info_prod['nombre']))

st.metric("Total a Pagar", f"${total_venta:,.2f}")
metodo_pago = st.selectbox("Forma de Pago:", ["Efectivo", "Transferencia Bancaria", "Pago Móvil", "Tarjeta"])

if st.button("🔥 Finalizar Orden y Generar Ticket"):
cursor = conn.cursor()
fecha_hoy = datetime.now().strftime("%Y-%m-%d")

# Guardar Orden
cursor.execute("INSERT INTO ordenes (cliente_id, fecha, metodo_pago, total) VALUES (?, ?, ?, ?)",
(cliente_id, fecha_hoy, metodo_pago, total_venta))
orden_id = cursor.lastrowid

# Guardar detalles y restar inventario
text_ticket = f"*ORDEN NÚMERO {orden_id}*\n\n"
for p_id, cant, precio, nombre_p in detalles_items:
cursor.execute("INSERT INTO detalles_orden (orden_id, producto_id, cantidad, precio_unitario) VALUES (?, ?, ?, ?)",
(orden_id, p_id, cant, precio))
cursor.execute("UPDATE productos SET stock = stock - ? WHERE id = ?", (cant, p_id))
text_ticket += f"• {nombre_p} x{cant} = ${cant*precio:,.2f}\n"

conn.commit()

# Generar enlace de WhatsApp
info_c = pd.read_sql_query(f"SELECT * FROM clientes WHERE id = {cliente_id}", conn).iloc[0]
text_ticket += f"\n*Total:* ${total_venta:,.2f}\n*Método:* {metodo_pago}\n\n¡Gracias por tu compra!"
texto_url = urllib.parse.quote(text_ticket)
url_whatsapp = f"https://whatsapp.com{info_c['telefono']}&text={texto_url}"

st.success(f"✅ ¡Orden #{orden_id} procesada con éxito!")
st.link_button("💬 Enviar Ticket por WhatsApp", url_whatsapp)

# --- MÓDULO 2: PANEL ADMINISTRADOR (Solo dueños) ---
if rol == "👑 Administrador (Dueño)":
st.markdown("---")
st.header("📊 Panel de Control y Finanzas (Solo Admin)")

fecha_filtro = st.date_input("Ver día:", datetime.now()).strftime("%Y-%m-%d")

# Cálculos Financieros mediante consultas SQL directas
cursor = conn.cursor()

# 1. Total Vendido
cursor.execute("SELECT SUM(total) FROM ordenes WHERE fecha = ?", (fecha_filtro,))
total_vendido = cursor.fetchone()[0] or 0.0

# 2. Total Consumido (Costo de lo vendido)
cursor.execute("""
SELECT SUM(d.cantidad * p.costo)
FROM detalles_orden d
JOIN productos p ON d.producto_id = p.id
JOIN ordenes o ON d.orden_id = o.id
WHERE o.fecha = ?
""", (fecha_filtro,))
total_consumido = cursor.fetchone()[0] or 0.0

# 3. Total Gastado
cursor.execute("SELECT SUM(monto) FROM gastos WHERE fecha = ?", (fecha_filtro,))
total_gastado = cursor.fetchone()[0] or 0.0

ganancia_neta = total_vendido - total_consumido - total_gastado

# Despliegue de Indicadores
c1, c2, c3, c4 = st.columns(4)
c1.metric("💰 Total Vendido", f"${total_vendido:,.2f}")
c2.metric("📉 Costo Consumido", f"${total_consumido:,.2f}")
c3.metric("💸 Gastos/Compras", f"${total_gastado:,.2f}")
c4.metric("📈 Utilidad Neta", f"${ganancia_neta:,.2f}", delta=f"${ganancia_neta:,.2f}")

# Gestión de Inventario y Gastos en pestañas
tab1, tab2, tab3 = st.tabs(["📦 Inventario", "🧾 Registrar Gasto", "📋 Historial de Órdenes"])

with tab1:
st.subheader("Carga de Productos")
with st.form("nuevo_producto"):
p_nom = st.text_input("Nombre del Artículo")
p_stock = st.number_input("Cantidad Inicial", min_value=0, step=1)
p_costo = st.number_input("Costo Unitario de Compra ($)", min_value=0.0, step=0.01)
p_precio = st.number_input("Precio de Venta al Público ($)", min_value=0.0, step=0.01)

if st.form_submit_button("Añadir al Inventario"):
if p_nom:
cursor.execute("INSERT INTO productos (nombre, stock, costo, precio) VALUES (?, ?, ?, ?)",
(p_nom, p_stock, p_costo, p_precio))
conn.commit()
st.success(f"{p_nom} agregado correctamente.")
else:
st.error("El nombre es obligatorio.")

st.subheader("Stock Actual")
st.dataframe(pd.read_sql_query("SELECT id, nombre, stock, costo, precio FROM productos", conn), use_container_width=True)

with tab2:
st.subheader("Registrar Compras Directas o Gastos fijos")
with st.form("nuevo_gasto"):
g_tipo = st.selectbox("Tipo", ["Gasto Operativo (Servicios, Alquiler)", "Compra Extra de Mercancía"])
g_desc = st.text_input("Descripción breve")
g_monto = st.number_input("Monto total gastado ($)", min_value=0.0, step=0.01)

if st.form_submit_button("Guardar Egreso"):
if g_desc and g_monto > 0:
cursor.execute("INSERT INTO gastos (tipo, descripcion, monto, fecha) VALUES (?, ?, ?, ?)",
(g_tipo, g_desc, g_monto, fecha_filtro))
conn.commit()
st.success("Gasto registrado exitosamente.")
else:
st.error("Verifica los datos del egreso.")

with tab3:
st.subheader("Monitoreo de Transacciones")
st.dataframe(pd.read_sql_query("SELECT * FROM ordenes", conn), use_container_width=True)
