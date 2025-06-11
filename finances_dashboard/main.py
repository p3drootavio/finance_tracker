# Import third-party libraries
import streamlit as st
from views import assets, budget, home, transactions, investments


def main():
    # Page factory: maps names to functions
    pages = {
        "Home": home.render,
        "Assets": assets.render,
        "Budget": budget.render,
        "Investments": investments.render,
        "Transactions": transactions.render
    }

    # Sidebar navigation
    selected_page = st.sidebar.radio("📂 Navigation", list(pages.keys()))
    pages[selected_page]()


if __name__ == "__main__":
    main()
