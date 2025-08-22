import streamlit as st
import requests
import json
import io
import PyPDF2  # For parsing PDFs
import docx    # For parsing DOCX files

# --- Page Configuration ---
st.set_page_config(
    page_title="AI Job Search Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Helper Function for Real Resume Parsing ---
# This function replaces the old, non-functional file reader.
def get_text_from_file(uploaded_file):
    """Extracts text content from uploaded file (PDF, DOCX, TXT)."""
    text = ""
    try:
        if uploaded_file.type == "application/pdf":
            # Use PyPDF2 to read PDF content
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(uploaded_file.getvalue()))
            for page in pdf_reader.pages:
                text += page.extract_text() or ""
        elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            # Use python-docx to read DOCX content
            document = docx.Document(io.BytesIO(uploaded_file.getvalue()))
            for para in document.paragraphs:
                text += para.text + "\n"
        elif uploaded_file.type == "text/plain":
            # Read plain text file
            text = str(uploaded_file.read(), "utf-8")
        return text
    except Exception as e:
        st.error(f"Error reading file: {e}")
        return None

# --- Mock AI Functions (Replace with your actual AI logic) ---
# For demonstration, these functions return structured mock data.
# In your real app, these would make API calls to your AI service.

def parse_resume_with_ai(resume_text):
    """
    (Mock) Sends resume text to an AI for parsing.
    In a real app, this would be an API call.
    """
    if not resume_text or len(resume_text) < 50:
        return None # Not enough content to parse
    
    # Simulate AI parsing
    return {
        "name": "Jane Doe (from Resume)",
        "email": "jane.doe@email.com",
        "phone": "123-456-7890",
        "summary": "Experienced professional with skills in Python, SQL, and data analysis.",
        "skills": ["Python", "SQL", "Streamlit", "Data Analysis", "Machine Learning"],
        "experience": [
            {"title": "Senior Data Analyst", "company": "Tech Solutions", "years": "3"},
            {"title": "Data Analyst", "company": "Data Corp", "years": "2"}
        ]
    }

def generate_resume_insights(resume_data):
    """(Mock) Generates insights from parsed resume data."""
    if not resume_data:
        return None
    insights = [
        f"Strengths: Strong foundation in {', '.join(resume_data['skills'][:3])}.",
        "Suggestion: Quantify achievements in your experience section (e.g., 'Increased efficiency by 20%').",
        "Job Title Match: Your profile is a strong match for 'Senior Data Analyst' roles."
    ]
    return insights

def search_jobs_with_ai(job_title, location):
    """
    (Mock) Searches for jobs using an AI simulation.
    This function simulates a real API call and returns realistic data.
    """
    # In a REAL application, you would make an API call here.
    # For example, using the requests library like below.
    # We will return mock data to ensure the app is functional.
    st.info(f"Simulating AI job search for '{job_title}' in '{location}'...")
    
    # Example mock data that is more extensive than the fallback
    mock_jobs = {
        "jobs": [
            {
                "id": "job_1", "title": "Senior Data Analyst", "company": "Innovatech", "location": "New York, NY",
                "type": "Full-time", "salary": "$110,000 - $140,000",
                "description": "Innovatech is seeking a Senior Data Analyst to interpret complex datasets and provide actionable insights...",
                "requirements": ["5+ years of experience", "Expertise in SQL and Python", "Experience with BI tools like Tableau"],
                "benefits": ["Health Insurance", "401(k) Matching", "Flexible PTO"],
                "postedDate": "1 day ago", "matchScore": 92, "ats": "Greenhouse"
            },
            {
                "id": "job_2", "title": "Data Analyst", "company": "Data Insights LLC", "location": "New York, NY",
                "type": "Full-time", "salary": "$85,000 - $105,000",
                "description": "Join our dynamic team to analyze large-scale data, create visualizations, and support business decisions...",
                "requirements": ["2+ years experience", "Proficiency in SQL", "Strong analytical skills"],
                "benefits": ["Dental & Vision", "Stock Options", "Remote Work Options"],
                "postedDate": "3 days ago", "matchScore": 88, "ats": "Lever"
            },
            {
                "id": "job_3", "title": "Business Intelligence Analyst", "company": "Quantum Leap", "location": "New York, NY",
                "type": "Contract", "salary": "$75 - $90 / hour",
                "description": "We are looking for a BI Analyst to develop and manage business intelligence solutions...",
                "requirements": ["Experience with Power BI or Tableau", "Data warehousing knowledge", "Excellent communication skills"],
                "benefits": ["Contractor Health Plan", "Flexible Hours"],
                "postedDate": "5 days ago", "matchScore": 85, "ats": "Workable"
            }
        ]
    }
    return mock_jobs

# --- Streamlit UI ---

# Sidebar for navigation
with st.sidebar:
    st.title("🤖 AI Job Search Agent")
    page = st.radio("Choose a page", ["📄 Resume Upload", "🔍 Job Search"])
    st.info("This is a demo application. AI responses are simulated.")

# --- Resume Upload Page ---
if page == "📄 Resume Upload":
    st.header("📄 Resume Analysis")
    st.write("Upload your resume for AI-powered analysis and insights.")
    
    uploaded_file = st.file_uploader(
        "Choose your resume file", 
        type=['pdf', 'txt', 'docx'],
        help="Upload your resume in PDF, TXT, or DOCX format"
    )
    
    if uploaded_file is not None:
        with st.spinner("🤖 Reading and analyzing your resume..."):
            # Use the NEW function to correctly get text from the file
            file_content = get_text_from_file(uploaded_file)
            
            if file_content:
                # Parse resume with AI
                resume_data = parse_resume_with_ai(file_content)
                
                if resume_data:
                    st.session_state.resume_data = resume_data
                    st.success("Resume analyzed successfully!")
                    
                    # Display parsed data and insights
                    st.subheader("Your Resume Summary")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.text_input("Name", resume_data.get("name"), disabled=True)
                    with col2:
                        st.text_input("Email", resume_data.get("email"), disabled=True)
                    
                    st.text_area("AI Summary", resume_data.get("summary"), height=100, disabled=True)

                    st.subheader("AI-Generated Insights")
                    insights = generate_resume_insights(resume_data)
                    for insight in insights:
                        st.markdown(f"- {insight}")
                else:
                    st.error("AI could not parse the resume. The document might be empty or scanned.")
            else:
                st.error("Could not read text from the uploaded file. Please try another file.")

# --- Job Search Page ---
elif page == "🔍 Job Search":
    st.header("🔍 AI-Powered Job Search")
    st.write("Enter your desired job title and location to find relevant openings.")
    
    with st.form("job_search_form"):
        col1, col2 = st.columns([2, 1])
        with col1:
            job_title = st.text_input("Job Title", "Senior Data Analyst")
        with col2:
            location = st.text_input("Location", "New York, NY")
        
        submitted = st.form_submit_button("Search for Jobs")

    if submitted:
        with st.spinner("🤖 AI is searching for the best job matches..."):
            jobs_data = search_jobs_with_ai(job_title, location)
            
            if jobs_data and jobs_data.get("jobs"):
                st.success(f"Found {len(jobs_data['jobs'])} matching jobs!")
                
                for job in jobs_data["jobs"]:
                    with st.container(border=True):
                        st.subheader(job['title'])
                        st.markdown(f"**🏢 {job['company']}** • **📍 {job['location']}** • 🕒 {job['postedDate']}")
                        st.progress(job['matchScore'], text=f"**{job['matchScore']}% Match**")
                        st.write(job['description'])
                        st.caption(f"**Requirements:** {' • '.join(job['requirements'])}")
                        st.markdown(f"**Salary:** <span style='color: #2e7d32; font-weight: bold;'>{job['salary']}</span>", unsafe_allow_html=True)
                        st.button("Apply Now", key=job['id'], type="primary")

            else:
                st.error("The AI job search failed. Please try again.")
