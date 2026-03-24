import streamlit as st
import pandas as pd
import re
import io

# --- PAGE CONFIG ---
st.set_page_config(page_title="Consteel Reaction Processor", layout="wide")

# --- CORE LOGIC FUNCTIONS ---
def clean_to_float(val, num_pattern):
    """Handles European float conversion (comma to period)."""
    if isinstance(val, str):
        val_stripped = val.strip()
        if num_pattern.match(val_stripped):
            return float(val_stripped.replace(',', '.'))
    elif isinstance(val, (int, float)):
        return float(val)
    return val

@st.cache_data
def load_raw_combined_data(uploaded_files):
    """Combines files without renaming columns yet to allow for selection."""
    all_dfs = []
    num_pattern = re.compile(r'^-?\d+(?:,\d+)?$')

    for uploaded_file in uploaded_files:
        if uploaded_file.name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file)
        else:
            df = pd.read_csv(uploaded_file, sep=None, engine='python', on_bad_lines='skip')
        all_dfs.append(df)

    if not all_dfs:
        return None

    combined_df = pd.concat(all_dfs, ignore_index=True)
    
    # Cleaning numeric values immediately
    combined_df = combined_df.map(lambda x: clean_to_float(x, num_pattern))
    combined_df.drop_duplicates(inplace=True)
    
    return combined_df

def get_extreme_values(df, group_col, component_list):
    """Calculates min/max for each designation."""
    extreme_rows = []
    unique_groups = df[group_col].unique()

    for group_val in unique_groups:
        subset = df[df[group_col] == group_val]
        for comp in component_list:
            if comp in subset.columns:
                idx_min = subset[comp].idxmin()
                idx_max = subset[comp].idxmax()
                
                row_min = df.loc[[idx_min]].copy()
                row_min['Extreme Type'] = f"{comp}_MIN"
                row_max = df.loc[[idx_max]].copy()
                row_max['Extreme Type'] = f"{comp}_MAX"
                
                extreme_rows.extend([row_min, row_max])
    
    return pd.concat(extreme_rows).reset_index(drop=True)

def to_excel(df):
    """Converts dataframe to an Excel buffer for download."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()


# --- UI LAYOUT ---
st.title("🏗️ Consteel Reaction Extreme Value Finder")

uploaded_files = st.file_uploader("Upload CSV or Excel files", type=['csv', 'xlsx', 'xls'], accept_multiple_files=True)

if uploaded_files:
    # 1. INITIAL DATA LOAD
    raw_df = load_raw_combined_data(uploaded_files)
    all_columns = raw_df.columns.tolist()

    with st.sidebar:
        st.header("Settings")
        
        # 2. DYNAMIC GROUP COLUMN SELECTION
        # Defaults to the first column [index=0]
        group_column = st.selectbox(
            "Select Grouping Column (ID)", 
            options=all_columns, 
            index=0,
            help="This column identifies individual supports. It defaults to the first column in your file."
        )
        
        # Option to rename that column if needed (optional)
        # rename_col = st.checkbox("Rename this column in export?", value=False)
        # final_group_name = group_column
        # if rename_col:
        #     final_group_name = st.text_input("New Name", value="Designation")

        # 3. COLUMN DROPPING
        cols_to_drop = st.multiselect(
            "Select columns to remove/drop:",
            options=[c for c in all_columns if c != group_column],
            default=[]
        )
        
        # 4. COMPONENT SELECTION
        remaining_cols = [c for c in all_columns if c not in cols_to_drop and c != group_column]
        default_comps = [c for c in ['Rx [kN]', 'Ry [kN]', 'Rz [kN]', 'Rxx [kNm]', 'Ryy [kNm]', 'Rzz [kNm]'] if c in remaining_cols]
        
        components = st.multiselect(
            "Reaction Components for Analysis", 
            options=remaining_cols,
            default=default_comps
        )

    # Apply processing based on sidebar choices
    combined_df = raw_df.drop(columns=cols_to_drop)
    active_group_col = group_column

    combined_df.sort_values(by=active_group_col, ascending=True, inplace=True)
    combined_df.reset_index()
    

    # --- DATA DISPLAY & ANALYSIS ---
    st.subheader("Combined Data Preview")
    number_of_rows = st.number_input(label="Number of rows to see", value=5, step=1, width=200)
    st.dataframe(combined_df.head(number_of_rows), use_container_width=True)

    # 3. EXTREME VALUES CALCULATION
    st.divider()
    st.subheader("📊 Individual Support Extremes")
    
    df_extremes = get_extreme_values(combined_df, active_group_col, components)
    st.dataframe(df_extremes, use_container_width=True)

    excel_data = to_excel(df_extremes)
    st.download_button(
        label="📥 Download Individual Extremes (Excel)",
        data=excel_data,
        file_name="Reaction Extremes for each support.xlsx",
        mime="application/vnd.ms-excel"
    )

    # 4. GROUPED ANALYSIS (Checkbox List / Multiselect)
    st.divider()
    st.subheader("👥 Support Group Analysis")
    
    unique_supports = sorted(combined_df[active_group_col].unique().tolist())
    
    selected_group = st.multiselect("Select supports for group analysis:", options=unique_supports)

    if selected_group:
        sub_df = combined_df[combined_df[active_group_col].isin(selected_group)]
        
        if not sub_df.empty:
            group_extreme_rows = []
            for comp in components:
                if comp in sub_df.columns:
                    idx_min = sub_df[comp].idxmin()
                    idx_max = sub_df[comp].idxmax()
                    
                    row_min = combined_df.loc[[idx_min]].copy()
                    row_min['Type'] = f"{comp}_MIN"
                    row_max = combined_df.loc[[idx_max]].copy()
                    row_max['Type'] = f"{comp}_MAX"
                    group_extreme_rows.extend([row_min, row_max])
            
            df_group_output = pd.concat(group_extreme_rows, ignore_index=True)
            st.dataframe(df_group_output, use_container_width=True)
            
            # --- DYNAMIC FILENAME CONSTRUCTION ---
            # 1. Join names with underscores
            group_names_str = "_".join(map(str, selected_group))
            
            # 2. Basic cleanup: replace spaces or dots with underscores for a cleaner filename
            clean_names = group_names_str.replace(" ", "_").replace(".", "_")
            
            # 3. Final filename string
            dynamic_filename = f"Group_Extremes_{clean_names}.xlsx"

            group_excel = to_excel(df_group_output)
            st.download_button(
                label="📥 Download Group Extremes",
                data=group_excel,
                file_name=dynamic_filename,
                mime="application/vnd.ms-excel"
            )
else:
    st.info("Please upload one or more files to begin.")