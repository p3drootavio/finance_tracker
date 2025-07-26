"""Budget tab view for the Streamlit finances dashboard.

Monthly budgeting across three major groups: **Expenses, Income, Investments**.
The page filters the uploaded transactions to the selected month, compares
**Planned** vs **Actual**, and shows the **Result** with sensible signs:

- **Expenses & Investments** → `Result = Planned - Actual`  (positive = good)
- **Income**                 → `Result = Actual - Planned`  (positive = good)

Data is persisted to ``budget.json`` keyed by year-month (``YYYY-MM``).
This mirrors the Home page structure (manager class + page class + `render`).
"""

# Import standard libraries
import json
import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Literal

# Import third-party libraries
import pandas as pd
import plotly.express as px
import streamlit as st


HEADER_ICON = "📊"
BUDGET_FILE = "budget.json"
COLUMN_WEIGHTS = [2, 1]
MAJORS = ("Expenses", "Income", "Investments")


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _month_key(dt: pd.Timestamp) -> str:
    """Return canonical key 'YYYY-MM' for a date-like value."""
    ts = pd.to_datetime(dt)
    return f"{ts.year:04d}-{ts.month:02d}"


def _ensure_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


# ---------------------------------------------------------------------------
# Budget persistence layer
# ---------------------------------------------------------------------------

@dataclass
class BudgetEntry:
    major: Literal["Expenses", "Income", "Investments"]
    category: str
    planned: float

    def to_dict(self) -> Dict[str, object]:
        return {"major": self.major, "category": self.category, "planned": float(self.planned)}


class BudgetManager:
    """Load/save monthly planned budgets and offer helpers to edit them."""

    def __init__(self, file_path: str = BUDGET_FILE) -> None:
        self.file_path = file_path
        # structure: { "YYYY-MM": [ {major, category, planned}, ... ] }
        self.data: Dict[str, List[Dict[str, object]]] = {}

    # --------------------------- persistence -------------------------------
    def load(self) -> None:
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except json.JSONDecodeError:
                st.error("Failed to load budget.json. Starting with an empty budget.")
                self.data = {}
        st.session_state["budget_data"] = self.data


    def save(self) -> None:
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        st.session_state["budget_data"] = self.data

    # --------------------------- accessors ---------------------------------
    def get_month_df(self, month_key: str) -> pd.DataFrame:
        rows = self.data.get(month_key, [])
        if not rows:
            return pd.DataFrame(columns=["major", "category", "planned"], dtype=object)
        return pd.DataFrame(rows)


    def set_month_df(self, month_key: str, df: pd.DataFrame) -> None:
        safe = (
            df[["major", "category", "planned"]]
            .dropna(subset=["major", "category"]).copy()
        )
        # coerce
        safe["planned"] = pd.to_numeric(safe["planned"], errors="coerce").fillna(0.0)
        safe["major"] = safe["major"].astype(str)
        safe["category"] = safe["category"].astype(str)
        self.data[month_key] = safe.to_dict(orient="records")
        self.save()


# ---------------------------------------------------------------------------
# Page logic
# ---------------------------------------------------------------------------

class BudgetPage:
    def __init__(self) -> None:
        self.manager = BudgetManager()

    # --------------------------- public API --------------------------------
    def render(self) -> None:
        st.header(f"{HEADER_ICON} Budget")
        st.caption("Plan each month and compare against actual transactions.")

        # Load persisted budgets
        self.manager.load()

        # Month selector (first day of current month default)
        default_month = pd.Timestamp.today().replace(day=1)
        month_date = st.date_input("Select month", value=default_month)
        month = _month_key(month_date)

        # Fetch current month plan and create an editable grid
        month_df = self._ensure_minimal_plan(self.manager.get_month_df(month))
        edited_df = self._edit_plan(month_df)

        # Save plan if requested
        if st.button("💾 Save Budget", type="primary"):
            self.manager.set_month_df(month, edited_df)
            st.success("Budget saved.")

        # Compute actual from transactions held in session_state
        actuals = self._compute_actuals(month, edited_df)

        # Render visuals and per‑major tables
        self._render_top_cards(actuals)
        self._render_major_blocks(actuals)

    # --------------------------- helpers -----------------------------------
    def _ensure_minimal_plan(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            # Provide a starter template for convenience
            df = pd.DataFrame(
                [
                    {"major": "Expenses", "category": "Groceries", "planned": 0.0},
                    {"major": "Expenses", "category": "Housing and Meal Plan", "planned": 0.0},
                    {"major": "Income", "category": "Work-on Campus", "planned": 0.0},
                    {"major": "Investments", "category": "High-Yield Savings", "planned": 0.0},
                ]
            )
        # enforce column order/types
        df = df.copy()
        for col in ("major", "category", "planned"):
            if col not in df.columns:
                df[col] = None
        df = df[["major", "category", "planned"]]
        return df


    def _edit_plan(self, df: pd.DataFrame) -> pd.DataFrame:
        st.subheader("Planned Budget (editable)")
        edited = st.data_editor(
            df,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "major": st.column_config.SelectboxColumn("Major", options=list(MAJORS)),
                "category": st.column_config.TextColumn("Category"),
                "planned": st.column_config.NumberColumn("Planned", format="$%.2f"),
            },
            key="budget_editor",
        )
        return edited

    # --------------------------- calculations ------------------------------
    def _compute_actuals(self, month_key: str, plan_df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """Return dict of per‑major DataFrames with Planned, Actual, Result.

        We read transactions from `st.session_state.debits_df` and
        `st.session_state.credits_df`, which the Home page already sets.
        - Expenses & Investments pull from **debits_df** (absolute amounts)
        - Income pulls from **credits_df**
        Only rows for the selected **month** and **matching categories** are used.
        """
        # prepare month filter helpers
        debits = st.session_state.get("debits_df", pd.DataFrame()).copy()
        credits = st.session_state.get("credits_df", pd.DataFrame()).copy()

        for df in (debits, credits):
            if not df.empty and "Posting Date" in df.columns:
                df["_date"] = _ensure_datetime(df["Posting Date"])
                df["_ym"] = df["_date"].dt.strftime("%Y-%m")

        out: Dict[str, pd.DataFrame] = {}
        for major in MAJORS:
            subset = plan_df[plan_df["major"] == major].copy()
            if subset.empty:
                out[major] = pd.DataFrame(columns=["Category", "Planned", "Actual", "Result"])
                continue

            categories = subset["category"].dropna().astype(str).tolist()

            if major == "Income":
                base = credits
                amt = "Amount"  # positive inflow
                agg_df = (
                    base[(base.get("_ym") == month_key) & (base["Category"].isin(categories))]
                    .groupby("Category", dropna=False)[amt]
                    .sum()
                    .reset_index()
                )
                subset.rename(columns={"category": "Category", "planned": "Planned"}, inplace=True)
                merged = subset.merge(agg_df, on="Category", how="left").fillna({"Amount": 0.0})
                merged.rename(columns={"Amount": "Actual"}, inplace=True)
                merged["Result"] = merged["Actual"] - merged["Planned"]  # positive good

            else:  # Expenses or Investments
                base = debits
                if base.empty:
                    actual_series = pd.Series(0.0, index=pd.Index([], name="Category"))
                agg_df = (
                    base[(base.get("_ym") == month_key) & (base["Category"].isin(categories))]
                    .assign(_abs=lambda d: d["Amount"].abs())
                    .groupby("Category", dropna=False)["_abs"]
                    .sum()
                    .reset_index()
                    .rename(columns={"_abs": "Actual"})
                )
                subset.rename(columns={"category": "Category", "planned": "Planned"}, inplace=True)
                merged = subset.merge(agg_df, on="Category", how="left").fillna({"Actual": 0.0})
                merged["Result"] = merged["Planned"] - merged["Actual"]  # positive good

            # order columns and compute totals row
            merged = merged[["Category", "Planned", "Actual", "Result"]]
            totals = pd.DataFrame({
                "Category": ["Totals"],
                "Planned": [merged["Planned"].sum()],
                "Actual": [merged["Actual"].sum()],
                "Result": [merged["Result"].sum()],
            })
            out[major] = pd.concat([totals, merged], ignore_index=True)
        return out

    # --------------------------- rendering ---------------------------------
    def _render_top_cards(self, actuals: Dict[str, pd.DataFrame]) -> None:
        """Top summary metrics stacked vertically (no column layout)."""
        e, i, v = (actuals.get("Expenses"), actuals.get("Income"), actuals.get("Investments"))
        if e is not None and not e.empty:
            st.metric("Expenses Result", f"${e.iloc[0]['Result']:,.2f}")
        if i is not None and not i.empty:
            st.metric("Income Result", f"${i.iloc[0]['Result']:,.2f}")
        if v is not None and not v.empty:
            st.metric("Investments Result", f"${v.iloc[0]['Result']:,.2f}")
        st.markdown("---")

    def _style_result(self, df: pd.DataFrame, major: str) -> "pd.io.formats.style.Styler":
        def colorize(val: float) -> str:
            # positive is good for all as per sign convention above
            if pd.isna(val):
                return ""
            return "color: #2e7d32; font-weight: 600;" if val >= 0 else "color: #c62828; font-weight: 600;"
        styler = df.style.format({"Planned": "${:,.2f}", "Actual": "${:,.2f}", "Result": "${:,.2f}"})
        styler = styler.applymap(colorize, subset=["Result"])  # type: ignore[arg-type]
        return styler

    def _render_major_blocks(self, actuals: Dict[str, pd.DataFrame]) -> None:
        col_left, col_right = st.columns(COLUMN_WEIGHTS)


        self._render_block("Expenses", actuals.get("Expenses", pd.DataFrame()))

        self._render_block("Income", actuals.get("Income", pd.DataFrame()))

        self._render_block("Investments", actuals.get("Investments", pd.DataFrame()))

    def _render_block(self, title: str, df: pd.DataFrame) -> None:
        st.subheader(title)
        if df.empty:
            st.info("No data for this section yet.")
            return
        st.dataframe(self._style_result(df, title), hide_index=True, use_container_width=True)

        # Build a pie chart from non-total rows
        body = df[df["Category"] != "Totals"].copy()
        if not body.empty:
            values_col = "Actual" if title == "Income" else "Actual"  # same column, but kept for clarity
            fig = px.pie(body, names="Category", values=values_col, hole=0.3, width=380, height=380)
            st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def render() -> None:
    BudgetPage().render()


if __name__ == "__main__":
    render()
