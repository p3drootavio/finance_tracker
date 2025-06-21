# Import standard libraries
import os
import json

# Import third-party libraries
import streamlit as st
import pandas as pd
import plotly.express as px

HEADER_ICON = "🏠"
COLUMN_WEIGHTS = [2, 1]
CATEGORY_COLORS = {
    "Groceries": "#4CAF50",      # Green
    "Rent": "#FF5722",           # Orange
    "Entertainment": "#9C27B0",  # Purple
    "Other": "#03A9F4"           # Blue
}
CATEGORY_FILE = "categories.json"


def render():
    st.header("🏠 Home")
    st.subheader("Welcome to the Finances Dashboard!")

    show_file_uploader()

    if "categories" not in st.session_state:
        st.session_state.categories = {
            "Uncategorized": []
        }

    if os.path.exists(CATEGORY_FILE):
        with open(CATEGORY_FILE, "r") as f:
            st.session_state.categories = json.load(f)

    # === SECTION 1: Weekly Spending Summary & Spending Health ===
    col1, col2 = st.columns(COLUMN_WEIGHTS)

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
            color="Category",  # Match names to colors
            color_discrete_map=CATEGORY_COLORS
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
        df = pd.read_csv(file, quotechar='"', skipinitialspace=True)
        st.write("First few rows:")
        st.write(df.head())
        df.columns = [col.strip() for col in df.columns]
        df["Amount"] = pd.to_numeric(df["Amount"].astype(str).str.replace(",", "").str.replace("$", ""), errors="coerce")
        df["Details"] = pd.to_datetime(df["Details"], format="%m/%d/%Y", errors="coerce")

        return categorize_transactions(df)
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None


def show_file_uploader():
    st.title("Data Loader")

    uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
    if uploaded_file is not None:
        data = load_data(uploaded_file)
        if data is not None:
            debits_df = data[data["Details"] == "DEBIT"].copy()
            credits_df = data[data["Details"] == "CREDIT"].copy()

            st.session_state.debits_df = debits_df.copy()

            tab1, tab2 = st.tabs(["Expenses (Debits)", "Payments (Credits)"])
            with tab1:
                new_category = st.text_input("New Category", key="new_category")
                add_category = st.button("Add Category")
                if new_category and add_category:
                    if new_category not in st.session_state.categories:
                        st.session_state.categories[new_category] = []
                        save_categories()
                        st.rerun()

                for category, transactions in st.session_state.categories.items():
                    if category == "Uncategorized":
                        continue

                    st.subheader(category)

                st.subheader("Your Expenses")
                edited_df = st.data_editor(
                    st.session_state.debits_df[["Details", "Posting Date", "Description"]]
                )


            st.write(data)


def save_categories():
    with open(CATEGORY_FILE, "w") as f:
        json.dump(st.session_state.categories, f)


def categorize_transactions(df):
    df["Category"] = "Uncategorized"

    for category, keywords in st.session_state.categories.items():
        if category == "Uncategorized" or not keywords:
            continue

        lowered_keywords = [keyword.lower().strip() for keyword in keywords]

        for idx, row in df.iterrows():
            description = row["Description"].lower().strip()
            if description in lowered_keywords:
                df.at[idx, "Category"] = category

    return df


def add_keyword_to_category(category, keyword):
    keyword = keyword.strip()
    if category not in st.session_state.categories[category]:
        st.session_state.categories[category].append(keyword)
        save_categories()
        return True
    return False
