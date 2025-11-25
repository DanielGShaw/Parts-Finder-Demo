import streamlit as st
import pandas as pd
from adapters import get_enabled_adapters
from normalizer import normalize_results, dedupe_rows
import os
import json
import glob
from datetime import datetime
import asyncio

# Issue reporting configuration
ISSUE_REPORT_PREFIX = "demo"

def save_issue_report(report_data: dict) -> str:
    """Save an issue report to a file in issues/ directory.

    Returns the filepath of the saved report.
    """
    # Ensure the issues directory exists
    issues_dir = os.path.join(os.path.dirname(__file__), '..', 'issues')
    os.makedirs(issues_dir, exist_ok=True)

    # Find the next issue number for this prefix
    pattern = os.path.join(issues_dir, f'*_{ISSUE_REPORT_PREFIX}*.json')
    existing_files = glob.glob(pattern)

    if existing_files:
        # Extract numbers from filenames and find max
        numbers = []
        for f in existing_files:
            basename = os.path.basename(f)
            # Extract the number after the prefix letter
            try:
                num_part = basename.split(f'_{ISSUE_REPORT_PREFIX}')[1].split('.')[0]
                numbers.append(int(num_part))
            except (IndexError, ValueError):
                continue
        next_num = max(numbers, default=0) + 1
    else:
        next_num = 1

    # Create filename
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    filename = f'{timestamp}_{ISSUE_REPORT_PREFIX}{next_num:03d}.json'
    filepath = os.path.join(issues_dir, filename)

    # Save the report
    with open(filepath, 'w') as f:
        json.dump(report_data, f, indent=2)

    return filepath


def show_error_report_dialog():
    """Show an error reporting form to collect user feedback and error details."""
    # Create a visually distinct container for the form
    with st.container():
        st.subheader("Report an Issue")

        with st.form(key='error_report_form'):
            st.write("Please describe the problem you encountered:")

            # Error details
            error_summary = st.text_input("Briefly describe the issue", key="error_summary")
            error_details = st.text_area("More details about the issue", height=150, key="error_details",
                                        value=f"Registration: {st.session_state.get('last_rego', 'N/A')}\n"
                                              f"State: {st.session_state.get('last_state', 'N/A')}\n"
                                              f"Suppliers: {st.session_state.get('last_suppliers', 'N/A')}\n"
                                              f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

            col1, col2 = st.columns(2)
            with col1:
                submitted = st.form_submit_button("Submit Error Report", type="primary")
            with col2:
                cancelled = st.form_submit_button("Cancel", type="secondary")

            if cancelled:
                # Close the dialog without submitting
                st.session_state["show_error_dialog"] = False
                st.rerun()

            if submitted:
                # Process the error report
                if error_summary.strip() == "":
                    st.warning("Please provide a brief summary of the issue.")
                    return False

                # Save the error report to a file
                error_report_data = {
                    "summary": error_summary,
                    "details": error_details,
                    "rego": st.session_state.get('last_rego', 'N/A'),
                    "state": st.session_state.get('last_state', 'N/A'),
                    "suppliers": st.session_state.get('last_suppliers', 'N/A'),
                    "timestamp": datetime.now().isoformat()
                }

                save_issue_report(error_report_data)
                st.success("Thank you for reporting this issue! It has been saved for review.")

                # Close the modal by resetting the session state
                st.session_state["show_error_dialog"] = False
                st.rerun()

def show_error_report_button():
    """Display the error reporting button in the sidebar"""
    def open_dialog():
        st.session_state["show_error_dialog"] = True

    if st.button("Report an Issue", key="report_issue_button", on_click=open_dialog):
        pass  # The actual state change happens in the callback

# Initialize session state variables if they don't exist
if 'show_error_dialog' not in st.session_state:
    st.session_state.show_error_dialog = False

st.set_page_config(page_title="Parts Finder Demo", layout="wide")

st.title("🧰 Parts Finder")

# --- Sidebar controls ---
st.sidebar.header("Controls")

st.sidebar.subheader("Suppliers")
available_adapters = get_enabled_adapters()
supplier_names = [a.name for a in available_adapters]
enabled_suppliers = st.sidebar.multiselect("Enabled Suppliers", supplier_names, default=supplier_names)

st.sidebar.divider()
show_costs = st.sidebar.toggle(":eye:", value=False, help="Display cost price columns in the results.")

# Add the error reporting button to the sidebar
show_error_report_button()

# Show the error report form in the main content area when requested
if st.session_state.get('show_error_dialog', False):
    show_error_report_dialog()
else:
    # Make sure flag is definitely False when not showing
    st.session_state.show_error_dialog = False

# --- Main controls ---
st.subheader("Vehicle Search")
rego = st.text_input("Registration", value="ABC123")
state = st.selectbox("State", ["VIC", "NSW", "QLD", "SA", "WA", "TAS", "ACT", "NT"], index=0)

st.info("Searching for parts related to: **Oil Filter, Air Filter, Cabin Air Filter**.")

run = st.button("Search for Parts")

# --- Helper functions for data retrieval ---
async def run_demo_search(enabled_adapters, rego, state):
    """Retrieve data from all suppliers using async pattern."""
    async def run_all_retrievals_async():
        supplier_tasks = {}
        for adapter in enabled_adapters:
            task = asyncio.create_task(run_single_retrieval(adapter, rego, state))
            supplier_tasks[adapter.name] = task

        # Wait for all tasks to complete
        await asyncio.gather(*supplier_tasks.values(), return_exceptions=True)

        all_parts = []
        for supplier_name, task in supplier_tasks.items():
            if not task.cancelled():
                try:
                    result = task.result()
                    all_parts.extend(result)
                except Exception as e:
                    st.warning(f"Error retrieving from {supplier_name}: {str(e)}")

        return all_parts

    async def run_single_retrieval(adapter, rego, state):
        try:
            if hasattr(adapter, 'fetch_async'):
                return await adapter.fetch_async(rego=rego, state=state)
            else:
                return adapter.fetch(rego=rego, state=state)
        except Exception as e:
            raise e

    try:
        return await run_all_retrievals_async()
    except Exception as e:
        st.error(f"An error occurred during data retrieval: {str(e)}")
        return []


# --- Run search ---
if run:
    # Store search parameters for error reporting
    st.session_state.last_rego = rego
    st.session_state.last_state = state
    st.session_state.last_suppliers = enabled_suppliers

    # Clear previous results on new search
    if 'selected_row_details' in st.session_state:
        st.session_state.selected_row_details = None
    st.session_state.df = pd.DataFrame()

    enabled_adapters = [adapter for adapter in available_adapters if adapter.name in enabled_suppliers]

    with st.spinner("Fetching results..."):
        results = asyncio.run(run_demo_search(enabled_adapters, rego, state))

        if not results:
            st.warning("No results found. Try another rego or check the data.")
            st.session_state.df = pd.DataFrame()
        else:
            df = pd.DataFrame(normalize_results(results))
            df = dedupe_rows(df)
            st.session_state.df = df

# --- Display results if they exist in session state ---
if 'df' in st.session_state and not st.session_state.df.empty:
    df = st.session_state.df
    st.success(f"Found {len(df)} unique results across {len(enabled_suppliers)} supplier(s).")

    # Group by category and display sorted tables
    grouped = df.groupby("category")

    for category, group_df in grouped:
        st.subheader(f"{category} ({len(group_df)} options)")

        # Refined sort: 1. Availability, 2. Cost Price (primary), 3. Qty (tie-breaker)
        # Create availability grouping: available > not available
        # All available parts compete on price regardless of whether specific quantity is known
        group_df['availability_with_stock'] = group_df.apply(
            lambda row: 1 if row['is_available'] else 0, axis=1)

        sorted_group = group_df.sort_values(
            by=['availability_with_stock', 'cost_ex_gst', 'availability_qty_sort'],
            ascending=[False, True, False]
        )

        # Drop the helper column after sorting
        sorted_group = sorted_group.drop('availability_with_stock', axis=1)

        # Rename columns for display
        display_df = sorted_group.rename(columns={
            "part_no": "Part Number",
            "supplier": "Supplier",
            "description": "Description",
            "rrp_inc_gst": "RRP (Inc. GST)",
            "cost_ex_gst": "Cost (Ex. GST)",
            "cost_inc_gst": "Cost (Inc. GST)",
            "availability": "Availability",
            "brand": "Brand",
            "url": "Link"
        })

        # Dynamically set columns to display based on the toggle
        base_cols = ["Supplier", "Part Number", "Description", "RRP (Inc. GST)"]
        cost_cols = ["Cost (Ex. GST)", "Cost (Inc. GST)"]
        end_cols = ["Availability", "Brand", "Link"]

        summary_cols = base_cols
        if show_costs:
            summary_cols = summary_cols + cost_cols
        summary_cols = summary_cols + end_cols

        to_show = [c for c in summary_cols if c in display_df.columns]

        st.dataframe(
            display_df[to_show],
            width='stretch',
            hide_index=True,
            column_config={
                "Link": st.column_config.LinkColumn("Product Link", display_text="Go to Supplier"),
                "RRP (Inc. GST)": st.column_config.NumberColumn(format="$%.2f"),
                "Cost (Ex. GST)": st.column_config.NumberColumn(format="$%.2f"),
                "Cost (Inc. GST)": st.column_config.NumberColumn(format="$%.2f"),
            }
        )
else:
    st.info("Enter a registration and state, then click **Search** to see results from our demo data.")
