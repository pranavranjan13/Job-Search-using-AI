import streamlit as st
import requests
import json
import io
import PyPDF2
import docx

# --- Page & API Configuration ---
tab1, tab2 = st.tabs(["AI Job Search Assistant", "Live Job Search Engine"])

with tab1:
    st.header("AI Job Search Assistant")
    st.write("Upload your resume and let our AI analyze it for job matching.")

with tab2:
    st.header("Live Job Search Engine")
    st.write("Enter your desired job title and location details to find live openings from the last 24 hours.")

    with st.form("job_search_form"):
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            job_title = st.text_input("Job Title", "Data Analyst")
        with col2:
            location_type = st.selectbox(
                "Location Type",
                ("Remote", "Onsite", "Hybrid"),
                help="Select the type of work location."
            )
        with col3:
            location_text = st.text_input("City or State", "New York", help="Required for Onsite/Hybrid searches.")

        submitted = st.form_submit_button("Search for Jobs")

    if submitted:
        if location_type in ["Onsite", "Hybrid"] and not location_text.strip():
            st.error("Please provide a city or state for Onsite/Hybrid searches.")
        else:
            with st.spinner("Scraping the web for live job listings... This may take a moment."):
                found_jobs = run_scrapers(job_title, location_type, location_text)

                if found_jobs:
                    st.success(f"Found {len(found_jobs)} unique job listings!")
                    for job in found_jobs:
                        with st.container(border=True):
                            st.subheader(job['title'])
                            st.caption(f"Source: {job['source']}")
                            st.write(job['snippet'])
                            st.link_button("View and Apply", job['link'])
                else:
                    st.warning("No job listings found matching your criteria from the last 24 hours. Try broadening your search.")

    st.sidebar.title("About")
    st.sidebar.info(
        "This application scrapes live job data from Google using advanced search queries. "
        "It is a proof-of-concept and demonstrates how to aggregate job listings from various Applicant Tracking Systems (ATS). "
        "**Note:** Scraping is performed in real-time. Frequent use may lead to temporary IP blocks from Google."
    )



# EURI API Configuration from the provided context
EURI_API_URL = "https://api.euron.one/api/v1/euri/chat/completions"
# Securely fetch the API key from Streamlit Secrets
try:
    EURI_API_KEY = st.secrets["EURI_API_KEY"]
except (KeyError, FileNotFoundError):
    st.error("EURI_API_KEY not found. Please add it to your Streamlit secrets.")
    st.stop()

# --- Session State Initialization ---
# This ensures data persists across page reloads and navigation
if 'resume_data' not in st.session_state:
    st.session_state.resume_data = None
if 'resume_insights' not in st.session_state:
    st.session_state.resume_insights = None
if 'jobs' not in st.session_state:
    st.session_state.jobs = []


# --- CORE FUNCTIONS (REAL IMPLEMENTATIONS) ---

def get_text_from_file(uploaded_file):
    """Extracts text content from uploaded file (PDF, DOCX, TXT)."""
    text = ""
    try:
        # Use file-like object directly from Streamlit uploader
        file_stream = io.BytesIO(uploaded_file.getvalue())
        if uploaded_file.type == "application/pdf":
            pdf_reader = PyPDF2.PdfReader(file_stream)
            for page in pdf_reader.pages:
                text += page.extract_text() or ""
        elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            document = docx.Document(file_stream)
            for para in document.paragraphs:
                text += para.text + "\n"
        elif uploaded_file.type == "text/plain":
            text = str(file_stream.read(), "utf-8")
        return text
    except Exception as e:
        st.error(f"Error reading file: {e}")
        return None

def extract_json_from_response(text):
    """Safely extracts a JSON object from a string that might contain other text."""
    try:
        # Find the start of the JSON object
        json_start_index = text.find('{')
        # Find the end of the JSON object
        json_end_index = text.rfind('}') + 1
        if json_start_index != -1 and json_end_index != -1:
            json_str = text[json_start_index:json_end_index]
            return json.loads(json_str)
    except (json.JSONDecodeError, IndexError):
        return None
    return None

def call_euri_api(prompt, api_key):
    """Generic function to call the EURI API."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-r1-distill-llama-70b",
        "messages": [{"role": "user", "content": prompt}]
    }
    try:
        response = requests.post(EURI_API_URL, headers=headers, json=payload, timeout=90)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        return response.json()['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        st.error(f"API Request Failed: {e}")
        return None
    except (KeyError, IndexError) as e:
        st.error(f"Invalid API Response format: {e}")
        return None

def parse_resume_with_ai(resume_text):
    """Sends resume text to EURI AI for parsing into a structured JSON."""
    prompt = f"""
    Analyze the following resume text and extract the information into a structured JSON format.
    The JSON object must include keys: "name", "email", "phone", "summary", "skills" (as a list),
    and "experience" (as a list of objects with "title", "company", "years").

    Resume Text:
    ---
    {resume_text}
    ---

    Return ONLY the JSON object.
    """
    response_text = call_euri_api(prompt, EURI_API_KEY)
    if response_text:
        return extract_json_from_response(response_text)
    return None
    
def generate_resume_insights(resume_data):
    """Generate insights and suggestions for resume improvement using EURI AI."""
    prompt = f"""
    Based on this resume data: {json.dumps(resume_data)}
    
    Provide improvement suggestions in JSON format. The JSON should have keys:
    "overallScore" (number from 0-100), "strengths" (list of 3 strings),
    and "improvements" (a list of objects with "area" and "suggestion").

    Return ONLY the JSON object.
    """
    response_text = call_euri_api(prompt, EURI_API_KEY)
    if response_text:
        return extract_json_from_response(response_text)
    return None

def search_jobs_with_ai(job_title, location):
    """Search for jobs using EURI AI and return structured JSON."""
    prompt = f"""
    Generate 8 realistic job listings for "{job_title}" positions in "{location}".
    Return the results as a single JSON object with a key "jobs", which is a list of job objects.
    Each job object must include: "id", "title", "company", "location", "type", "salary",
    "description" (100-150 words), "requirements" (list of 4-6 strings),
    "postedDate", "matchScore" (a number between 70-95), and "ats" (e.g., "Greenhouse", "Lever").

    Return ONLY the JSON object.
    """
    response_text = call_euri_api(prompt, EURI_API_KEY)
    if response_text:
        return extract_json_from_response(response_text)
    return None

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer': 'https://www.google.com/'
}

def scrape_google_for_ats(search_query):
    """
    Scrapes Google for a specific search query and returns structured job data.
    """
    # URL encode the query and add the 24-hour filter
    encoded_query = quote_plus(search_query)
    search_url = f"https://www.google.com/search?q={encoded_query}&tbs=qdr:d"
    
    jobs = []
    try:
        response = requests.get(search_url, headers=HEADERS, timeout=10)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # This selector targets the main search result containers. It's fragile and may need updates if Google changes its HTML structure.
        for result in soup.find_all('div', class_='g'):
            title_tag = result.find('h3')
            link_tag = result.find('a')
            snippet_tag = result.find('div', style='-webkit-line-clamp:2') # Google uses this style for snippets

            if title_tag and link_tag and link_tag['href'].startswith('http'):
                title = title_tag.get_text()
                link = link_tag['href']
                snippet = snippet_tag.get_text() if snippet_tag else "No snippet available."
                
                # Basic filtering to remove non-job links
                if "careers" in link or "jobs" in link or "job" in title.lower():
                    jobs.append({
                        "title": title,
                        "link": link,
                        "snippet": snippet,
                        "source": search_query.split('site:')[1].split(' ')[0] if 'site:' in search_query else 'Google'
                    })
    except requests.exceptions.RequestException as e:
        st.warning(f"Could not scrape for query '{search_query}'. Reason: {e}")
        
    return jobs

def scrape_remoterocketship(job_title):
    """
    Directly scrapes Remote Rocketship based on its URL structure.
    """
    encoded_title = quote_plus(job_title)
    url = f"https://www.remoterocketship.com/?jobTitle={encoded_title}&sort=DateAdded"
    jobs = []
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')

        # This selector targets job listing rows. This is specific to Remote Rocketship and will break if they change their site.
        for listing in soup.find_all('tr', class_='job-listing-row'):
            title_tag = listing.find('h3', class_='job-title')
            company_tag = listing.find('h2', class_='company-name')
            link_tag = listing.find('a', class_='job-title-link')

            if title_tag and link_tag and company_tag:
                jobs.append({
                    "title": f"{title_tag.get_text().strip()} at {company_tag.get_text().strip()}",
                    "link": f"https://www.remoterocketship.com{link_tag['href']}",
                    "snippet": "View on Remote Rocketship for more details.",
                    "source": "RemoteRocketship"
                })
    except requests.exceptions.RequestException as e:
        st.warning(f"Could not scrape Remote Rocketship. Reason: {e}")
    return jobs


def run_scrapers(job_title, location_type, location_text):
    """
    Constructs search queries and runs all scrapers in parallel.
    """
    
    # Build the location part of the query
    location_query = ""
    if location_type == "Remote":
        location_query = "remote"
    elif location_type == "Hybrid" and location_text:
        location_query = f"hybrid \"{location_text}\""
    elif location_type == "Onsite" and location_text:
        location_query = f"\"{location_text}\""

    # List of ATS sites to build Google search queries for
    ats_sites = [
        "greenhouse.io", "lever.co", "ashbyhq.com", 
        "pinpointhq.com", "jobs.*"
    ]
    
    search_queries = [f"\"{job_title}\" site:{site} {location_query}" for site in ats_sites]
    
    all_jobs = []
    
    # Use a ThreadPoolExecutor to run scraping tasks concurrently for speed
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # Prepare future tasks for Google scraping
        future_to_query = {executor.submit(scrape_google_for_ats, query): query for query in search_queries}
        # Add the direct scraper for Remote Rocketship if location is remote
        if location_type == "Remote":
            future_to_query[executor.submit(scrape_remoterocketship, job_title)] = "RemoteRocketship"
            
        for future in concurrent.futures.as_completed(future_to_query):
            try:
                jobs = future.result()
                all_jobs.extend(jobs)
            except Exception as exc:
                st.error(f'A scraper generated an exception: {exc}')
    
    # Remove duplicate jobs based on the link
    unique_jobs = list({job['link']: job for job in all_jobs}.values())
    return unique_jobs



# --- STREAMLIT UI ---

st.sidebar.title("🤖 AI Job Search Assistant")
page = st.sidebar.radio("Navigation", ["Resume Analyzer", "Job Search"])

if page == "Resume Analyzer":
    st.header("📄 Resume Analysis")
    st.write("Upload your resume (PDF, DOCX, or TXT) for AI-powered analysis.")

    uploaded_file = st.file_uploader(
        "Choose your resume file", 
        type=['pdf', 'docx', 'txt']
    )

    if uploaded_file is not None:
        with st.spinner("🤖 Analyzing your resume with AI... This may take a moment."):
            file_content = get_text_from_file(uploaded_file)
            if file_content:
                resume_data = parse_resume_with_ai(file_content)
                if resume_data:
                    st.session_state.resume_data = resume_data
                    st.session_state.resume_insights = generate_resume_insights(resume_data)
                    st.success("Resume Analyzed Successfully!")
                else:
                    st.error("AI failed to parse the resume. Please check the document content and try again.")
            else:
                st.error("Could not read text from the uploaded file. It might be empty or corrupted.")
    
    # Display resume data and insights if they exist in session state
    if st.session_state.resume_data:
        st.subheader("Extracted Resume Information")
        st.text_input("Name", st.session_state.resume_data.get("name"), disabled=True)
        st.text_area("AI Summary", st.session_state.resume_data.get("summary"), height=100, disabled=True)
        
    if st.session_state.resume_insights:
        st.subheader("AI-Powered Insights")
        insights = st.session_state.resume_insights
        st.progress(insights.get("overallScore", 0), text=f"Overall Score: {insights.get('overallScore', 'N/A')}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Strengths:**")
            for strength in insights.get("strengths", []):
                st.markdown(f"- {strength}")
        with col2:
            st.write("**Areas for Improvement:**")
            for item in insights.get("improvements", []):
                st.markdown(f"- **{item['area']}:** {item['suggestion']}")

elif page == "Job Search":
    st.header("🔍 AI-Powered Job Search")
    st.write("Enter your desired job title and location to find relevant openings.")
    
    with st.form("job_search_form"):
        col1, col2 = st.columns([2, 1])
        with col1:
            job_title = st.text_input("Job Title", "Senior Data Analyst" if not st.session_state.resume_data else st.session_state.resume_data.get('experience', [{}])[0].get('title', ''))
        with col2:
            location = st.text_input("Location", "New York, NY")
        
        submitted = st.form_submit_button("Search for Jobs")

    if submitted:
        with st.spinner("🤖 AI is searching for the best job matches..."):
            jobs_data = search_jobs_with_ai(job_title, location)
            if jobs_data and "jobs" in jobs_data:
                st.session_state.jobs = jobs_data["jobs"]
            else:
                st.session_state.jobs = []
                st.error("The AI job search failed or returned no results. Please try again.")

    if st.session_state.jobs:
        st.success(f"Found {len(st.session_state.jobs)} matching jobs!")
        for job in st.session_state.jobs:
            with st.container(border=True):
                st.subheader(job['title'])
                st.markdown(f"**🏢 {job['company']}** • **📍 {job['location']}** • 🕒 {job.get('postedDate', 'N/A')}")
                if 'matchScore' in job:
                    st.progress(job['matchScore'], text=f"**{job['matchScore']}% Match**")
                st.write(job['description'])
                st.caption(f"**Requirements:** {' • '.join(job.get('requirements', []))}")
                st.button("Apply Now", key=job['id'], type="primary")

st.header(" B Live Job Search Engine")
st.write("Enter your desired job title and location details to find live openings from the last 24 hours.")

with st.form("job_search_form"):
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        job_title = st.text_input("Job Title", "Data Analyst")
    with col2:
        location_type = st.selectbox(
            "Location Type",
            ("Remote", "Onsite", "Hybrid"),
            help="Select the type of work location."
        )
    with col3:
        location_text = st.text_input("City or State", "New York", help="Required for Onsite/Hybrid searches.")

    submitted = st.form_submit_button(" B Search for Jobs")

if submitted:
    if location_type in ["Onsite", "Hybrid"] and not location_text.strip():
        st.error("Please provide a city or state for Onsite/Hybrid searches.")
    else:
        with st.spinner(" B Scraping the web for live job listings... This may take a moment."):
            found_jobs = run_scrapers(job_title, location_type, location_text)
            
            if found_jobs:
                st.success(f" B Found {len(found_jobs)} unique job listings!")
                for job in found_jobs:
                    with st.container(border=True):
                        st.subheader(job['title'])
                        st.caption(f"Source: {job['source']}")
                        st.write(job['snippet'])
                        st.link_button("View and Apply", job['link'])
            else:
                st.warning("No job listings found matching your criteria from the last 24 hours. Try broadening your search.")

st.sidebar.title("About")
st.sidebar.info(
    "This application scrapes live job data from Google using advanced search queries. "
    "It is a proof-of-concept and demonstrates how to aggregate job listings from various Applicant Tracking Systems (ATS). "
    "**Note:** Scraping is performed in real-time. Frequent use may lead to temporary IP blocks from Google."
)