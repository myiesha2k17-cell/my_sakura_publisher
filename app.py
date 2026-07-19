import streamlit as st
import os
from master_publisher import run_master_publisher

st.set_page_config(page_title="Sakura Series Studio", layout="centered")

st.title("🌸 Sakura Series Production")

# 1. Automatically find all CSVs in the /data folder
data_folder = "data"
csv_files = [f for f in os.listdir(data_folder) if f.endswith(".csv")]

# 2. Dropdown for user to select the journal
selected_file = st.selectbox("Select a Series Journal to Generate:", csv_files)

# 3. Text input for output file name
series_name = st.text_input("Name the Output PDF:",
                            value=selected_file.replace("_prompts.csv", "").replace("sakura_", "").title())

if st.button("Generate Selected Journal"):
    with st.spinner(f"Generating {series_name}..."):
        csv_path = os.path.join(data_folder, selected_file)
        output_name = f"{series_name.replace(' ', '_')}_Journal.pdf"

        # Call the logic from master_publisher
        run_master_publisher(csv_path, output_name)

        with open(output_name, "rb") as f:
            st.download_button("Download PDF", f, file_name=output_name)

        st.success("Finished!")