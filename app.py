import streamlit as st
import pandas as pd
import plotly.express as px
import networkx as nx
from pyvis.network import Network
import streamlit.components.v1 as components
import os

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN VISUAL
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Observatorio Putumayo",
    page_icon="🇨🇴",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS para Tarjetas y Estilo
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-left: 5px solid #FF4B4B;
        padding: 15px;
        border-radius: 5px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
        margin-bottom: 10px;
    }
    .metric-title { color: #6c757d; font-size: 0.9rem; font-weight: bold; text-transform: uppercase; }
    .metric-value { color: #212529; font-size: 1.8rem; font-weight: 700; }
    .metric-sub { color: #198754; font-size: 0.8rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; border-radius: 4px 4px 0px 0px; gap: 1px; }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. CARGA DE DATOS
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
    rutas_posibles = ["data/contratos_putumayo.csv", "contratos_putumayo.csv"]
    ruta_encontrada = next((r for r in rutas_posibles if os.path.exists(r)), None)
    
    if ruta_encontrada:
        df = pd.read_csv(ruta_encontrada)
        
        # Limpieza
        if 'valor_del_contrato' in df.columns:
            df['valor_del_contrato'] = pd.to_numeric(df['valor_del_contrato'], errors='coerce').fillna(0)
        
        if 'fecha_de_firma' in df.columns:
            df['fecha_de_firma'] = pd.to_datetime(df['fecha_de_firma'], errors='coerce')

        if 'ciudad' in df.columns:
            df['ciudad'] = df['ciudad'].astype(str).str.upper().str.strip()
            df['ciudad'] = df['ciudad'].replace({
                'PUERTO ASIS': 'PUERTO ASÍS', 'LEGUIZAMO': 'PUERTO LEGUÍZAMO', 'VALLE DEL GUAMUEZ': 'LA HORMIGA'
            })
        
        if 'nombre_entidad' in df.columns:
            df['nombre_entidad'] = df['nombre_entidad'].astype(str).str.upper().str.strip()

        # CLASIFICADOR
        def discriminar_entidad(row):
            entidad = row['nombre_entidad'].replace('Á','A').replace('É','E').replace('Í','I').replace('Ó','O').replace('Ú','U')
            ciudad = row['ciudad']
            
            if "NARIÑO" in entidad or "CAUCA" in entidad or "HUILA" in entidad or "CUNDINAMARCA" in entidad or "BOGOTA" in entidad:
                return "⚠️ ENTIDADES EXTERNAS", entidad

            if ("GOBERNACION" in entidad or "DEPARTAMENTO DEL PUTUMAYO" in entidad) and "INDERCULTURA" not in entidad:
                return "🚨 GOBERNACIÓN", "Gobernación del Putumayo"
            
            es_local = ("ALCALDIA" in entidad or "MUNICIPIO" in entidad or "CONCEJO" in entidad)
            excepcion = ("PERSONERIA" in entidad or "INSTITUCION" in entidad or "CENTRO" in entidad or "EMPRESA" in entidad or "AGUAS" in entidad or "TRANSPORTE" in entidad)

            if es_local and not excepcion:
                if "MOCOA" in ciudad or "MOCOA" in entidad: return "🏛️ ALCALDÍAS MUNICIPALES", "Alcaldía de MOCOA (Incl. Concejo)"
                return "🏛️ ALCALDÍAS MUNICIPALES", f"Alcaldía de {ciudad}"
            
            elif "HOSPITAL" in entidad or "E.S.E" in entidad or "ESE " in entidad:
                return "🏥 HOSPITALES / SALUD", entidad.replace("EMPRESA SOCIAL DEL ESTADO", "").replace("HOSPITAL", "HOSP.").strip()
            
            elif "INSTITUCION" in entidad or "CENTRO EDUCATIVO" in entidad or "SENA" in entidad or "UNIVERSITARIA" in entidad:
                return "🎓 EDUCACIÓN", "Colegios y Universidades"

            elif "BATALLON" in entidad or "POLICIA" in entidad or "ARMADA" in entidad:
                return "🛡️ FUERZA PÚBLICA", entidad

            else: return "🏢 OTRAS ENTIDADES", entidad

        df['categoria'], df['entidad_filtro'] = zip(*df.apply(discriminar_entidad, axis=1))
        return df
    return None

df = load_data()

# -----------------------------------------------------------------------------
# 3. FILTROS (CON LA OPCIÓN "TODAS")
# -----------------------------------------------------------------------------
st.sidebar.title("🎛️ Panel de Control")
if df is not None:
    cats = sorted(df['categoria'].unique().tolist())
    orden = ["🚨 GOBERNACIÓN", "🏛️ ALCALDÍAS MUNICIPALES", "🏥 HOSPITALES / SALUD", "🎓 EDUCACIÓN", "🛡️ FUERZA PÚBLICA", "🏢 OTRAS ENTIDADES"]
    cats_sort = [c for c in orden if c in cats] + [c for c in cats if c not in orden]
    
    cat_sel = st.sidebar.selectbox("1. Tipo de Entidad", cats_sort)
    
    # Obtenemos las entidades y AGREGAMOS LA OPCIÓN "TODAS" AL PRINCIPIO
    entidades = sorted(df[df['categoria'] == cat_sel]['entidad_filtro'].unique().tolist())
    entidades.insert(0, "🌐 TODAS (Ver Conexiones)")
    
    ent_sel = st.sidebar.selectbox("2. Entidad Específica", entidades)
    
    # LÓGICA DE FILTRADO
    if ent_sel == "🌐 TODAS (Ver Conexiones)":
        df_filtrado = df[df['categoria'] == cat_sel]
        modo_red = True # Activamos modo red complejo
    else:
        df_filtrado = df[df['entidad_filtro'] == ent_sel]
        modo_red = False # Modo entidad única
else:
    st.error("Error: No hay datos.")
    st.stop()

# -----------------------------------------------------------------------------
# 4. DASHBOARD
# -----------------------------------------------------------------------------
titulo = f"{ent_sel}" if not modo_red else f"Análisis Global: {cat_sel}"
st.title(titulo)

# Métricas
total = df_filtrado['valor_del_contrato'].sum()
count = len(df_filtrado)
col_mod = 'modalidad_de_contratacion'
pct_dedo = 0
if col_mod in df_filtrado.columns:
    dedo = len(df_filtrado[df_filtrado[col_mod].astype(str).str.contains("Directa|Especial", case=False, na=False)])
    pct_dedo = (dedo / count * 100) if count > 0 else 0

c1, c2, c3 = st.columns(3)
with c1: st.markdown(f"""<div class="metric-card"><div class="metric-title">Presupuesto</div><div class="metric-value">${total/1e6:,.0f} M</div></div>""", unsafe_allow_html=True)
with c2: st.markdown(f"""<div class="metric-card"><div class="metric-title">Contratos</div><div class="metric-value">{count}</div></div>""", unsafe_allow_html=True)
with c3: 
    color = "#198754" if pct_dedo < 40 else "#dc3545"
    st.markdown(f"""<div class="metric-card" style="border-left:5px solid {color}"><div class="metric-title">Contratación Directa</div><div class="metric-value" style="color:{color}">{pct_dedo:.0f}%</div></div>""", unsafe_allow_html=True)

st.markdown("---")

# -----------------------------------------------------------------------------
# PESTAÑAS (INCLUYENDO LA RED)
# -----------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(["📊 RADIOGRAFÍA", "📅 CRONOGRAMA", "🕸️ RED DE PODER", "🔎 AUDITORÍA"])

# --- TAB 1: GRÁFICAS ---
with tab1:
    col_izq, col_der = st.columns(2)
    with col_izq:
        st.subheader("Modalidad")
        if col_mod in df_filtrado.columns:
            df_pie = df_filtrado[col_mod].value_counts().reset_index()
            df_pie.columns = ['Modalidad', 'Cantidad']
            fig = px.pie(df_pie, names='Modalidad', values='Cantidad', hole=0.6, color_discrete_sequence=px.colors.qualitative.Prism)
            st.plotly_chart(fig, use_container_width=True)
    with col_der:
        st.subheader("Top Contratistas ($)")
        col_prov = 'proveedor_adjudicado'
        if col_prov in df_filtrado.columns:
            top = df_filtrado.groupby(col_prov)['valor_del_contrato'].sum().nlargest(10).reset_index()
            fig2 = px.bar(top, x='valor_del_contrato', y=col_prov, orientation='h', text_auto='.2s')
            fig2.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig2, use_container_width=True)

# --- TAB 2: CRONOGRAMA ---
with tab2:
    st.subheader("📅 Línea de Tiempo de Contratos")
    if 'fecha_de_firma' in df_filtrado.columns and not df_filtrado.empty:
        fig_time = px.scatter(
            df_filtrado, x="fecha_de_firma", y="valor_del_contrato",
            size="valor_del_contrato", color="modalidad_de_contratacion",
            hover_name="objeto_del_contrato", size_max=60,
            color_discrete_sequence=px.colors.qualitative.Bold
        )
        fig_time.update_layout(height=450, plot_bgcolor="white", yaxis=dict(gridcolor='#eee'))
        st.plotly_chart(fig_time, use_container_width=True)

# --- TAB 3: RED DE PODER (LA TELARAÑA) ---
with tab3:
    st.subheader("🕸️ Mapa de Conexiones")
    
    mensaje = """
    **¿Cómo leer esto?**
    * Los **CUADROS AZULES** son las Entidades Públicas.
    * Los **PUNTOS ROJOS** son los Contratistas.
    * Si ves un punto rojo conectado a varios cuadros azules, ¡Bingo! Has encontrado un contratista compartido.
    """
    st.info(mensaje)
    
    # 1. Preparar datos (Limitamos para no colgar el navegador)
    # Tomamos los 50 contratistas más grandes de la selección actual
    top_contractors = df_filtrado.groupby('proveedor_adjudicado')['valor_del_contrato'].sum().nlargest(50).index.tolist()
    df_graph = df_filtrado[df_filtrado['proveedor_adjudicado'].isin(top_contractors)]
    
    if not df_graph.empty:
        G = nx.Graph()
        
        for idx, row in df_graph.iterrows():
            entidad = row['entidad_filtro'] # Puede ser Mocoa, Orito, etc.
            contratista = row['proveedor_adjudicado']
            valor = row['valor_del_contrato']
            
            # Nodo Entidad (Azul)
            G.add_node(entidad, label=entidad, title="Entidad Pública", color="#00A8E8", shape="box", size=25)
            # Nodo Contratista (Rojo)
            info = f"Contratista: {contratista}\nValor: ${valor:,.0f}"
            G.add_node(contratista, label=contratista[:15]+"...", title=info, color="#FF4B4B", shape="dot", size=15)
            # Conexión
            G.add_edge(entidad, contratista, color="#cccccc")
            
        try:
            # Física para que se separen
            net = Network(height="600px", width="100%", bgcolor="#ffffff", font_color="black")
            net.from_nx(G)
            net.repulsion(node_distance=150, spring_length=250)
            
            path_tmp = "grafo.html"
            net.save_graph(path_tmp)
            with open(path_tmp, 'r', encoding='utf-8') as f:
                html_string = f.read()
            components.html(html_string, height=620, scrolling=True)
        except Exception as e:
            st.error(f"Error visualizando red: {e}")
    else:
        st.warning("No hay suficientes datos para generar la red.")

# --- TAB 4: AUDITORÍA ---
with tab4:
    st.subheader("🕵️ Buscador")
    busqueda = st.text_input("Buscar:", placeholder="Ej: Vías...")
    df_show = df_filtrado.copy()
    if busqueda:
        mask = df_show.astype(str).apply(lambda x: x.str.contains(busqueda, case=False)).any(axis=1)
        df_show = df_show[mask]
    
    cols_ver = ['fecha_de_firma', 'entidad_filtro', 'proveedor_adjudicado', 'objeto_del_contrato', 'valor_del_contrato']
    st.dataframe(df_show[[c for c in cols_ver if c in df_show.columns]].sort_values('valor_del_contrato', ascending=False), 
                 use_container_width=True, hide_index=True)
