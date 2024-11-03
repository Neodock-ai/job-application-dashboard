import streamlit as st
import sqlite3
from transformers import pipeline
from datetime import datetime
import pandas as pd
import os
import re
from io import BytesIO

# Initialize SQLite database
conn = sqlite3.connect("job_applications.db")
cursor = conn.cursor()

# Check if salary column exists; if not, add it
try:
    cursor.execute('ALTER TABLE applications ADD COLUMN salary TEXT')
    conn.commit()
except sqlite3.OperationalError:
    pass  # Column already exists or table has not been created yet

# Create table if it doesn't exist
cursor.execute('''CREATE TABLE IF NOT EXISTS applications (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  job_title TEXT,
                  company TEXT,
                  location TEXT,
                  requirements TEXT,
                  salary TEXT,
                  date TEXT
                  )''')
conn.commit()

# Initialize Hugging Face NER pipeline
ner_pipeline = pipeline("ner", model="dbmdz/bert-large-cased-finetuned-conll03-english", grouped_entities=True)

# Function to extract job details using Hugging Face Transformers
def extract_job_details(description):
    entities = ner_pipeline(description)
    job_details = {
        "Job Title": "",
        "Company": "",
        "Location": "",
        "Requirements": "",
        "Salary": ""
    }
    
    # Improved salary extraction pattern
    salary_match = re.search(r"\$\d{2,3}(?:,\d{3})?(?:K)?(?:\s*-\s*\$\d{2,3}(?:,\d{3})?(?:K)?)?", description, re.IGNORECASE)
    if salary_match:
        job_details["Salary"] = salary_match.group().strip()

    requirements = []
    for entity in entities:
        if entity['entity_group'] == 'ORG' and not job_details["Company"]:
            job_details["Company"] = entity['word']
        elif entity['entity_group'] == 'LOC' and not job_details["Location"]:
            job_details["Location"] = entity['word']

    # Use rule-based matching for job title and requirements
    for line in description.splitlines():
        if "role:" in line.lower() or "title" in line.lower():
            job_details["Job Title"] = line.replace("Role:", "").replace("Title:", "").strip()
        elif any(keyword in line.lower() for keyword in ["requirement", "responsibility", "duties", "developing", "analyzing"]):
            requirements.append(line.strip())
    
    job_details["Requirements"] = " ".join(requirements)
    return job_details

# Function to create a downloadable Excel file from DataFrame
def download_excel(dataframe):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        dataframe.to_excel(writer, index=False, sheet_name='Applications')
    output.seek(0)
    return output

# Streamlit App
st.title("Job Application Tracking Dashboard")

description = st.text_area("Paste the Job Description Here")

if st.button("Extract and Save Job Details"):
    job_details = extract_job_details(description)
    job_details["Date"] = datetime.now().strftime("%Y-%m-%d")

    st.write("**Extracted Job Details:**")
    for key, value in job_details.items():
        st.write(f"**{key}:** {value}")

    cursor.execute('''INSERT INTO applications (job_title, company, location, requirements, salary, date)
                      VALUES (?, ?, ?, ?, ?, ?)''', (
                      job_details["Job Title"],
                      job_details["Company"],
                      job_details["Location"],
                      job_details["Requirements"],
                      job_details["Salary"],
                      job_details["Date"]
                      ))
    conn.commit()
    
    st.success("Job details saved successfully!")

# Load data from SQLite and display it in an interactive table
df = pd.read_sql_query("SELECT id, job_title, company, location, requirements, salary, date FROM applications", conn)
st.subheader("All Tracked Job Applications")
st.dataframe(df.drop(columns=['id']))  # Display without 'id' column for readability

# Download button for exporting table as an Excel file
st.download_button(
    label="Download as Excel",
    data=download_excel(df.drop(columns=['id'])),
    file_name="job_applications.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# Delete a job entry
st.subheader("Delete a Job Entry")

# Use only numeric part of the ID for deletion
job_to_delete = st.selectbox("Select a Job to Delete", df['id'].apply(lambda x: f"ID {x}: {df.loc[df['id'] == x, 'job_title'].values[0]} - {df.loc[df['id'] == x, 'company'].values[0]}"))

if st.button("Delete Selected Job"):
    job_id = int(re.search(r"\d+", job_to_delete).group())  # Extract only the numeric ID
    cursor.execute("DELETE FROM applications WHERE id=?", (job_id,))
    conn.commit()
    st.success("Job entry deleted successfully!")
    
    # Refresh the DataFrame to update the table
    df = pd.read_sql_query("SELECT id, job_title, company, location, requirements, salary, date FROM applications", conn)
    st.dataframe(df.drop(columns=['id']))