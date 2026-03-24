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
def process_uploaded_files(uploaded_files, group_col, drop_cols):
    """Combines, cleans, and sorts uploaded CSV/Excel files."""
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

    # Column maintenance
    cols = list(combined_df.columns)
    cols[0] = group_col
    combined_df.columns = cols
    combined_df.drop(columns=drop_cols, errors='ignore', inplace=True)

    # Conversion & Cleaning
    combined_df = combined_df.map(lambda x: clean_to_float(x, num_pattern))
    combined_df.sort_values(by=group_col, ascending=True, inplace=True)
    combined_df.drop_duplicates(inplace=True)
    
    return combined_df.reset_index(drop=True)

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
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

# --- UI LAYOUT ---
st.title("🏗️ Consteel Reaction Extreme Value Finder")
st.markdown("Upload your reaction CSV/Excel files to find the governing min/max values.")

with st.sidebar:
    st.header("Settings")
    group_column = st.text_input("Group Column Name", "Designation")
    components = st.multiselect(
        "Reaction Components", 
        ['Rx [kN]', 'Ry [kN]', 'Rz [kN]', 'Rxx [kNm]', 'Ryy [kNm]', 'Rzz [kNm]'],
        default=['Rx [kN]', 'Ry [kN]', 'Rz [kN]', 'Rxx [kNm]', 'Ryy [kNm]', 'Rzz [kNm]']
    )
    drop_list = st.text_input("Columns to drop (comma separated)", "Dominant").split(',')

# 1. FILE UPLOAD
uploaded_files = st.file_uploader("Upload CSV or Excel files", type=['csv', 'xlsx', 'xls'], accept_multiple_files=True)

if uploaded_files:
    # 2. DATA PROCESSING
    combined_df = process_uploaded_files(uploaded_files, group_column, drop_list)
    
    if combined_df is not None:
        st.subheader("Combined Data Preview")
        st.dataframe(combined_df, width='stretch')

        # 3. EXTREME VALUES CALCULATION
        st.divider()
        st.subheader("📊 Individual Support Extremes")
        
        df_extremes = get_extreme_values(combined_df, group_column, components)
        st.dataframe(df_extremes, width='stretch')

        excel_data = to_excel(df_extremes)
        st.download_button(
            label="📥 Download Individual Extremes (Excel)",
            data=excel_data,
            file_name="Individual Extremes.xlsx",
            mime="application/vnd.ms-excel"
        )

        # 4. GROUPED ANALYSIS
        st.divider()
        st.subheader("👥 Support Group Analysis")
        
        # Get and sort unique values for the UI
        unique_supports = sorted(combined_df[group_column].unique().tolist())

        # Display the available supports so the user knows what to type
        st.info(f"**Available Supports:** {', '.join(map(str, unique_supports))}")

        group_input = st.text_input("Define a support group (e.g., P31, P32, P35, P36)", "P31, P32, P35, P36")
        
        if group_input:
            target_group = [s.strip() for s in group_input.split(',')]
            sub_df = combined_df[combined_df[group_column].astype(str).isin(target_group)]
            
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
                
                group_excel = to_excel(df_group_output)
                st.download_button(
                    label=f"📥 Download Group {group_input[:10]}... Extremes",
                    data=group_excel,
                    file_name="Group_Extremes.xlsx",
                    mime="application/vnd.ms-excel"
                )
            else:
                st.warning("No data found for the specified group members.")
else:
    st.info("Please upload one or more files to begin.")