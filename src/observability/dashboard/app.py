"""
Streamlit dashboard for WHAT-TO-EAT-AGENT observability.
Visualizes RAG pipeline performance, agent activities, and system metrics.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import sqlite3
import os
from typing import Dict, List, Optional


# Set page configuration
st.set_page_config(
    page_title="WHAT-TO-EAT-AGENT Dashboard",
    page_icon="🥗",
    layout="wide"
)

st.title("🥗 WHAT-TO-EAT-AGENT Observability Dashboard")

# Initialize session state
if 'selected_view' not in st.session_state:
    st.session_state.selected_view = "Overview"

# Sidebar navigation
with st.sidebar:
    st.header("Navigation")
    selected_view = st.radio(
        "Go to",
        ["Overview", "RAG Performance", "Agent Activities", "User Metrics", "System Health"],
        key="navigation_radio"
    )

# Mock data generators for demonstration
@st.cache_data
def generate_mock_rag_performance_data(days: int = 30) -> pd.DataFrame:
    """Generate mock RAG performance data."""
    dates = [datetime.now() - timedelta(days=x) for x in range(days)]
    dates.reverse()

    data = {
        "date": dates,
        "queries": np.random.randint(50, 200, size=days),
        "success_rate": np.random.uniform(0.85, 0.98, size=days),
        "avg_response_time": np.random.uniform(0.5, 2.5, size=days),
        "top_queries": np.random.choice([
            "vegetarian dinner ideas", "quick breakfast recipes",
            "low-carb lunch options", "high-protein snacks",
            "gluten-free desserts", "mediterranean dishes"
        ], size=days)
    }

    return pd.DataFrame(data)

@st.cache_data
def generate_mock_agent_activities_data(days: int = 30) -> pd.DataFrame:
    """Generate mock agent activity data."""
    dates = [datetime.now() - timedelta(days=x) for x in range(days)]
    dates.reverse()

    activities = np.random.choice([
        "recipe_research", "meal_planning",
        "inventory_check", "shopping_list_gen"
    ], size=days*10)

    data = {
        "timestamp": [datetime.now() - timedelta(hours=x*2) for x in range(days*10)],
        "activity": activities,
        "user_id": [f"user_{np.random.randint(1, 20)}" for _ in range(days*10)],
        "duration": np.random.uniform(0.1, 2.0, size=days*10),
        "success": np.random.choice([True, False], size=days*10, p=[0.92, 0.08])
    }

    return pd.DataFrame(data)

@st.cache_data
def generate_mock_user_metrics_data() -> pd.DataFrame:
    """Generate mock user metrics data."""
    return pd.DataFrame({
        "user_id": [f"user_{i}" for i in range(1, 21)],
        "session_count": np.random.randint(1, 50, size=20),
        "avg_session_duration": np.random.uniform(5, 30, size=20),
        "dietary_restrictions": np.random.choice([
            "none", "vegetarian", "vegan", "gluten-free", "dairy-free", "nut-free"
        ], size=20, p=[0.4, 0.2, 0.15, 0.1, 0.1, 0.05]),
        "preferred_cuisines": np.random.choice([
            "italian", "asian", "mexican", "american", "mediterranean", "indian"
        ], size=20)
    })

@st.cache_data
def generate_popular_recipes_data() -> pd.DataFrame:
    """Generate mock popular recipes data."""
    return pd.DataFrame({
        "recipe_name": [
            "Vegetable Stir Fry", "Chicken Pasta", "Quinoa Salad",
            "Avocado Toast", "Beef Tacos", "Salmon Bowl",
            "Vegetable Curry", "Pancakes", "Greek Salad", "Ramen"
        ],
        "popularity_score": np.random.randint(50, 100, size=10),
        "avg_rating": np.random.uniform(4.0, 5.0, size=10),
        "preparation_time": np.random.randint(15, 60, size=10)
    })


# Main dashboard views
if selected_view == "Overview":
    st.header("📊 System Overview")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(label="Total Queries", value="1,248", delta="+12%")
    with col2:
        st.metric(label="Success Rate", value="94.2%", delta="+2.1%")
    with col3:
        st.metric(label="Avg Response Time", value="1.2s", delta="-0.3s")
    with col4:
        st.metric(label="Active Users", value="156", delta="+8")

    # Charts row 1
    st.subheader("Query Activity")
    rag_data = generate_mock_rag_performance_data(14)

    fig1 = px.line(
        rag_data,
        x='date',
        y='queries',
        title='Daily Query Volume',
        markers=True
    )
    fig1.update_layout(height=350)
    st.plotly_chart(fig1, use_container_width=True)

    # Charts row 2
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Success Rate Trend")
        fig2 = px.line(
            rag_data,
            x='date',
            y='success_rate',
            title='Success Rate Over Time',
            range_y=[0.8, 1.0]
        )
        fig2.update_layout(height=350)
        st.plotly_chart(fig2, use_container_width=True)

    with col2:
        st.subheader("Top Queries")
        top_queries = rag_data['top_queries'].value_counts().head(5)
        fig3 = px.bar(
            x=top_queries.values,
            y=top_queries.index,
            orientation='h',
            title='Most Popular Queries'
        )
        fig3.update_layout(height=350)
        st.plotly_chart(fig3, use_container_width=True)

elif selected_view == "RAG Performance":
    st.header("🔍 RAG Pipeline Performance")

    # Date range selector
    date_range = st.date_input(
        "Select date range",
        value=[datetime.now() - timedelta(days=7), datetime.now()]
    )

    rag_data = generate_mock_rag_performance_data(30)

    # Performance metrics
    col1, col2, col3 = st.columns(3)

    with col1:
        avg_success_rate = rag_data['success_rate'].mean()
        st.metric(label="Average Success Rate", value=f"{avg_success_rate:.1%}")

    with col2:
        avg_response_time = rag_data['avg_response_time'].mean()
        st.metric(label="Average Response Time", value=f"{avg_response_time:.2f}s")

    with col3:
        total_queries = rag_data['queries'].sum()
        st.metric(label="Total Queries Processed", value=f"{total_queries:,}")

    # Detailed charts
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Queries vs Success Rate")
        fig = px.scatter(
            rag_data,
            x='queries',
            y='success_rate',
            trendline="ols",
            title="Query Volume vs Success Rate Correlation"
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Response Time Distribution")
        fig = px.histogram(
            rag_data,
            x='avg_response_time',
            nbins=20,
            title="Distribution of Average Response Times"
        )
        st.plotly_chart(fig, use_container_width=True)

    # Top performing days
    st.subheader("Performance by Day of Week")
    rag_data['weekday'] = rag_data['date'].dt.day_name()
    weekday_perf = rag_data.groupby('weekday')['success_rate'].mean().reindex([
        'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'
    ])

    fig = px.bar(
        x=weekday_perf.index,
        y=weekday_perf.values,
        title="Average Success Rate by Day of Week"
    )
    st.plotly_chart(fig, use_container_width=True)

elif selected_view == "Agent Activities":
    st.header("🤖 Agent Activities")

    activity_data = generate_mock_agent_activities_data(14)

    # Activity metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_activities = len(activity_data)
        st.metric(label="Total Activities", value=f"{total_activities}")

    with col2:
        success_rate = activity_data['success'].mean()
        st.metric(label="Activity Success Rate", value=f"{success_rate:.1%}")

    with col3:
        avg_duration = activity_data['duration'].mean()
        st.metric(label="Avg Activity Duration", value=f"{avg_duration:.2f}s")

    with col4:
        unique_users = activity_data['user_id'].nunique()
        st.metric(label="Active Users", value=f"{unique_users}")

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Activities by Type")
        activity_counts = activity_data['activity'].value_counts()
        fig = px.pie(
            values=activity_counts.values,
            names=activity_counts.index,
            title="Distribution of Activity Types"
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Success Rate by Activity Type")
        success_by_type = activity_data.groupby('activity')['success'].mean()
        fig = px.bar(
            x=success_by_type.index,
            y=success_by_type.values,
            title="Success Rate by Activity Type"
        )
        fig.update_yaxes(range=[0, 1])
        st.plotly_chart(fig, use_container_width=True)

    # Timeline view
    st.subheader("Activity Timeline")
    activity_data['hour'] = activity_data['timestamp'].dt.hour
    hourly_activity = activity_data.groupby('hour').size()

    fig = px.bar(
        x=hourly_activity.index,
        y=hourly_activity.values,
        title="Activities by Hour of Day"
    )
    fig.update_xaxes(title="Hour of Day")
    fig.update_yaxes(title="Number of Activities")
    st.plotly_chart(fig, use_container_width=True)

elif selected_view == "User Metrics":
    st.header("👥 User Engagement Metrics")

    user_data = generate_mock_user_metrics_data()
    recipe_data = generate_popular_recipes_data()

    # User metrics
    col1, col2, col3 = st.columns(3)

    with col1:
        total_users = len(user_data)
        st.metric(label="Total Registered Users", value=f"{total_users}")

    with col2:
        avg_sessions = user_data['session_count'].mean()
        st.metric(label="Avg Sessions per User", value=f"{avg_sessions:.1f}")

    with col3:
        avg_duration = user_data['avg_session_duration'].mean()
        st.metric(label="Avg Session Duration", value=f"{avg_duration:.1f} min")

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Dietary Restrictions Distribution")
        diet_counts = user_data['dietary_restrictions'].value_counts()
        fig = px.pie(
            values=diet_counts.values,
            names=diet_counts.index,
            title="User Dietary Restrictions"
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Preferred Cuisines")
        cuisine_counts = user_data['preferred_cuisines'].value_counts()
        fig = px.bar(
            x=cuisine_counts.values,
            y=cuisine_counts.index,
            orientation='h',
            title="Most Preferred Cuisines"
        )
        st.plotly_chart(fig, use_container_width=True)

    # Popular recipes
    st.subheader("Popular Recipes")
    recipe_data_sorted = recipe_data.sort_values('popularity_score', ascending=False)

    fig = px.bar(
        recipe_data_sorted,
        x='popularity_score',
        y='recipe_name',
        orientation='h',
        title="Recipe Popularity Ranking",
        color='avg_rating',
        color_continuous_scale='viridis'
    )
    st.plotly_chart(fig, use_container_width=True)

elif selected_view == "System Health":
    st.header("🏥 System Health Monitor")

    # Simulate system health metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(label="Vector Store Status", value="Operational", delta=None)
    with col2:
        st.metric(label="BM25 Index Status", value="Operational", delta=None)
    with col3:
        st.metric(label="User DB Status", value="Operational", delta=None)
    with col4:
        st.metric(label="Inventory DB Status", value="Operational", delta=None)

    # System metrics
    st.subheader("Resource Utilization")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("CPU Usage")
        cpu_usage = np.random.uniform(20, 80, size=100)
        fig = go.Figure(data=go.Scatter(y=cpu_usage, mode='lines', name='CPU %'))
        fig.update_layout(
            title="CPU Usage Over Time",
            height=350,
            xaxis_title="Time Interval",
            yaxis_title="CPU %"
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Memory Usage")
        mem_usage = np.random.uniform(30, 90, size=100)
        fig = go.Figure(data=go.Scatter(y=mem_usage, mode='lines', name='Memory %'))
        fig.update_layout(
            title="Memory Usage Over Time",
            height=350,
            xaxis_title="Time Interval",
            yaxis_title="Memory %"
        )
        st.plotly_chart(fig, use_container_width=True)

    # Database performance
    st.subheader("Database Performance")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Query Response Times")
        query_times = np.random.exponential(scale=0.5, size=50)
        fig = px.histogram(x=query_times, nbins=20, title="Database Query Response Times")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Connection Pool Status")
        pool_data = pd.DataFrame({
            'Pool Type': ['Vector Store', 'BM25 Index', 'User DB', 'Inventory DB'],
            'Active Connections': np.random.randint(1, 10, size=4),
            'Max Capacity': [20, 20, 50, 50]
        })
        fig = px.bar(
            pool_data,
            x='Pool Type',
            y=['Active Connections', 'Max Capacity'],
            title="Database Connection Pool Status",
            barmode='overlay'
        )
        st.plotly_chart(fig, use_container_width=True)

# Footer
st.markdown("---")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | WHAT-TO-EAT-AGENT Observability Dashboard")