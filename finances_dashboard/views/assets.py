"""Assets tab view for the Streamlit finances dashboard."""

# Import standard libraries
import json
import os
from typing import Dict, Iterable

# Import third-party libraries
import pandas as pd
import plotly.express as px
import streamlit as st


HEADER_ICON = "💰"
ASSET_FILE = "assets.json"
COLUMN_WEIGHTS = [2, 1]


class AssetManager:
    """Handle CRUD operations related to assets."""

    def __init__(self, file_path: str = ASSET_FILE) -> None:
        self.file_path = file_path
        self.assets: Dict[str, float] = {}


    def load(self) -> None:
        """Load asset prices from disk into session state."""

        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    self.assets = json.load(f)
            except json.JSONDecodeError:
                st.error("Failed to load saved assets. Using defaults.")
                self.assets = {}
        else:
            self.save()

        st.session_state["assets"] = self.assets


    def save(self) -> None:
        """Persist assets to disk and keep session-state in sync."""
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self.assets, f)
        st.session_state["assets"] = self.assets


    def add_or_update(self, name: str, amount: float) -> None:
        self.assets[name] = amount
        self.save()


    def delete(self, name: str) -> None:
        if name in self.assets:
            del self.assets[name]
            self.save()


    def to_dataframe(self) -> pd.DataFrame:
        df = pd.DataFrame(
            [{"Asset": k, "Balance": v} for k, v in self.assets.items()]
        )

        return df if not df.empty else pd.DataFrame(columns=["Asset", "Balance"])


class AssetsPage:
    """Render logic for the application's assets screen."""
    def __init__(self) -> None:
        self.manager = AssetManager()


    def render(self) -> None:
        """Main entry point used by ``main.py``."""
        st.header(f"{HEADER_ICON} Assets")
        st.caption("Manage your assets and their current balances.")

        if "assets" not in st.session_state:
            self.manager.load()
        else:
            # Re‑use the in‑memory copy to avoid going to disk on every rerun
            self.manager.assets = st.session_state["assets"]

        st.subheader("Add/Update Asset")
        with st.form("add_asset", clear_on_submit=False):
            asset_name = st.text_input("Asset Name")
            asset_balance = st.number_input("Balance", min_value=0.0, format="%.2f")
            submit_button = st.form_submit_button("Add Asset")

            if submit_button and asset_name.strip() and asset_balance > 0:
                self.manager.add_or_update(asset_name.strip(), float(asset_balance))
                st.success("Asset added successfully.")
                st.rerun()

        st.markdown("---")

        col_chart, col_summary = st.columns(COLUMN_WEIGHTS)

        with col_chart:
            df = self.manager.to_dataframe()
            if df.empty:
                st.info("Add some assets on the left to get started!")
            else:
                st.subheader("Asset Allocation")
                fig = px.pie(
                    df,
                    names="Asset",
                    values="Balance",
                    hole=0.35,
                    width=400,
                    height=400,
                    color="Asset",
                )
                fig.update_traces(textposition="inside", textinfo="percent+label")
                st.plotly_chart(fig, use_container_width=True)

        with col_summary:
            st.subheader("Balances")
            edited_df = st.data_editor(
                self.manager.to_dataframe(),
                column_config={
                    "Balance": st.column_config.NumberColumn("Balance", format="$%.2f"),
                },
                hide_index=True,
                use_container_width=True,
            )

            if st.button("💾 Save Changes", type="primary"):
                for _, row in edited_df.iterrows():
                    self.manager.add_or_update(row["Asset"], float(row["Balance"]))
                st.success("Changes saved successfully.")

            total_assets = sum(self.manager.assets.values())
            st.metric("Total Assets", f"${total_assets:.2f}")

            with st.expander("Delete Assets"):
                to_delete = st.selectbox("Choose assets to delete", ["-"] + list(self.manager.assets.keys()))
                if st.button("Delete", disabled=to_delete == "-"):
                    self.manager.delete(to_delete)
                    st.rerun()


def render():
    AssetsPage().render()


if __name__ == "__main__":
    st.set_page_config(page_title="Assets", page_icon="💰")
    render()
