"""Home page view with high-level UI and data loading logic."""

# Import standard libraries
import json
import os
import re
from typing import Dict, Iterable

# Import third-party libraries
import pandas as pd
import plotly.express as px
import streamlit as st


HEADER_ICON = "🏠"
COLUMN_WEIGHTS = [2, 1]
CATEGORY_COLORS = {
    "Groceries": "#4CAF50",      # Green
    "Rent": "#FF5722",           # Orange
    "Entertainment": "#9C27B0",  # Purple
    "Other": "#03A9F4",          # Blue
}
CATEGORY_FILE = "categories.json"


class CategoryManager:
    """Handle CRUD operations related to spending categories."""

    def __init__(self, file_path: str = CATEGORY_FILE) -> None:
        self.file_path = file_path
        self.categories: Dict[str, Iterable[str]] = {"Uncategorized": []}

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def load(self) -> None:
        """Load category keywords from disk into session state."""

        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    self.categories = json.load(f)
            except json.JSONDecodeError: # Corrupted category file would break the UI
                st.error("Failed to load saved categories. Using defaults.")
                self.categories = {"Uncategorized": []}

        st.session_state["categories"] = self.categories


    def save(self) -> None:
        """Persist categories to disk and keep session-state in sync."""
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self.categories, f)
        st.session_state["categories"] = self.categories

    # ------------------------------------------------------------------
    # Mutating helpers
    # ------------------------------------------------------------------
    def add_category(self, name: str) -> bool:
        name = name.strip()
        if not name or name in self.categories:
            return False
        self.categories[name] = []
        self.save()
        return True


    def add_keyword(self, category: str, keyword: str) -> bool:
        keyword = keyword.strip()
        if category not in self.categories or not keyword:
            return False

        if keyword not in self.categories[category]:
            self.categories[category].append(keyword)
            self.save()
            return True
        return False

    # ------------------------------------------------------------------
    # Categorisation
    # ------------------------------------------------------------------
    def categorize_transactions(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return df with an added ``Category`` column.

        Transactions are matched against keywords for each category. This
        method uses vectorised ``str.contains`` calls which are significantly
        faster than a nested for-loop when working with typical banking data
        sizes (thousands of rows). Any unmatched transaction defaults to the
        ``Uncategorized`` bucket.
        """

        df = df.copy()
        df["Category"] = "Uncategorized"

        for category, keywords in self.categories.items():
            if category == "Uncategorized" or not keywords:
                continue

            # Combine keywords into a single regular expression. ``re.escape``
            # avoids unintended regex behavior if keywords contain symbols.
            pattern = "|".join(re.escape(k) for k in keywords)
            mask = df["Description"].str.lower().str.contains(pattern)
            df.loc[mask, "Category"] = category

        return df


class TransactionDataLoader:
    """Load and preprocess CSV data before it is visualized."""

    def __init__(self, categorizer: CategoryManager) -> None:
        self.categorizer = categorizer


    def load(self, file) -> pd.DataFrame | None:
        """Parse a CSV upload into a DataFrame.

        Errors are surfaced to the user instead of being raised so that the
        UI remains usable even with malformed input files.
        """
        expected_cols = [
            "Details",  # DEBIT / CREDIT
            "Posting Date",  # MM/DD/YYYY
            "Description",
            "Amount",
            "Type",
            "Balance",
            "Check or Slip #"
        ]
        raw_cols = expected_cols + ["_extra"]

        try:
            df = pd.read_csv(
                file,
                dtype=str,
                names=raw_cols,
                header=0,
                usecols=raw_cols[:-1],
                skipinitialspace=True
            )
            df.columns = [c.strip() for c in df.columns]

            return self.categorizer.categorize_transactions(df)

        except Exception as exc:
            st.error(f"Error loading data: {exc}")
            return None


class HomePage:
    """Render logic for the application's home screen."""

    def __init__(self) -> None:
        self.categorizer = CategoryManager()
        self.loader = TransactionDataLoader(self.categorizer)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def render(self) -> None:
        """Main entry point used by ``main.py``."""

        st.header(f"{HEADER_ICON} Home")
        st.subheader("Welcome to the Finances Dashboard!")

        self.categorizer.load()
        self._show_file_uploader()
        # self._render_weekly_summary()
        # self._render_recent_transactions()

    # ------------------------------------------------------------------
    # UI components
    # ------------------------------------------------------------------
    def _render_weekly_summary(self) -> None:
        """Static pie chart and spending health indicator."""

        col1, col2 = st.columns(COLUMN_WEIGHTS)

        with col1:
            st.subheader("Weekly Spending Summary")
            spending_data = pd.DataFrame(
                {
                    "Category": ["Groceries", "Rent", "Entertainment", "Other"],
                    "Amount": [350, 280, 200, 170],
                }
            )
            fig = px.pie(
                spending_data,
                names="Category",
                values="Amount",
                hole=0.3,
                width=400,
                height=400,
                color="Category",
                color_discrete_map=CATEGORY_COLORS,
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Spending Health")
            status = "Good"  # TODO: calculate status based on real data
            if status == "Good":
                st.success("🟢 Good")
            elif status == "Moderate":
                st.warning("🟠 Moderate")
            else:
                st.error("🔴 Bad")


    def _render_recent_transactions(self) -> None:
        """Mock recent transactions table and balance summary."""

        col3, col4 = st.columns(2)

        with col3:
            st.subheader("Recent Transactions")
            transactions = pd.DataFrame(
                {
                    "Date": ["Mar. 29", "Mar. 27", "Mar. 27", "Mar. 25"],
                    "Category": ["Groceries", "Rent", "Utilities", "Entertainment"],
                    "Amount": [500, 2000, 130, 50],
                }
            )
            st.table(transactions)

        with col4:
            st.subheader("Balance Summary")
            st.metric("Checking", "$1,500")
            st.metric("Savings", "$5,000")
            st.metric("Investments", "$12,000")
            st.metric("Total Assets", "$18,500")


    def _show_file_uploader(self) -> None:
        """Handle CSV upload and category management UI."""

        st.title("Data Loader")
        uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

        if uploaded_file is None:
            return

        data = self.loader.load(uploaded_file)
        if data is None:
            return

        st.session_state.debits_df = data[data["Details"] == "DEBIT"].copy()
        st.session_state.credits_df = data[data["Details"] == "CREDIT"].copy()

        tab1, tab2 = st.tabs(["Expenses (Debits)", "Payments (Credits)"])
        with tab1:
            new_category = st.text_input("New Category", key="new_category")
            if st.button("Add Category"):
                if self.categorizer.add_category(new_category):
                    st.rerun()

            for category in self.categorizer.categories:
                if category == "Uncategorized":
                    continue
                # st.subheader(category)

            st.subheader("Your Expenses")
            edited_df_db = st.data_editor(
                st.session_state.debits_df[["Posting Date", "Description", "Amount", "Category"]],
                column_config={
                    "Date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                    "Amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
                    "Category": st.column_config.SelectboxColumn(
                        "Category",
                        options=list(st.session_state.categories.keys())),
                },
                hide_index=True,
                use_container_width=True,
                key="category_editor"
            )

            save_button = st.button("Save Changes", type="primary")
            if save_button:
                for idx, row in edited_df_db.iterrows():
                    new_category = row["Category"]
                    if new_category == st.session_state.debits_df.at[idx, "Category"]:
                        continue

                    description = row["Description"]
                    st.session_state.debits_df.at[idx, "Category"] = new_category
                    self.categorizer.add_keyword(new_category, description)

        with tab2:
            '''
            new_category_cr = st.text_input("New Category", key="new_category_cr")
            if st.button("Add Category"):
                if self.categorizer.add_keyword(new_category_cr):
                    st.rerun()
            '''

            for category in self.categorizer.categories:
                if category == "Uncategorized":
                    continue

            st.subheader("Your Payments")
            st.data_editor(
                st.session_state.credits_df[["Posting Date", "Description", "Amount"]]
            )

        # st.write(data)


def render() -> None:
    """Streamlit entry point used by ``main.py``."""

    HomePage().render()

