import streamlit as st
import pandas as pd
import plotly.express as px


def render():
        st.header("🏠 Home")
        st.subheader("Welcome to the Finances Dashboard!")

        upload_file()

        # === SECTION 1: Weekly Spending Summary + Spending Health ===
        col1, col2 = st.columns([2, 1])

        # Pie chart - mock spending data
        with col1:
            st.subheader("Weekly Spending Summary")
            spending_data = pd.DataFrame({
                "Category": ["Groceries", "Rent", "Entertainment", "Other"],
                "Amount": [350, 280, 200, 170]
            })
            fig = px.pie(
                spending_data,
                names="Category",
                values="Amount",
                hole=0.3,
                width=400,
                height=400,
                color="Category",  # This line is required to match names to colors
                color_discrete_map={
                    "Groceries": "#4CAF50",  # Green
                    "Rent": "#FF5722",  # Orange
                    "Entertainment": "#9C27B0",  # Purple
                    "Other": "#03A9F4"  # Blue
                }
            )
            st.plotly_chart(fig, use_container_width=True)

        # Spending health status
        with col2:
            st.subheader("Spending Health")
            status = "Good"  # Later: compute based on thresholds
            if status == "Good":
                st.success("🟢 Good")
            elif status == "Moderate":
                st.warning("🟠 Moderate")
            else:
                st.error("🔴 Bad")

        # === SECTION 2: Recent Transactions + Balance Summary ===
        col3, col4 = st.columns(2)

        with col3:
            st.subheader("Recent Transactions")
            transactions = pd.DataFrame({
                "Date": ["Mar. 29", "Mar. 27", "Mar. 27", "Mar. 25"],
                "Category": ["Groceries", "Rent", "Utilities", "Entertainment"],
                "Amount": [500, 2000, 130, 50]
            })
            st.table(transactions)

        with col4:
            st.subheader("Balance Summary")
            st.metric("Checking", "$1,500")
            st.metric("Savings", "$5,000")
            st.metric("Investments", "$12,000")
            st.metric("Total Assets", "$18,500")


def load_data(file):
        try:
            df = pd.read_csv(file)
            return df
        except Exception as e:
            st.error(f"Error loading data: {e}")
            return None


def upload_file():
        st.title("Data Loader")

        uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
        if uploaded_file is not None:
            data = load_data(uploaded_file)
            if data is not None:
                st.write(data)

