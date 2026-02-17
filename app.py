import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io

# ─────────────────────────────────────────────
# CONFIGURACIÓN DE PÁGINA
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Dashboard Limpieza en Seco",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────
# ESTILOS CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
    /* Fondo general */
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    
    /* Contenido principal */
    .block-container {
        background: transparent;
        padding-top: 2rem;
    }
    
    /* Título principal */
    .main-header {
        background: white;
        padding: 30px;
        border-radius: 15px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        text-align: center;
        margin-bottom: 25px;
    }
    .main-header h1 {
        color: #667eea;
        font-size: 2.5em;
        margin-bottom: 5px;
    }
    .main-header p {
        color: #666;
        font-size: 1.1em;
    }
    
    /* Tarjetas KPI */
    .kpi-card {
        background: white;
        padding: 25px 20px;
        border-radius: 15px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        text-align: center;
        transition: all 0.3s;
        height: 140px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .kpi-label {
        color: #888;
        font-size: 0.8em;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 10px;
        font-weight: 600;
    }
    .kpi-value {
        color: #667eea;
        font-size: 2.2em;
        font-weight: bold;
        line-height: 1;
        margin-bottom: 5px;
    }
    .kpi-sub {
        color: #bbb;
        font-size: 0.8em;
    }
    
    /* Tarjetas de gráficos */
    .chart-card {
        background: white;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        margin-bottom: 20px;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background: white;
        box-shadow: 5px 0 20px rgba(0,0,0,0.1);
    }
    
    /* Upload box */
    .upload-section {
        background: white;
        padding: 30px;
        border-radius: 15px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        text-align: center;
        margin-bottom: 25px;
    }
    
    /* Ocultar elementos de Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# FUNCIONES DE PROCESAMIENTO
# ─────────────────────────────────────────────

def get_tracker_column(df):
    """Detecta si la columna de tracker se llama 'CBOX' o 'Tracker'"""
    if 'Tracker' in df.columns:
        return 'Tracker'
    elif 'CBOX' in df.columns:
        return 'CBOX'
    return None

def get_strings_column(df):
    """Detecta el nombre exacto de la columna de strings"""
    for col in df.columns:
        if 'String' in col or 'string' in col:
            return col
    return None

def load_excel(file) -> dict:
    """Carga y procesa el archivo Excel"""
    try:
        xl = pd.ExcelFile(file)
        sheets = xl.sheet_names

        if 'REGISTRO_DIARIO' not in sheets:
            st.error("❌ No se encontró la hoja 'REGISTRO_DIARIO' en el archivo.")
            return None

        # Leer REGISTRO_DIARIO
        df_reg = pd.read_excel(file, sheet_name='REGISTRO_DIARIO')
        df_reg = df_reg.iloc[:, :10]

        tracker_col = get_tracker_column(df_reg)
        if not tracker_col:
            st.error("❌ No se encontró columna 'Tracker' o 'CBOX'.")
            return None

        df_reg = df_reg.dropna(subset=['Fecha', tracker_col])
        df_reg['Fecha'] = pd.to_datetime(df_reg['Fecha']).dt.date
        df_reg = df_reg.rename(columns={tracker_col: 'Tracker'})

        # Columna strings
        strings_col = get_strings_column(df_reg)
        if strings_col and strings_col != 'Strings':
            df_reg = df_reg.rename(columns={strings_col: 'Strings'})

        # Leer BASE_DATOS si existe
        df_base = None
        if 'BASE_DATOS' in sheets:
            df_base = pd.read_excel(file, sheet_name='BASE_DATOS')

        # Calcular progreso correcto día a día
        df_progreso = calcular_progreso(df_reg)

        # Nombre de planta desde el archivo
        nombre = file.name.replace('limpieza_en_seco_', '').replace('.xlsx', '').replace('.xls', '')

        return {
            'registro': df_reg,
            'base': df_base,
            'progreso': df_progreso,
            'nombre': nombre,
            'tracker_col': 'Tracker'
        }

    except Exception as e:
        st.error(f"❌ Error al procesar el archivo: {str(e)}")
        return None


def calcular_progreso(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula el progreso acumulado correcto día a día"""
    total_paneles = df['Paneles Acumulados'].max() if 'Paneles Acumulados' in df.columns else df['Paneles Limpiados'].sum()

    resumen = (
        df.groupby('Fecha')['Paneles Limpiados']
        .sum()
        .reset_index()
        .sort_values('Fecha')
    )
    resumen['Acumulado'] = resumen['Paneles Limpiados'].cumsum()
    resumen['% Avance'] = (resumen['Acumulado'] / total_paneles * 100).round(2)
    resumen.columns = ['Fecha', 'Paneles del Día', 'Paneles Acumulados', '% Avance']
    return resumen


def apply_filters(df: pd.DataFrame, fecha, inversor, cbox, tracker) -> pd.DataFrame:
    """Aplica filtros al dataframe"""
    filtered = df.copy()
    if fecha != 'Todas':
        filtered = filtered[filtered['Fecha'] == pd.to_datetime(fecha).date()]
    if inversor != 'Todos':
        filtered = filtered[filtered['Inversor'] == inversor]
    if cbox != 'Todos' and 'CBOX' in df.columns:
        filtered = filtered[filtered['CBOX'] == cbox]
    if tracker != 'Todos':
        filtered = filtered[filtered['Tracker'] == tracker]
    return filtered


# ─────────────────────────────────────────────
# COMPONENTES DE VISUALIZACIÓN
# ─────────────────────────────────────────────

def render_kpis(df: pd.DataFrame, progreso: pd.DataFrame):
    """Renderiza tarjetas KPI"""
    total_paneles = int(df['Paneles Limpiados'].sum())
    total_strings = int(df['Strings'].sum()) if 'Strings' in df.columns else 0
    max_avance = float(progreso['% Avance'].max()) if len(progreso) > 0 else 0.0
    total_potencia = float(df['Potencia DC Asociada'].sum()) if 'Potencia DC Asociada' in df.columns else 0.0

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Total Paneles Limpiados</div>
            <div class="kpi-value">{total_paneles:,}</div>
            <div class="kpi-sub">Acumulado</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Strings Limpiados</div>
            <div class="kpi-value">{total_strings:,}</div>
            <div class="kpi-sub">Total</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">% Avance Total</div>
            <div class="kpi-value">{max_avance:.1f}%</div>
            <div class="kpi-sub">Progreso Global</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Potencia DC Total</div>
            <div class="kpi-value">{total_potencia:.0f}</div>
            <div class="kpi-sub">kW</div>
        </div>
        """, unsafe_allow_html=True)


def render_charts(df: pd.DataFrame, progreso: pd.DataFrame):
    """Renderiza los 4 gráficos"""
    
    # ── Colores de marca ──────────────────────
    COLOR_PRIMARY   = '#667eea'
    COLOR_SECONDARY = '#764ba2'
    COLOR_TEAL      = '#4ecdc4'
    COLOR_RED       = '#ff6b6b'
    PALETTE = [COLOR_PRIMARY, COLOR_SECONDARY, COLOR_TEAL, COLOR_RED,
               '#a29bfe', '#fd79a8', '#00cec9', '#fdcb6e']

    col1, col2 = st.columns(2)

    # ── Gráfico 1: Paneles por Tracker ────────
    with col1:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        tracker_data = df.groupby('Tracker')['Paneles Limpiados'].sum().reset_index().sort_values('Tracker')
        fig1 = px.bar(
            tracker_data,
            x='Tracker', y='Paneles Limpiados',
            title='📊 Paneles Limpiados por Tracker',
            color_discrete_sequence=[COLOR_PRIMARY]
        )
        fig1.update_layout(
            plot_bgcolor='white', paper_bgcolor='white',
            title_font_color=COLOR_PRIMARY,
            showlegend=False,
            xaxis_tickangle=-45,
            height=350,
            margin=dict(t=50, b=60)
        )
        st.plotly_chart(fig1, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Gráfico 2: Progreso acumulado ─────────
    with col2:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=progreso['Fecha'].astype(str),
            y=progreso['% Avance'],
            mode='lines+markers',
            fill='tozeroy',
            line=dict(color=COLOR_SECONDARY, width=3),
            marker=dict(size=10, color=COLOR_SECONDARY),
            customdata=progreso[['Paneles Acumulados', 'Paneles del Día']].values,
            hovertemplate=(
                '<b>%{x}</b><br>'
                'Avance: %{y:.2f}%<br>'
                'Paneles acumulados: %{customdata[0]:,}<br>'
                'Limpiados hoy: %{customdata[1]:,}<extra></extra>'
            )
        ))
        fig2.update_layout(
            title='📈 Progreso Acumulado por Fecha',
            title_font_color=COLOR_PRIMARY,
            plot_bgcolor='white', paper_bgcolor='white',
            yaxis=dict(range=[0, 105], ticksuffix='%'),
            height=350,
            margin=dict(t=50, b=40)
        )
        st.plotly_chart(fig2, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    col3, col4 = st.columns(2)

    # ── Gráfico 3: Potencia por Inversor ──────
    with col3:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        if 'Potencia DC Asociada' in df.columns:
            pot_data = df.groupby('Inversor')['Potencia DC Asociada'].sum().reset_index()
            fig3 = px.pie(
                pot_data,
                names='Inversor', values='Potencia DC Asociada',
                title='⚡ Potencia DC por Inversor',
                color_discrete_sequence=PALETTE,
                hole=0.4
            )
            fig3.update_traces(
                textposition='inside', textinfo='percent+label',
                hovertemplate='<b>%{label}</b><br>%{value:.1f} kW<extra></extra>'
            )
            fig3.update_layout(
                title_font_color=COLOR_PRIMARY,
                paper_bgcolor='white',
                height=350,
                margin=dict(t=50, b=40)
            )
            st.plotly_chart(fig3, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Gráfico 4: Paneles por Fecha ──────────
    with col4:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        fig4 = px.bar(
            progreso,
            x=progreso['Fecha'].astype(str),
            y='Paneles del Día',
            title='🎯 Paneles Limpiados por Fecha',
            color_discrete_sequence=[COLOR_TEAL],
            text='Paneles del Día'
        )
        fig4.update_traces(texttemplate='%{text:,}', textposition='outside')
        fig4.update_layout(
            plot_bgcolor='white', paper_bgcolor='white',
            title_font_color=COLOR_PRIMARY,
            showlegend=False,
            height=350,
            margin=dict(t=50, b=40),
            xaxis_title='Fecha',
            yaxis_title='Paneles'
        )
        st.plotly_chart(fig4, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)


def render_table(df: pd.DataFrame, base: pd.DataFrame):
    """Renderiza la tabla de detalle"""
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.markdown("### 📋 Detalle de Registros")

    # Preparar tabla de display
    display_cols = ['Fecha', 'Tracker', 'Inversor', 'Paneles Limpiados']
    if 'Strings' in df.columns:
        display_cols.append('Strings')
    if '% Avance' in df.columns:
        display_cols.append('% Avance')
    if 'Potencia DC Asociada' in df.columns:
        display_cols.append('Potencia DC Asociada')

    df_display = df[display_cols].copy()
    df_display['Fecha'] = df_display['Fecha'].astype(str)

    if '% Avance' in df_display.columns:
        df_display['% Avance'] = (df_display['% Avance'] * 100).map('{:.0f}%'.format)

    if 'Potencia DC Asociada' in df_display.columns:
        df_display['Potencia DC Asociada'] = df_display['Potencia DC Asociada'].map('{:.1f} kW'.format)

    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        height=400,
        column_config={
            'Paneles Limpiados': st.column_config.NumberColumn(format='%d'),
        }
    )
    st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────
# SIDEBAR: FILTROS Y CARGA DE ARCHIVO
# ─────────────────────────────────────────────

with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding: 20px 0 10px;">
        <span style="font-size:2em;">⚡</span>
        <h2 style="color:#667eea; margin:5px 0;">Limpieza en Seco</h2>
        <p style="color:#888; font-size:0.85em;">Dashboard Universal</p>
    </div>
    <hr style="border-color:#eee; margin-bottom:20px;">
    """, unsafe_allow_html=True)

    st.markdown("### 📁 Cargar Archivo")
    uploaded_file = st.file_uploader(
        "Selecciona el Excel de limpieza",
        type=['xlsx', 'xls'],
        help="El archivo debe tener las hojas REGISTRO_DIARIO y BASE_DATOS"
    )

    st.markdown("---")

    if uploaded_file:
        st.markdown("### 🔍 Filtros")


# ─────────────────────────────────────────────
# CONTENIDO PRINCIPAL
# ─────────────────────────────────────────────

# Header principal
st.markdown("""
<div class="main-header">
    <h1>Dashboard Limpieza en Seco</h1>
    <p>Sistema Universal de Control de Operaciones</p>
</div>
""", unsafe_allow_html=True)


# ── Sin archivo cargado → pantalla de bienvenida ──
if not uploaded_file:
    st.markdown("""
    <div class="upload-section">
        <h2 style="color:#667eea; margin-bottom:15px;">📂 Carga tu archivo Excel</h2>
        <p style="color:#888; margin-bottom:20px;">
            Usa el panel izquierdo para seleccionar tu archivo de limpieza
        </p>
        <div style="background:#f8f9ff; padding:20px; border-radius:10px; display:inline-block; text-align:left;">
            <p style="color:#555;"><strong>El archivo debe contener:</strong></p>
            <p style="color:#666;">✅ Hoja <code>REGISTRO_DIARIO</code></p>
            <p style="color:#666;">✅ Hoja <code>BASE_DATOS</code></p>
            <p style="color:#666; margin-top:10px;"><strong>Compatible con cualquier planta:</strong></p>
            <p style="color:#666;">⚡ Planta Sauce &nbsp;|&nbsp; 🌳 Planta El Roble &nbsp;|&nbsp; 🏭 Otras plantas</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


# ── Procesar archivo ──────────────────────────
with st.spinner("⏳ Procesando archivo..."):
    data = load_excel(uploaded_file)

if not data:
    st.stop()

df_reg  = data['registro']
df_base = data['base']
df_prog = data['progreso']
planta  = data['nombre']


# ── Filtros en sidebar ────────────────────────
with st.sidebar:
    fechas  = ['Todas'] + [str(f) for f in sorted(df_reg['Fecha'].unique())]
    inversores = ['Todos'] + sorted(df_reg['Inversor'].dropna().unique().tolist())
    trackers   = ['Todos'] + sorted(df_reg['Tracker'].dropna().unique().tolist())

    cbox_opts = ['Todos']
    if df_base is not None and 'CBOX' in df_base.columns:
        cbox_opts += sorted(df_base['CBOX'].dropna().unique().tolist())

    sel_fecha    = st.selectbox("📅 Fecha",    fechas)
    sel_inversor = st.selectbox("🔌 Inversor", inversores)
    sel_cbox     = st.selectbox("📦 CBOX",     cbox_opts)
    sel_tracker  = st.selectbox("🎯 Tracker",  trackers)

    if st.button("🔄 Resetear Filtros", use_container_width=True):
        st.rerun()


# ── Aplicar filtros ───────────────────────────
df_filtered = apply_filters(df_reg, sel_fecha, sel_inversor, sel_cbox, sel_tracker)

if len(df_filtered) == 0:
    st.warning("⚠️ No hay datos con los filtros seleccionados.")
    st.stop()

# Recalcular progreso con datos filtrados
df_prog_filtered = calcular_progreso(df_filtered)

# Título de planta
st.markdown(f"""
<div style="background:white; padding:15px 25px; border-radius:12px;
     box-shadow:0 5px 20px rgba(0,0,0,0.15); margin-bottom:20px;
     display:flex; align-items:center; justify-content:space-between;">
    <h2 style="color:#667eea; margin:0;">Planta {planta}</h2>
    <span style="color:#888; font-size:0.9em;">
        {len(df_filtered):,} registros &nbsp;|&nbsp;
        {df_filtered['Fecha'].nunique()} días &nbsp;|&nbsp;
        {df_filtered['Tracker'].nunique()} trackers
    </span>
</div>
""", unsafe_allow_html=True)

# ── KPIs ──────────────────────────────────────
render_kpis(df_filtered, df_prog_filtered)

st.markdown("<br>", unsafe_allow_html=True)

# ── Gráficos ──────────────────────────────────
render_charts(df_filtered, df_prog_filtered)

st.markdown("<br>", unsafe_allow_html=True)

# ── Tabla ─────────────────────────────────────
render_table(df_filtered, df_base)

# ── Footer ────────────────────────────────────
st.markdown("""
<div style="text-align:center; padding:20px; color:rgba(255,255,255,0.6); font-size:0.85em;">
    Dashboard Limpieza en Seco · Sistema Universal de Control
</div>
""", unsafe_allow_html=True)
