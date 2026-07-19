import streamlit as st
import os
import zipfile
from io import BytesIO

# Import your publisher logic here
# from master_publisher import run_master_publisher

st.set_page_config(page_title="Sakura Series Publisher", layout="centered")

st.title("🌸 Sakura Series Publisher")
st.write("Generate your KDP interiors and metadata on the go.")

if st.button("Generate Full Series"):
    with st.spinner("Engineering your PDFs..."):
        # run_master_publisher() # This runs your series logic

        # Create a zip file of all outputs for easy downloading
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            for root, dirs, files in os.walk("."):
                for file in files:
                    if file.endswith((".pdf", ".txt")):
                        zip_file.write(os.path.join(root, file))

        st.success("Series generated successfully!")
        st.download_button(
            label="Download All Journals & Metadata",
            data=zip_buffer.getvalue(),
            file_name="Sakura_Series_Production.zip",
            mime="application/zip"
        )

st.info("Ensure template.pdf and all *_prompts.csv files are in the repository.")