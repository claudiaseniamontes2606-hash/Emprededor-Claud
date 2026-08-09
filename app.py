import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import urllib.parse

# 1. CONFIGURACIÓN DE LA BASE DE DATOS
def conectar_db():
    conn = sqlite3.connect("sistema_emprendimiento.db", check_same_thread=False)
    cursor = conn.cursor()
    
    # Crear tablas e incorporar columna de imagen si no existe
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT, telefono TEXT
    )""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS productos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT, stock INTEGER, costo REAL, precio REAL, imagen_url TEXT
    )""")
    
    # Asegurar compatibilidad agregando la columna por si ya existía la tabla vieja sin imagen
    try:
        cursor.execute("ALTER TABLE productos ADD COLUMN imagen_url TEXT")
    except sqlite3.OperationalError:
        pass # La columna ya existía

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

# 2. CONFIGURACIÓN VISUAL E IDENTIDAD (LOGO)
st.set_page_config(page_title="EmprendeApp Pro", layout="wide", page_icon="📈")

# Sección del Logotipo del Negocio en la Barra Lateral
st.sidebar.markdown("### 🏬 Identidad del Negocio")
logo_url = st.sidebar.text_input("Enlace URL de tu Logotipo:",
    value="https://flaticon.com",
    help="Pega aquí el enlace de la imagen de tu logo subida a internet")

if logo_url:
    st.sidebar.image(logo_url, width=120)

st.title("🚀 EmprendeApp Pro: Control Total")

# Selección de Rol
rol = st.sidebar.selectbox("Selecciona tu Rol:", ["👤 Empleado (Ventas)", "👑 Administrador (Dueño)"])

# --- MÓDULO 1: REGISTRO DE VENTAS ---
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

    # Sección Productos con Catálogo Visual
    st.subheader("2. Carrito de Compras e Inventario")
    productos_df = pd.read_sql_query("SELECT * FROM productos WHERE stock > 0", conn)
    
    if productos_df.empty:
        st.warning("No hay productos en inventario con existencias. El Administrador debe agregarlos en su panel.")
    elif cliente_id is None:
        st.warning("Registra o selecciona un cliente para continuar.")
    else:
        # Mostrar catálogo visual con fotos en cuadrícula antes de elegir
        st.markdown("**📸 Catálogo Visual de Artículos Disponibles:**")
        cols_catalogo = st.columns(4)
        for idx, row in productos_df.iterrows():
            with cols_catalogo[idx % 4]:
                img_p = row['imagen_url'] if row['imagen_url'] else "https://flaticon.com"
                st.image(img_p, use_container_width=True)
                st.markdown(f"**{row['nombre']}**\n\n💰 Precio: ${row['precio']:.2f}\n\n📦 Stock: {row['stock']} uds")
        
        st.markdown("---")
        # Selección del carrito
        opciones_prod = {f"{r['nombre']} (Stock: {r['stock']} | ${r['precio']})": r['id'] for _, r in productos_df.iterrows()}
        productos_seleccionados = st.multiselect("Selecciona los productos para la orden:", list(opciones_prod.keys()))
        
        cantidades = {}
        total_venta = 0.0
        detalles_items = []
        
        if productos_seleccionados:
            for prod in productos_seleccionados:
                p_id = opciones_prod[prod]
                # Buscar la fila correspondiente en vez de usar .iloc directo que fallaba por índice
                info_prod = productos_df[productos_df['id'] == p_id].iloc[0]
                cant = st.number_input(f"Cantidad para {info_prod['nombre']}", min_value=1, max_value=int(info_prod['stock']), value=1, key=f"cant_{p_id}")
                cantidades[p_id] = cant
                subtotal = cant * info_prod['precio']
                total_venta += subtotal
                detalles_items.append((p_id, cant, info_prod['precio'], info_prod['nombre']))
                
            st.metric("Total a Pagar", f"${total_venta:,.2f}")
            
            # NUEVOS MÉTODOS DE PAGO SOLICITADOS
            metodo_pago = st.selectbox("Forma de Pago:", ["Yappy 🌟", "Cuentas por Cobrar 📝", "Efectivo 💵", "Transferencia Bancaria 🏦", "Tarjeta 💳"])
            
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
                text_ticket += f"\n*Total:* ${total_venta:,.2f}\n*Método:* {metodo_pago}\n\n¡Gracias por tu confianza!"
                texto_url = urllib.parse.quote(text_ticket)
                url_whatsapp = f"https://whatsapp.com{info_c['telefono']}&text={texto_url}"
                
                st.success(f"✅ ¡Orden #{orden_id} procesada con éxito!")
                
                # Mostrar el Ticket en la interfaz
                st.text_area("📋 Copia del Ticket Emitido:", value=text_ticket, height=180)
                st.link_button("💬 Enviar Ticket por WhatsApp", url_whatsapp)

# --- MÓDULO 2: PANEL ADMINISTRADOR ---
if rol == "👑 Administrador (Dueño)":
    st.markdown("---")
    st.header("📊 Panel de Control y Finanzas (Solo Admin)")
    
    fecha_filtro = st.date_input("Ver día:", datetime.now()).strftime("%Y-%m-%d")
    
    cursor = conn.cursor()
    
    # 1. Total Vendido
    cursor.execute("SELECT SUM(total) FROM ordenes WHERE fecha = ?", (fecha_filtro,))
    res_v = cursor.fetchone()[0]
    total_vendido = res_v if res_v is not None else 0.0
    
    # 2. Total Consumido
    cursor.execute("""
        SELECT SUM(d.cantidad * p.costo)
        FROM detalles_orden d
        JOIN productos p ON d.producto_id = p.id
        JOIN ordenes o ON d.orden_id = o.id
        WHERE o.fecha = ?
    """, (fecha_filtro,))
    res_c = cursor.fetchone()[0]
    total_consumido = res_c if res_c is not None else 0.0
    
    # 3. Total Gastado
    cursor.execute("SELECT SUM(monto) FROM gastos WHERE fecha = ?", (fecha_filtro,))
    res_g = cursor.fetchone()[0]
    total_gastado = res_g if res_g is not None else 0.0
    
    ganancia_neta = total_vendido - total_consumido - total_gastado
    
    # Despliegue de Indicadores Financieros
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Total Vendido", f"${total_vendido:,.2f}")
    c2.metric("📉 Costo Consumido", f"${total_consumido:,.2f}")
    c3.metric("💸 Gastos/Compras", f"${total_gastado:,.2f}")
    c4.metric("📈 Utilidad Neta", f"${ganancia_neta:,.2f}", delta=f"${ganancia_neta:,.2f}")
    
    # Gestión en pestañas
    tab1, tab2, tab3 = st.tabs(["📦 Inventario Avanzado", "🧾 Registrar Gasto", "📋 Historial de Órdenes"])
    
    with tab1:
        st.subheader("Carga de Productos con Foto")
        with st.form("nuevo_producto"):
            p_nom = st.text_input("Nombre del Artículo")
            p_stock = st.number_input("Cantidad Inicial en Stock", min_value=0, step=1)
            p_costo = st.number_input("Costo de Compra ($)", min_value=0.0, step=0.01)
