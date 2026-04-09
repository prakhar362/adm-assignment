import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Setup page config
st.set_page_config(
    page_title="Ticket Routing System",
    page_icon="🎫",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Backend API URL
API_URL = "http://localhost:8000/api"

# -----------------------------------------------------------------------------
# Premium UI CSS Styling
# -----------------------------------------------------------------------------
st.markdown("""
<style>
    /* Global Fonts */
    .stApp {
        font-family: 'Inter', sans-serif;
    }
    
    /* Header Enhancements */
    .main-header { 
        font-size: 2.8rem; 
        font-weight: 800; 
        letter-spacing: -0.02em;
        margin-bottom: 0.2rem; 
    }
    .sub-header { 
        font-size: 1.15rem; 
        margin-bottom: 2.5rem; 
        font-weight: 400;
        opacity: 0.8;
    }

    /* Cards for Metrics using Streamlit Containers */
    div[data-testid="metric-container"] {
        padding: 1.5rem;
        border-radius: 0.75rem;
        border: 1px solid rgba(128, 128, 128, 0.2);
    }
    div[data-testid="stMetricValue"] {
        font-size: 2.2rem;
        font-weight: 700;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 1rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        opacity: 0.7;
    }

    /* Styling Dataframes */
    .stDataFrame {
        border-radius: 0.5rem;
        overflow: hidden;
    }
    
    /* Buttons */
    .stButton>button {
        border-radius: 0.5rem;
        font-weight: 600;
        padding: 0.5rem 1rem;
        transition: all 0.2s;
    }
    .stButton>button:hover {
        transform: translateY(-1px);
    }
    
    /* Divider */
    hr {
        border-top: 1px solid rgba(128, 128, 128, 0.2);
        margin: 3rem 0;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Sidebar Navigation & Status
# -----------------------------------------------------------------------------
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2072/2072120.png", width=70)
    st.markdown("<h2 style='color:#0f172a; font-weight:800; margin-top:10px;'>PortalOS</h2>", unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    view_mode = st.radio("Navigation Menu", ["🧑‍💻 Customer Portal", "🛡️ Admin Dashboard"], label_visibility="hidden")
    
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    
    # Check health
    try:
        res = requests.get(f"{API_URL}/health", timeout=2)
        if res.status_code == 200:
            st.success("🟢 Core Systems Online", icon="✅")
        else:
            st.error("🔴 API Degraded", icon="🚨")
    except requests.exceptions.RequestException:
        st.error("🔴 Connection Lost", icon="🚨")


# -----------------------------------------------------------------------------
# VIEW 1: CUSTOMER PORTAL
# -----------------------------------------------------------------------------
if view_mode == "🧑‍💻 Customer Portal":
    st.markdown('<div class="main-header">🎫 Support Center</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Experiencing an issue? Let us know and our AI will route it to the right expert.</div>', unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown("#### Submit a Request")
        with st.form(key='ticket_form'):
            col1, col2 = st.columns(2)
            with col1:
                customer_name = st.text_input("Full Name", placeholder="e.g. Jane Doe")
            with col2:
                customer_email = st.text_input("Email Address", placeholder="e.g. jane@example.com")
                
            subject = st.text_input("Issue Subject", placeholder="Short summary of the problem")
            description = st.text_area("Detailed Description", placeholder="Please explain your issue in detail...", height=150)
            
            st.markdown("<br>", unsafe_allow_html=True)
            submit_button = st.form_submit_button(label="🚀 Submit Ticket Immediately", type="primary", use_container_width=True)

    if submit_button:
        if not customer_name or not customer_email or not subject or len(description) < 10:
            st.warning("Please fill in all fields. The description must be at least 10 characters long.")
        else:
            payload = {
                "customer_name": customer_name,
                "customer_email": customer_email,
                "subject": subject,
                "description": description,
                "language": "en",
                "source_channel": "streamlit_ui"
            }
            
            with st.spinner('Authenticating & Routing...'):
                try:
                    response = requests.post(f"{API_URL}/tickets/route", json=payload)
                    if response.status_code == 201:
                        st.balloons()
                        st.success("✅ Your ticket has been securely submitted!")
                        data = response.json()
                        st.info(f"**Reference ID: #{data['ticket_id']}**")
                    else:
                        st.error(f"System Error {response.status_code}: {response.text}")
                except requests.exceptions.RequestException:
                    st.error("Failed to connect to backend server.")


# -----------------------------------------------------------------------------
# VIEW 2: ADMIN DASHBOARD (PREMIUM)
# -----------------------------------------------------------------------------
elif view_mode == "🛡️ Admin Dashboard":
    st.markdown('<div class="main-header">🛡️ Analytics Dashboard</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Real-time overview of active ticket volumes, AI predictions, and priority escalations.</div>', unsafe_allow_html=True)

    colA, colB = st.columns([0.85, 0.15])
    with colB:
        st.button("🔄 Sync Operations", type="primary", use_container_width=True)

    with st.spinner("Compiling Analytics..."):
        try:
            res = requests.get(f"{API_URL}/tickets")
            if res.status_code == 200:
                tickets_data = res.json()
                
                if not tickets_data:
                    st.info("No active tickets found in the operational database.")
                else:
                    df_list = []
                    total_escalated = 0
                    confidences = []
                    
                    for t in tickets_data:
                        pred = t.get("prediction") or {}
                        routing = t.get("routing") or {}
                        
                        escalated = routing.get("escalated", False)
                        if escalated:
                            total_escalated += 1
                            
                        # Format confidence safely
                        conf_val = pred.get('category_confidence')
                        if conf_val is not None:
                            confidences.append(float(conf_val))
                            conf_str = f"{conf_val:.2f}"
                        else:
                            conf_str = "N/A"
                            
                        df_list.append({
                            "ID": t.get("ticket_id"),
                            "Customer": t.get("customer_name"),
                            "Subject": t.get("subject"),
                            "Category": pred.get("predicted_category", "Unknown"),
                            "Confidence": float(conf_val) if conf_val is not None else 0.0,
                            "Queue": routing.get("assigned_queue", "Unassigned"),
                            "Priority": routing.get("priority", "medium").capitalize(),
                            "Escalated": "Yes" if escalated else "No",
                            "Created At": t.get("created_at")[:16].replace("T", " ")
                        })
                    
                    df = pd.DataFrame(df_list)
                    
                    # --- TOP KPI METRICS ---
                    st.markdown("<br>", unsafe_allow_html=True)
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Global Volume", len(df))
                    m2.metric("Critical Escalations", total_escalated)
                    
                    if confidences:
                        avg_conf = sum(confidences) / len(confidences)
                        m3.metric("AI Precision Score", f"{avg_conf*100:.1f}%")
                    else:
                        m3.metric("AI Precision Score", "N/A")
                        
                    high_prio = len(df[df["Priority"].isin(["Critical", "High"])])
                    m4.metric("High Priority Workload", high_prio)
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    # --- PLOTLY CHARTS ---
                    st.markdown("### Operational Insights")
                    c1, c2 = st.columns(2)
                    
                    with c1:
                        with st.container(border=True):
                            # Donut Chart for Priorities
                            prio_counts = df["Priority"].value_counts().reset_index()
                            prio_counts.columns = ["Priority", "Count"]
                            
                            color_map = {"Critical": "#ef4444", "High": "#f97316", "Medium": "#10b981", "Low": "#64748b"}
                            
                            fig_donut = px.pie(
                                prio_counts, 
                                names="Priority", 
                                values="Count", 
                                hole=0.6,
                                title="Routing Priorities",
                                color="Priority",
                                color_discrete_map=color_map
                            )
                            fig_donut.update_layout(margin=dict(t=40, b=10, l=10, r=10), title_font=dict(size=18, family="Inter"))
                            st.plotly_chart(fig_donut, use_container_width=True)
                            
                    with c2:
                        with st.container(border=True):
                            # Horizontal Bar for Categories
                            cat_counts = df["Category"].value_counts().reset_index().head(6)  # Top 6
                            cat_counts.columns = ["Category", "Volume"]
                            cat_counts = cat_counts.sort_values(by="Volume", ascending=True)
                            
                            fig_bar = px.bar(
                                cat_counts, 
                                x="Volume", 
                                y="Category", 
                                orientation='h',
                                title="Top AI Classification Categories",
                                template="none"
                            )
                            fig_bar.update_traces(marker_color='#3b82f6', marker_line_color='#2563eb', marker_line_width=1.5, opacity=0.8)
                            fig_bar.update_layout(margin=dict(t=40, b=10, l=10, r=10), title_font=dict(size=18, family="Inter"))
                            st.plotly_chart(fig_bar, use_container_width=True)

                    st.markdown("<hr>", unsafe_allow_html=True)

                    # --- DATAFRAME VIEW ---
                    st.markdown("### Active Ticket Directory")
                    
                    # Styling dataframe conditionally
                    def color_priority(val):
                        if val == "Critical": return 'color: white; background-color: #ef4444'
                        elif val == "High": return 'color: white; background-color: #f97316'
                        return ''
                    
                    styled_df = df.style.map(color_priority, subset=['Priority']) \
                                        .format({'Confidence': "{:.2f}"})
                    
                    st.dataframe(
                        styled_df, 
                        use_container_width=True,
                        hide_index=True,
                        height=250,
                        column_config={
                            "ID": st.column_config.TextColumn("ID", width="small"),
                        }
                    )
                    
                    # --- DRILL DOWN ---
                    st.markdown("<br>", unsafe_allow_html=True)
                    with st.expander("🔍 Deep Dive: AI Routing Mechanics", expanded=False):
                        selected_id = st.selectbox("Select a Subject to inspect reasoning logic:", df["Subject"].tolist())
                        if selected_id:
                            # find ticket by subject
                            tkt_row = df[df["Subject"] == selected_id].iloc[0]
                            detail = next((item for item in tickets_data if item["ticket_id"] == tkt_row["ID"]), None)
                            if detail:
                                rp = detail.get("prediction", {})
                                rr = detail.get("routing", {})
                                
                                st.write(f"**Ticket ID:** #{tkt_row['ID']}  |  **Queue:** `{rr.get('assigned_queue')}`")
                                st.info(f"**Business Rule Engine Execution:** {rr.get('reason')}")
                                
                                sub_c1, sub_c2 = st.columns(2)
                                sub_c1.metric("Predicted Intent", rp.get('predicted_intent', 'N/A'))
                                sub_c2.metric("Inference Latency", f"{rp.get('inference_time_ms', 0)} ms")

            else:
                st.error("Error fetching tickets from server nodes.")
                
        except Exception as e:
            st.error("Failed to fetch tickets. Please check connection.")
            st.exception(e)
