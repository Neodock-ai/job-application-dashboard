import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import io

# Add CSS for better styling in Streamlit
st.markdown("""
<style>
    /* Customize button styles */
    .stButton>button {
        font-size: 16px;
        color: white;
        background-color: #4CAF50;
        border-radius: 8px;
        padding: 10px 20px;
    }

    /* Style the title and headers */
    .stMarkdown h1 {
        font-size: 36px;
        color: #4CAF50;
    }
    .stMarkdown h2 {
        font-size: 28px;
        color: #4CAF50;
    }
    .stMarkdown h3 {
        font-size: 24px;
        color: #4CAF50;
    }

    /* Customize data table appearance */
    .dataframe {
        background-color: #f9f9f9;
        color: #333;
        font-size: 14px;
    }

    /* Style download buttons */
    .stDownloadButton>button {
        font-size: 14px;
        background-color: #007ACC;
        color: white;
        border-radius: 5px;
        padding: 8px 15px;
    }

    /* Center the Streamlit app content */
    .css-1d391kg { 
        align-items: center;
        justify-content: center;
    }
</style>
""", unsafe_allow_html=True)

# Function to fetch list of common drugs (for demo)
def get_drug_list():
    # Static list of common drugs for demonstration purposes
    return ["aspirin", "ibuprofen", "acetaminophen", "metformin", "lisinopril"]

# Caching the data fetching function to avoid repeated API calls
@st.cache_data(ttl=3600)  # Cache data for 1 hour
def fetch_data(drug_name, limit=100):
    url = f"https://api.fda.gov/drug/event.json?search=patient.drug.medicinalproduct:{drug_name}&limit={limit}"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for HTTP codes 4XX/5XX
        data = response.json().get("results", [])
        if not data:
            st.warning("No data available for this drug.")
        return data
    except requests.exceptions.RequestException as e:
        st.error("Failed to connect to the OpenFDA API. Please check your internet connection or try again later.")
        return []
    except ValueError:
        st.error("Unexpected response format from OpenFDA API.")
        return []

# Enhanced function to process and analyze the data
def process_data(data):
    try:
        # Convert to DataFrame
        df = pd.json_normalize(data)

        # Check for required columns before proceeding
        if 'patient.reaction' not in df.columns:
            st.warning("Data format changed or missing key fields. Cannot display reactions.")
            return None, None, None

        # Extract and count most common reactions
        reactions = df['patient.reaction'].apply(lambda x: [reaction.get('reactionmeddrapt', 'Unknown') for reaction in x] if isinstance(x, list) else [])
        reactions_flattened = pd.Series([item for sublist in reactions for item in sublist])
        most_common_reactions = reactions_flattened.value_counts().head(10)
        
        # Process time trend of adverse events
        df['date'] = pd.to_datetime(df['receivedate'], errors='coerce')
        events_over_time = df.groupby(df['date'].dt.to_period("M")).size()
        
        return df, most_common_reactions, events_over_time

    except Exception as e:
        st.error(f"Error processing data: {str(e)}")
        return None, None, None

# Function to create the dashboard with advanced features
def create_dashboard(df, most_common_reactions, events_over_time):
    if df is None or most_common_reactions is None or events_over_time is None:
        st.warning("Unable to display the dashboard due to missing or invalid data.")
        return

    # Top Reactions Plot
    st.subheader("Top 10 Reported Adverse Reactions")
    fig, ax = plt.subplots()
    most_common_reactions.plot(kind='barh', ax=ax)
    ax.set_xlabel("Count")
    st.pyplot(fig)

    # Adverse Events Over Time Plot
    st.subheader("Adverse Events Over Time")
    fig, ax = plt.subplots()
    events_over_time.plot(kind='line', ax=ax)
    ax.set_xlabel("Date")
    ax.set_ylabel("Number of Events")
    st.pyplot(fig)

    # Demographic Analysis
    st.subheader("Demographic Analysis")
    if 'patient.patientsex' in df.columns:
        sex_distribution = df['patient.patientsex'].value_counts()
        fig, ax = plt.subplots()
        sex_distribution.plot(kind='bar', ax=ax)
        ax.set_title("Sex Distribution of Adverse Events")
        st.pyplot(fig)

    if 'patient.patientonsetage' in df.columns:
        fig, ax = plt.subplots()
        sns.histplot(df['patient.patientonsetage'].dropna(), kde=True, ax=ax)
        ax.set_title("Age Distribution of Patients")
        st.pyplot(fig)

    # Severity Analysis
    st.subheader("Severity Analysis")
    severity_fields = ['serious', 'seriousnesshospitalization', 'seriousnessother']
    for field in severity_fields:
        if field in df.columns:
            fig, ax = plt.subplots()
            df[field].value_counts().plot(kind='bar', ax=ax)
            ax.set_title(f"{field.replace('seriousness', 'Seriousness ').capitalize()} Counts")
            st.pyplot(fig)

    # Display Interactive Data Table
    st.subheader("Adverse Event Data")
    st.dataframe(df)  # Show all data with search and sorting capabilities

    # Data Export Options
    st.subheader("Export Data")
    csv = df.to_csv(index=False)
    json_data = df.to_json(orient='records')
    
    # Use BytesIO for Excel export
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    excel_data = excel_buffer.getvalue()
    
    # Download buttons
    st.download_button("Download CSV", data=csv, file_name="adverse_event_data.csv", mime="text/csv")
    st.download_button("Download JSON", data=json_data, file_name="adverse_event_data.json", mime="application/json")
    st.download_button("Download Excel", data=excel_data, file_name="adverse_event_data.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# Streamlit App Layout with Enhanced UI
st.title("Drug Adverse Event Dashboard")

# Dropdown to select drug and input for limit
drug_list = get_drug_list()
drug_name = st.selectbox("Select Drug Name", drug_list)
limit = st.number_input("Number of Records to Fetch", min_value=1, max_value=1000, value=100)

if st.button("Fetch Data"):
    data = fetch_data(drug_name, limit)
    if data:
        df, most_common_reactions, events_over_time = process_data(data)
        create_dashboard(df, most_common_reactions, events_over_time)
    else:
        st.warning("No data available for the selected drug.")
