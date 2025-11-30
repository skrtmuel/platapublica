import streamlit as st
import pandas as pd
import plotly.express as px
import os

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN VISUAL
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Veeduría Ciudadana Putumayo",
    page_icon="🇨🇴",
    layout="wide"
)

# -----------------------------------------------------------------------------
# 2. CARGA, LIMPIEZA Y CLASIFICACIÓN INTELIGENTE
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
    # Solo buscamos en la carpeta oficial
    ruta = "data/contratos_putumayo.csv"
    
    if os.path.exists(ruta):
        df = pd.read_csv(ruta)
        
        # --- LIMPIEZA TÉCNICA ---
        if 'valor_del_contrato' in df.columns:
            df['valor_del_contrato'] = pd.to_numeric(df['valor_del_contrato'], errors='coerce').fillna(0)
        
        if 'ciudad' in df.columns:
            df['ciudad'] = df['ciudad'].astype(str).str.upper().str.strip()
            # Normalización de nombres de ciudades
            df['ciudad'] = df['ciudad'].replace({
                'PUERTO ASIS': 'PUERTO ASÍS',
                'LEGUIZAMO': 'PUERTO LEGUÍZAMO',
                'VALLE DEL GUAMUEZ': 'LA HORMIGA'
            })
        
        if 'nombre_entidad' in df.columns:
            df['nombre_entidad'] = df['nombre_entidad'].astype(str).str.upper().str.strip()


        # -----------------------------------------------------------------
        # EL CEREBRO CLASIFICADOR (Versión Anti-Colados)
        # -----------------------------------------------------------------
        def discriminar_entidad(row):
            # Limpiamos tildes para evitar errores
            entidad = row['nombre_entidad'].replace('Á','A').replace('É','E').replace('Í','I').replace('Ó','O').replace('Ú','U')
            ciudad = row['ciudad']
            
            # 1. FILTRO DE SEGURIDAD (ANTI-COLADOS)
            # Si dice Nariño, Cauca, etc., lo marcamos como externo.
            if "NARIÑO" in entidad or "CAUCA" in entidad or "HUILA" in entidad or "CUNDINAMARCA" in entidad or "BOGOTA" in entidad:
                return "⚠️ ENTIDADES EXTERNAS (POSIBLES ERRORES SECOP)", entidad

            # 2. GOBERNACIÓN
            if ("GOBERNACION" in entidad or "DEPARTAMENTO DEL PUTUMAYO" in entidad) and "INDERCULTURA" not in entidad:
                return "🚨 GOBERNACIÓN", "Gobernación del Putumayo"
            
            # 3. ALCALDÍAS (PODER LOCAL)
            es_poder_local = ("ALCALDIA" in entidad or "MUNICIPIO" in entidad or "CONCEJO" in entidad)
            # Excepciones que dicen municipio pero no son la alcaldía
            es_excepcion = ("PERSONERIA" in entidad or "INSTITUCION" in entidad or "CENTRO" in entidad or "EMPRESA" in entidad or "AGUAS" in entidad or "TRANSPORTE" in entidad)

            if es_poder_local and not es_excepcion:
                # CASO MOCOA UNIFICADO
                if "MOCOA" in ciudad or "MOCOA" in entidad:
                        return "🏛️ ALCALDÍAS MUNICIPALES", "Alcaldía de MOCOA (Incl. Concejo)"
                # Resto de municipios
                return "🏛️ ALCALDÍAS MUNICIPALES", f"Alcaldía de {ciudad}"
            
            # 4. SALUD
            elif "HOSPITAL" in entidad or "E.S.E" in entidad or "ESE " in entidad:
                nombre_corto = entidad.replace("EMPRESA SOCIAL DEL ESTADO", "").replace("HOSPITAL", "HOSP.").strip()
                return "🏥 HOSPITALES / SALUD", nombre_corto
            
            # 5. EDUCACIÓN
            elif "INSTITUCION" in entidad or "CENTRO EDUCATIVO" in entidad or "SENA" in entidad or "UNIVERSITARIA" in entidad:
                return "🎓 EDUCACIÓN", "Colegios y Universidades"

            # 6. FUERZA PÚBLICA
            elif "BATALLON" in entidad or "POLICIA" in entidad or "ARMADA" in entidad:
                return "🛡️ FUERZA PÚBLICA", entidad

            # 7. OTROS
            else:
                return "🏢 OTRAS ENTIDADES", entidad

        # Aplicamos la lógica
        df['categoria'], df['entidad_filtro'] = zip(*df.apply(discriminar_entidad, axis=1))
        
        return df
    return None

df = load_data()

# -----------------------------------------------------------------------------
# 3. BARRA LATERAL (FILTROS EN CASCADA)
# -----------------------------------------------------------------------------
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/thumb/2/21/Flag_of_Colombia.svg/2560px-Flag_of_Colombia.svg.png", width=50)
st.sidebar.header("🔎 Panel de Selección")

if df is not None:
    # --- PASO 1: CATEGORÍA ---
    categorias_disponibles = sorted(df['categoria'].unique().tolist())
    # Orden forzado para que se vea bonito
    orden_ideal = ["🚨 GOBERNACIÓN", "🏛️ ALCALDÍAS MUNICIPALES", "🏥 HOSPITALES / SALUD", "🎓 EDUCACIÓN", "🛡️ FUERZA PÚBLICA", "🏢 OTRAS ENTIDADES", "⚠️ ENTIDADES EXTERNAS (POSIBLES ERRORES SECOP)"]
    cats_ordenadas = [c for c in orden_ideal if c in categorias_disponibles]
    
    cat_sel = st.sidebar.selectbox("1. Tipo de Entidad", cats_ordenadas)
    
    # --- PASO 2: ENTIDAD ---
    df_cat = df[df['categoria'] == cat_sel]
    entidades_disponibles = sorted(df_cat['entidad_filtro'].unique().tolist())
    
    # Pre-selección inteligente
    idx_ent = 0
    if cat_sel == "🏛️ ALCALDÍAS MUNICIPALES":
        match = [i for i, x in enumerate(entidades_disponibles) if "MOCOA" in x]
        if match: idx_ent = match[0]
            
    ent_sel = st.sidebar.selectbox("2. Entidad Específica", entidades_disponibles, index=idx_ent)
    
    # --- FILTRO FINAL ---
    df_filtrado = df[df['entidad_filtro'] == ent_sel]

else:
    st.error("⚠️ No hay datos. Ejecuta 'py etl.py'.")
    st.stop()

# -----------------------------------------------------------------------------
# 4. DASHBOARD PRINCIPAL
# -----------------------------------------------------------------------------
st.title(f"Lupa a: {ent_sel}")
st.caption(f"Categoría: {cat_sel}")
st.divider()

# KPIs
c1, c2, c3 = st.columns(3)
total_plata = df_filtrado['valor_del_contrato'].sum()
total_contratos = len(df_filtrado)

col_modalidad = 'modalidad_de_contratacion'
pct_dedo = 0
if col_modalidad in df_filtrado.columns:
    directa = len(df_filtrado[df_filtrado[col_modalidad].astype(str).str.contains("Directa|Especial", case=False, na=False)])
    pct_dedo = (directa / total_contratos * 100) if total_contratos > 0 else 0

with c1:
    st.info("💰 **Presupuesto Ejecutado**")
    st.metric("", f"${total_plata:,.0f}")
with c2:
    st.info("📄 **Contratos Firmados**")
    st.metric("", total_contratos)
with c3:
    if pct_dedo > 70:
        st.error(f"🚨 **Alerta: {pct_dedo:.0f}% a Dedo**")
    elif pct_dedo > 40:
        st.warning(f"⚠️ **Atención: {pct_dedo:.0f}% a Dedo**")
    else:
        st.success(f"✅ **Saludable: {pct_dedo:.0f}% a Dedo**")

st.divider()

# --- MAPA INTERACTIVO (SOLO SI APLICA) ---
# Mostramos mapa si estamos viendo Alcaldías o Gobernación, para ver dónde gastan
if not df_filtrado.empty and 'lat' in df_filtrado.columns:
    st.subheader(f"🗺️ ¿Dónde invierte {ent_sel}?")
    
    # Agrupamos por ciudad de ejecución
    map_data = df_filtrado.groupby('ciudad').agg({
        'valor_del_contrato': 'sum',
        'lat': 'first',
        'lon': 'first',
        'nombre_entidad': 'count'
    }).reset_index().dropna(subset=['lat'])
    
    if not map_data.empty:
        fig_map = px.scatter_mapbox(
            map_data, lat="lat", lon="lon", size="valor_del_contrato",
            color="valor_del_contrato", color_continuous_scale="Viridis",
            size_max=40, zoom=7, center={"lat": 0.8, "lon": -76.6},
            hover_name="ciudad", mapbox_style="carto-positron"
        )
        fig_map.update_layout(height=400, margin={"r":0,"t":0,"l":0,"b":0})
        st.plotly_chart(fig_map, use_container_width=True)

# --- GRÁFICAS ---
col_izq, col_der = st.columns(2)
with col_izq:
    st.subheader("1. Modalidad de Contratación")
    if col_modalidad in df_filtrado.columns:
        df_pie = df_filtrado[col_modalidad].value_counts().reset_index()
        df_pie.columns = ['Modalidad', 'Cantidad']
        fig = px.pie(df_pie, names='Modalidad', values='Cantidad', hole=0.5)
        st.plotly_chart(fig, use_container_width=True)

with col_der:
    st.subheader("2. Top Contratistas ($)")
    col_prov = 'proveedor_adjudicado'
    if col_prov in df_filtrado.columns:
        top = df_filtrado.groupby(col_prov)['valor_del_contrato'].sum().nlargest(10).reset_index()
        fig2 = px.bar(top, x='valor_del_contrato', y=col_prov, orientation='h', text_auto='.2s')
        fig2.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig2, use_container_width=True)

# --- AUDITORÍA ---
st.divider()
st.subheader("🕵️ Auditoría Detallada")
if col_prov in df_filtrado.columns:
    top_list = df_filtrado.groupby(col_prov)['valor_del_contrato'].sum().nlargest(50).index.tolist()
    prov_sel = st.selectbox("Seleccione un contratista para ver sus contratos:", top_list)
    
    df_zoom = df_filtrado[df_filtrado[col_prov] == prov_sel]
    
    st.markdown(f"**{prov_sel}** - Total: **${df_zoom['valor_del_contrato'].sum():,.0f}**")
    
    cols_show = ['fecha_de_firma', 'objeto_del_contrato', 'valor_del_contrato']
    cols_valid = [c for c in cols_show if c in df_filtrado.columns]
    
    st.dataframe(
        df_zoom[cols_valid].sort_values('valor_del_contrato', ascending=False),
        use_container_width=True, hide_index=True,
        column_config={"valor_del_contrato": st.column_config.NumberColumn("Valor", format="$%d")}
    )

# --- ZONA FORENSE (DEBUGGING) ---
st.divider()
with st.expander("🛠️ ZONA TÉCNICA (Verificación de Datos)"):
    st.write("Tabla de todas las entidades encontradas y su clasificación:")
    diag = df[['nombre_entidad', 'categoria', 'entidad_filtro']].drop_duplicates().sort_values('categoria')
    st.dataframe(diag, use_container_width=True)