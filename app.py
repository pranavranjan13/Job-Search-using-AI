import streamlit as st
import requests
import json
import io
import PyPDF2
import docx
import concurrent.futures
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
import logging
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Page Configuration ---
st.set_page_config(
    page_title="AI Job Search Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- API Configuration ---
EURI_API_URL = "https://api.euron.one/api/v1/euri/chat/completions"

# Securely fetch the API key from Streamlit Secrets
try:
    EURI_API_KEY = st.secrets["EURI_API_KEY"]
except (KeyError, FileNotFoundError):
    st.error("❌ EURI_API_KEY not found. Please add it to your Streamlit secrets.")
    st.info("Add your API key to `.streamlit/secrets.toml` file or Streamlit Cloud secrets.")
    st.stop()

# --- Session State Initialization ---
if 'resume_data' not in st.session_state:
    st.session_state.resume_data = None
if 'resume_insights' not in st.session_state:
    st.session_state.resume_insights = None
if 'scraped_jobs' not in st.session_state:
    st.session_state.scraped_jobs = []
if 'ai_jobs' not in st.session_state:
    st.session_state.ai_jobs = []

# --- Constants ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer': 'https://www.google.com/',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
}

TIME_FILTERS = {
    "Last 24 hours": "qdr:d",
    "Last week": "qdr:w",
    "Last 2 weeks": "qdr:w2",
    "Last month": "qdr:m"
}

ATS_SITES = [
    "greenhouse.io",
    "lever.co", 
    "ashbyhq.com",
    "pinpointhq.com",
    "workday.com",
    "bamboohr.com",
    "smartrecruiters.com",
    "jobvite.com",
    "careers.google.com",
    "jobs.netflix.com",
    "amazon.jobs",
    "careers.microsoft.com",
    "jobs.apple.com"
]

# --- Utility Functions ---
def get_text_from_file(uploaded_file):
    """Extracts text content from uploaded file (PDF, DOCX, TXT)."""
    text = ""
    try:
        file_stream = io.BytesIO(uploaded_file.getvalue())
        
        if uploaded_file.type == "application/pdf":
            pdf_reader = PyPDF2.PdfReader(file_stream)
            for page in pdf_reader.pages:
                extracted_text = page.extract_text()
                if extracted_text:
                    text += extracted_text + "\n"
                    
        elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            document = docx.Document(file_stream)
            for para in document.paragraphs:
                if para.text.strip():
                    text += para.text + "\n"
                    
        elif uploaded_file.type == "text/plain":
            text = str(uploaded_file.getvalue(), "utf-8")
            
        return text.strip()
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        st.error(f"Error reading file: {e}")
        return None

def extract_json_from_response(text):
    """Safely extracts a JSON object from a string that might contain other text."""
    try:
        # Remove markdown code blocks if present
        text = text.replace('```json', '').replace('```', '').strip()
        
        # Find the start and end of JSON object
        json_start = text.find('{')
        json_end = text.rfind('}') + 1
        
        if json_start != -1 and json_end > json_start:
            json_str = text[json_start:json_end]
            return json.loads(json_str)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"JSON parsing error: {e}")
    return None

def call_euri_api(prompt, max_retries=3):
    """Generic function to call the EURI API with retry logic."""
    headers = {
        "Authorization": f"Bearer {EURI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-r1-distill-llama-70b",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2000,
        "temperature": 0.7
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                EURI_API_URL, 
                headers=headers, 
                json=payload, 
                timeout=90
            )
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content']
            
        except requests.exceptions.Timeout:
            st.warning(f"API request timed out. Attempt {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
        except requests.exceptions.RequestException as e:
            logger.error(f"API Request Failed: {e}")
            st.error(f"API Request Failed: {e}")
            return None
        except (KeyError, IndexError) as e:
            logger.error(f"Invalid API Response format: {e}")
            st.error(f"Invalid API Response format: {e}")
            return None
    
    return None

# --- AI Functions ---
def parse_resume_with_ai(resume_text):
    """Sends resume text to EURI AI for parsing into a structured JSON."""
    prompt = f"""
    Analyze the following resume text and extract the information into a structured JSON format.
    
    Requirements:
    - Extract all personal information, skills, experience, education, and achievements
    - Identify ATS optimization opportunities 
    - Provide skill categorization (technical, soft skills, certifications)
    - Format experience with quantifiable achievements where possible
    
    Return a JSON object with these exact keys:
    - "name": string
    - "email": string  
    - "phone": string
    - "location": string
    - "summary": string (2-3 sentences)
    - "skills": array of strings
    - "technical_skills": array of strings  
    - "soft_skills": array of strings
    - "experience": array of objects with keys: "title", "company", "duration", "achievements" (array), "technologies" (array)
    - "education": array of objects with keys: "degree", "institution", "year", "gpa" (if available)
    - "certifications": array of strings
    - "projects": array of objects with keys: "name", "description", "technologies"
    
    Resume Text:
    ---
    {resume_text}
    ---
    
    IMPORTANT: Return ONLY a valid JSON object. No additional text or explanations.
    """
    
    response_text = call_euri_api(prompt)
    if response_text:
        parsed_data = extract_json_from_response(response_text)
        if parsed_data:
            return parsed_data
    
    # Fallback to basic parsing if AI fails
    return {
        "name": "Could not extract",
        "email": "Could not extract", 
        "phone": "Could not extract",
        "location": "Could not extract",
        "summary": resume_text[:200] + "..." if len(resume_text) > 200 else resume_text,
        "skills": [],
        "technical_skills": [],
        "soft_skills": [],
        "experience": [],
        "education": [],
        "certifications": [],
        "projects": []
    }

def generate_resume_insights(resume_data):
    """Generate comprehensive ATS-optimized insights for resume improvement."""
    prompt = f"""
    Based on this resume data, provide comprehensive ATS optimization insights:
    
    Resume Data: {json.dumps(resume_data, indent=2)}
    
    Analyze for:
    1. ATS compatibility issues
    2. Keyword optimization opportunities  
    3. Format and structure improvements
    4. Content enhancement suggestions
    5. Industry-specific recommendations
    
    Return JSON with these exact keys:
    - "ats_score": number (0-100)
    - "overall_score": number (0-100) 
    - "strengths": array of 3-5 detailed strings
    - "ats_issues": array of objects with keys: "issue", "solution", "priority" (High/Medium/Low)
    - "keyword_suggestions": array of strings (relevant industry keywords missing)
    - "format_improvements": array of strings
    - "content_improvements": array of objects with keys: "section", "suggestion", "example"
    - "industry_recommendations": array of strings
    - "action_items": array of prioritized improvement tasks
    
    IMPORTANT: Return ONLY a valid JSON object. No additional text.
    """
    
    response_text = call_euri_api(prompt)
    if response_text:
        return extract_json_from_response(response_text)
    return None

def search_jobs_with_ai(job_title, location, resume_data=None):
    """Search for jobs using EURI AI with resume matching if available."""
    resume_context = ""
    if resume_data:
        resume_context = f"""
        
        User's Resume Context:
        - Skills: {', '.join(resume_data.get('skills', []))}
        - Experience Level: {len(resume_data.get('experience', []))} positions
        - Technical Skills: {', '.join(resume_data.get('technical_skills', []))}
        """
    
    prompt = f"""
    Generate 10 realistic and diverse job listings for "{job_title}" positions in "{location}".
    {resume_context}
    
    Make the jobs realistic with:
    - Real company names (mix of startups, mid-size, and enterprises)
    - Accurate salary ranges for the location and role
    - Realistic job descriptions with current industry trends
    - Relevant requirements and qualifications
    - Mix of experience levels
    - Different company sizes and industries
    
    Return JSON with key "jobs" containing an array of job objects:
    - "id": unique string
    - "title": string  
    - "company": string (real company name)
    - "location": string
    - "type": string (Full-time/Part-time/Contract)
    - "remote_type": string (Remote/Hybrid/On-site)
    - "salary_min": number
    - "salary_max": number
    - "description": string (150-200 words with realistic details)
    - "requirements": array of 5-8 realistic requirements
    - "preferred_qualifications": array of 3-5 preferred skills
    - "benefits": array of 4-6 benefits
    - "posted_date": string (recent date)
    - "match_score": number (70-98, higher if resume provided and matches)
    - "match_reasons": array of strings (why it matches user's profile)
    - "company_size": string (Startup/Mid-size/Enterprise)
    - "industry": string
    
    IMPORTANT: Return ONLY a valid JSON object.
    """
    
    response_text = call_euri_api(prompt)
    if response_text:
        return extract_json_from_response(response_text)
    return None

# --- Web Scraping Functions ---
def scrape_google_for_ats(search_query, time_filter="qdr:d"):
    """Scrapes Google for job listings from ATS sites."""
    encoded_query = quote_plus(search_query)
    search_url = f"https://www.google.com/search?q={encoded_query}&tbs={time_filter}&num=20"
    
    jobs = []
    try:
        response = requests.get(search_url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Multiple selectors for different Google result formats
        selectors = ['div.g', 'div[data-ved]', '.rc']
        
        for selector in selectors:
            results = soup.select(selector)
            if results:
                break
        
        for result in results[:15]:  # Limit to prevent overwhelming
            title_elem = result.find('h3')
            link_elem = result.find('a')
            snippet_elem = result.find(['span', 'div'], class_=lambda x: x and ('st' in x or 'snippet' in x.lower()))
            
            if not snippet_elem:
                snippet_elem = result.find('div', class_=lambda x: x and 'VwiC3b' in x)
            
            if title_elem and link_elem and link_elem.get('href', '').startswith('http'):
                title = title_elem.get_text(strip=True)
                link = link_elem['href']
                snippet = snippet_elem.get_text(strip=True) if snippet_elem else "No description available."
                
                # Filter for job-related content
                job_indicators = ['job', 'career', 'position', 'hiring', 'vacancy', 'employment']
                if any(indicator in title.lower() for indicator in job_indicators) or \
                   any(indicator in link.lower() for indicator in job_indicators):
                    
                    # Determine source from URL
                    source = "Unknown"
                    for site in ATS_SITES:
                        if site.split('.')[0] in link:
                            source = site.split('.')[0].title()
                            break
                    
                    jobs.append({
                        "title": title,
                        "link": link,
                        "snippet": snippet[:300] + "..." if len(snippet) > 300 else snippet,
                        "source": source,
                        "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M")
                    })
        
        # Remove duplicates based on link
        unique_jobs = {job['link']: job for job in jobs}.values()
        return list(unique_jobs)
        
    except requests.exceptions.RequestException as e:
        logger.warning(f"Could not scrape for query '{search_query}'. Reason: {e}")
        return []

def scrape_remote_sites(job_title, time_filter_days=1):
    """Scrapes remote job sites directly."""
    jobs = []
    
    # Remote job sites to scrape
    remote_sites = [
        f"site:remote.co \"{job_title}\"",
        f"site:remoteok.io \"{job_title}\"",
        f"site:weworkremotely.com \"{job_title}\"",
        f"site:flexjobs.com \"{job_title}\" remote"
    ]
    
    time_filters = {1: "qdr:d", 7: "qdr:w", 14: "qdr:w2", 30: "qdr:m"}
    time_filter = time_filters.get(time_filter_days, "qdr:d")
    
    for site_query in remote_sites:
        site_jobs = scrape_google_for_ats(site_query, time_filter)
        jobs.extend(site_jobs)
    
    return jobs

def run_comprehensive_scraper(job_title, location_type, location_text="", time_duration="Last 24 hours"):
    """Comprehensive job scraping from multiple sources."""
    time_filter = TIME_FILTERS.get(time_duration, "qdr:d")
    
    # Build location query
    location_query = ""
    if location_type == "Remote":
        location_query = "remote work from home"
    elif location_type == "Hybrid" and location_text:
        location_query = f"hybrid \"{location_text}\""  
    elif location_type == "On-site" and location_text:
        location_query = f"\"{location_text}\" onsite"
    
    # Build search queries for different ATS sites
    search_queries = []
    
    # ATS-specific queries
    for site in ATS_SITES[:8]:  # Limit to prevent rate limiting
        query = f"\"{job_title}\" site:{site} {location_query} apply".strip()
        search_queries.append(query)
    
    # General job board queries
    general_queries = [
        f"\"{job_title}\" {location_query} jobs apply now",
        f"\"{job_title}\" {location_query} hiring careers",
        f"\"{job_title}\" {location_query} \"we're hiring\"",
    ]
    search_queries.extend(general_queries)
    
    # Add LinkedIn and Indeed specific searches
    if location_type == "Remote":
        search_queries.extend([
            f"site:linkedin.com/jobs \"{job_title}\" remote",
            f"site:indeed.com \"{job_title}\" remote"
        ])
    
    all_jobs = []
    
    # Use ThreadPoolExecutor for concurrent scraping
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        future_to_query = {}
        
        for query in search_queries[:12]:  # Limit concurrent requests
            future = executor.submit(scrape_google_for_ats, query, time_filter)
            future_to_query[future] = query
        
        # Add remote site scraping if applicable
        if location_type == "Remote":
            time_days = {"Last 24 hours": 1, "Last week": 7, "Last 2 weeks": 14, "Last month": 30}
            days = time_days.get(time_duration, 1)
            future = executor.submit(scrape_remote_sites, job_title, days)
            future_to_query[future] = "Remote Sites"
        
        # Collect results with timeout
        for future in concurrent.futures.as_completed(future_to_query, timeout=60):
            query = future_to_query[future]
            try:
                jobs = future.result(timeout=15)
                if jobs:
                    all_jobs.extend(jobs)
                    logger.info(f"Scraped {len(jobs)} jobs from: {query}")
            except Exception as exc:
                logger.warning(f'Query "{query}" generated exception: {exc}')
    
    # Remove duplicates and sort by relevance
    unique_jobs = {}
    for job in all_jobs:
        job_hash = hashlib.md5(
            (job['title'] + job['link']).encode()
        ).hexdigest()
        
        if job_hash not in unique_jobs:
            unique_jobs[job_hash] = job
    
    final_jobs = list(unique_jobs.values())
    
    # Sort by title relevance (basic scoring)
    def relevance_score(job):
        title_lower = job['title'].lower()
        job_title_lower = job_title.lower()
        score = 0
        
        # Exact match gets highest score
        if job_title_lower in title_lower:
            score += 10
        
        # Word matches
        job_words = job_title_lower.split()
        for word in job_words:
            if word in title_lower:
                score += 2
        
        return score
    
    final_jobs.sort(key=relevance_score, reverse=True)
    return final_jobs

# --- Streamlit UI ---
def main():
    st.title("🤖 AI-Powered Job Search Assistant")
    st.markdown("*Find your next opportunity with AI-enhanced resume analysis and live job scraping*")
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Choose a feature:",
        ["📄 Resume Analyzer", "🔍 Live Job Search", "💼 AI Job Matching"]
    )
    
    if page == "📄 Resume Analyzer":
        render_resume_analyzer()
    elif page == "🔍 Live Job Search":
        render_live_job_search()
    else:
        render_ai_job_matching()

def render_resume_analyzer():
    st.header("📄 Resume Analysis & ATS Optimization")
    st.markdown("Upload your resume for comprehensive AI analysis and ATS optimization tips.")
    
    uploaded_file = st.file_uploader(
        "Choose your resume file",
        type=['pdf', 'docx', 'txt'],
        help="Supported formats: PDF, DOCX, TXT"
    )
    
    if uploaded_file is not None:
        # Show file details
        st.info(f"📁 File: {uploaded_file.name} ({uploaded_file.size} bytes)")
        
        if st.button("🚀 Analyze Resume", type="primary"):
            with st.spinner("🤖 AI is analyzing your resume... This may take 30-60 seconds."):
                file_content = get_text_from_file(uploaded_file)
                
                if file_content and len(file_content.strip()) > 50:
                    # Parse resume
                    resume_data = parse_resume_with_ai(file_content)
                    
                    if resume_data and resume_data.get('name') != 'Could not extract':
                        st.session_state.resume_data = resume_data
                        
                        # Generate insights
                        insights = generate_resume_insights(resume_data)
                        if insights:
                            st.session_state.resume_insights = insights
                        
                        st.success("✅ Resume analyzed successfully!")
                    else:
                        st.error("❌ AI failed to parse the resume. Please ensure the document contains clear text.")
                else:
                    st.error("❌ Could not extract meaningful text from the file. Please check the document.")
    
    # Display results if available
    if st.session_state.resume_data:
        display_resume_analysis()

def display_resume_analysis():
    """Display resume analysis results."""
    resume_data = st.session_state.resume_data
    insights = st.session_state.resume_insights
    
    st.subheader("📊 Resume Overview")
    
    # Basic info in columns
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Name", resume_data.get('name', 'N/A'))
    with col2:
        st.metric("Experience", f"{len(resume_data.get('experience', []))} positions")
    with col3:
        st.metric("Skills", f"{len(resume_data.get('skills', []))} total")
    
    # Scores and insights
    if insights:
        st.subheader("🎯 ATS Optimization Scores")
        
        col1, col2 = st.columns(2)
        with col1:
            ats_score = insights.get('ats_score', 0)
            st.metric("ATS Compatibility", f"{ats_score}%", 
                     delta="Good" if ats_score > 70 else "Needs Work")
        with col2:
            overall_score = insights.get('overall_score', 0)
            st.metric("Overall Score", f"{overall_score}%",
                     delta="Excellent" if overall_score > 80 else "Room for Improvement")
        
        # Detailed insights in tabs
        tab1, tab2, tab3, tab4 = st.tabs(["🎯 ATS Issues", "💪 Strengths", "🔧 Improvements", "📝 Action Items"])
        
        with tab1:
            st.subheader("ATS Optimization Issues")
            ats_issues = insights.get('ats_issues', [])
            for issue in ats_issues:
                priority_color = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}
                st.markdown(f"{priority_color.get(issue.get('priority', 'Low'), '🔵')} **{issue.get('issue', '')}**")
                st.markdown(f"*Solution:* {issue.get('solution', '')}")
                st.markdown("---")
        
        with tab2:
            st.subheader("Resume Strengths")
            for strength in insights.get('strengths', []):
                st.markdown(f"✅ {strength}")
        
        with tab3:
            st.subheader("Content Improvements")
            improvements = insights.get('content_improvements', [])
            for improvement in improvements:
                st.markdown(f"**{improvement.get('section', '')}:**")
                st.markdown(f"📝 {improvement.get('suggestion', '')}")
                if improvement.get('example'):
                    st.code(improvement['example'])
                st.markdown("---")
        
        with tab4:
            st.subheader("Prioritized Action Items")
            action_items = insights.get('action_items', [])
            for i, item in enumerate(action_items, 1):
                st.markdown(f"{i}. {item}")
    
    # Resume details in expander
    with st.expander("📄 Extracted Resume Details"):
        st.json(resume_data)

def render_live_job_search():
    st.header("🔍 Live Job Search Engine")
    st.markdown("Scrape live job postings from major ATS platforms and job boards")
    
    with st.form("live_job_search"):
        col1, col2 = st.columns(2)
        
        with col1:
            job_title = st.text_input("Job Title", "Data Scientist", help="Enter the job title you're looking for")
            location_type = st.selectbox(
                "Work Type",
                ["Remote", "On-site", "Hybrid"],
                help="Select preferred work arrangement"
            )
        
        with col2:
            time_duration = st.selectbox(
                "Time Range",
                list(TIME_FILTERS.keys()),
                help="How far back to search for job postings"
            )
            location_text = st.text_input(
                "Location", 
                "San Francisco, CA",
                help="City, state, or region (required for On-site/Hybrid)"
            )
        
        submitted = st.form_submit_button("🚀 Search Live Jobs", type="primary")
    
    if submitted:
        if location_type in ["On-site", "Hybrid"] and not location_text.strip():
            st.error("❌ Please provide a location for On-site/Hybrid searches.")
        else:
            with st.spinner(f"🔍 Scraping live job listings from the {time_duration.lower()}..."):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Update progress
                progress_bar.progress(25)
                status_text.text("Searching ATS platforms...")
                
                found_jobs = run_comprehensive_scraper(
                    job_title, location_type, location_text, time_duration
                )
                
                progress_bar.progress(100)
                status_text.text("Search completed!")
                
                st.session_state.scraped_jobs = found_jobs
                
                if found_jobs:
                    st.success(f"✅ Found {len(found_jobs)} unique job listings!")
                    display_scraped_jobs(found_jobs)
                else:
                    st.warning(f"⚠️ No job listings found matching your criteria from the {time_duration.lower()}. Try:")
                    st.markdown("• Broadening your search terms")
                    st.markdown("• Extending the time range")
                    st.markdown("• Trying different job titles or locations")

def display_scraped_jobs(jobs):
    """Display scraped job results."""
    if not jobs:
        return
    
    st.markdown(f"### 📋 Found {len(jobs)} Job Listings")
    
    # Filters
    col1, col2 = st.columns(2)
    with col1:
        source_filter = st.multiselect(
            "Filter by Source",
            options=list(set([job['source'] for job in jobs])),
            default=list(set([job['source'] for job in jobs]))
        )
    with col2:
        search_filter = st.text_input("Search in titles", placeholder="e.g., senior, remote")
    
    # Apply filters
    filtered_jobs = jobs
    if source_filter:
        filtered_jobs = [job for job in filtered_jobs if job['source'] in source_filter]
    if search_filter:
        filtered_jobs = [job for job in filtered_jobs if search_filter.lower() in job['title'].lower()]
    
    st.markdown(f"*Showing {len(filtered_jobs)} of {len(jobs)} jobs*")
    
    # Display jobs
    for i, job in enumerate(filtered_jobs):
        with st.container():
            st.markdown("---")
            
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**{job['title']}**")
                st.markdown(f"🏢 Source: {job['source']} • ⏰ Scraped: {job.get('scraped_at', 'Unknown')}")
            with col2:
                st.link_button("📄 View & Apply", job['link'], use_container_width=True)
            
            # Snippet
            if job.get('snippet'):
                st.markdown(f"*{job['snippet']}*")

def render_ai_job_matching():
    st.header("💼 AI Job Matching")
    st.markdown("Get personalized job recommendations powered by AI")
    
    # Show resume status
    if st.session_state.resume_data:
        st.success("✅ Resume loaded - AI will provide personalized matches!")
        st.info(f"👤 {st.session_state.resume_data.get('name', 'User')} | 🎯 {len(st.session_state.resume_data.get('skills', []))} skills detected")
    else:
        st.info("💡 Upload your resume in the Resume Analyzer for personalized matches!")
    
    with st.form("ai_job_search"):
        col1, col2 = st.columns(2)
        
        with col1:
            job_title = st.text_input(
                "Job Title",
                value=st.session_state.resume_data.get('experience', [{}])[0].get('title', 'Software Engineer') if st.session_state.resume_data else 'Software Engineer',
                help="AI will find jobs matching this title"
            )
        
        with col2:
            location = st.text_input(
                "Preferred Location",
                "San Francisco, CA",
                help="City, state or 'Remote' for remote positions"
            )
        
        submitted = st.form_submit_button("🤖 Get AI Job Matches", type="primary")
    
    if submitted:
        with st.spinner("🤖 AI is finding the best job matches for you..."):
            jobs_data = search_jobs_with_ai(job_title, location, st.session_state.resume_data)
            
            if jobs_data and jobs_data.get("jobs"):
                st.session_state.ai_jobs = jobs_data["jobs"]
                st.success(f"✅ AI found {len(jobs_data['jobs'])} personalized job matches!")
                display_ai_jobs(jobs_data["jobs"])
            else:
                st.error("❌ AI job search failed. Please try again with different parameters.")

def display_ai_jobs(jobs):
    """Display AI-generated job matches."""
    if not jobs:
        return
    
    # Sort by match score
    jobs_sorted = sorted(jobs, key=lambda x: x.get('match_score', 0), reverse=True)
    
    st.markdown(f"### 🎯 AI Job Matches")
    
    # Filter options
    col1, col2, col3 = st.columns(3)
    with col1:
        min_salary = st.number_input("Min Salary ($)", min_value=0, max_value=500000, value=0, step=5000)
    with col2:
        company_size_filter = st.multiselect(
            "Company Size",
            ["Startup", "Mid-size", "Enterprise"],
            default=["Startup", "Mid-size", "Enterprise"]
        )
    with col3:
        remote_type_filter = st.multiselect(
            "Work Type",
            ["Remote", "Hybrid", "On-site"],
            default=["Remote", "Hybrid", "On-site"]
        )
    
    # Apply filters
    filtered_jobs = []
    for job in jobs_sorted:
        if (job.get('salary_min', 0) >= min_salary and 
            job.get('company_size', '') in company_size_filter and
            job.get('remote_type', '') in remote_type_filter):
            filtered_jobs.append(job)
    
    if not filtered_jobs:
        st.warning("No jobs match your current filters. Try adjusting the criteria.")
        return
    
    st.markdown(f"*Showing {len(filtered_jobs)} of {len(jobs)} jobs*")
    
    # Display jobs
    for job in filtered_jobs:
        with st.container():
            st.markdown("---")
            
            # Header with match score
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"### {job.get('title', 'N/A')}")
                st.markdown(f"🏢 **{job.get('company', 'N/A')}** • 📍 {job.get('location', 'N/A')} • 💼 {job.get('remote_type', 'N/A')}")
            with col2:
                match_score = job.get('match_score', 0)
                st.metric("Match Score", f"{match_score}%")
            
            # Salary and details
            col1, col2, col3 = st.columns(3)
            with col1:
                salary_range = f"${job.get('salary_min', 0):,} - ${job.get('salary_max', 0):,}"
                st.markdown(f"💰 **Salary:** {salary_range}")
            with col2:
                st.markdown(f"🏭 **Size:** {job.get('company_size', 'N/A')}")
            with col3:
                st.markdown(f"🏷️ **Industry:** {job.get('industry', 'N/A')}")
            
            # Description
            st.markdown("**Job Description:**")
            st.markdown(job.get('description', 'No description available.'))
            
            # Requirements and qualifications in columns
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Requirements:**")
                for req in job.get('requirements', []):
                    st.markdown(f"• {req}")
            
            with col2:
                st.markdown("**Preferred Qualifications:**")
                for qual in job.get('preferred_qualifications', []):
                    st.markdown(f"• {qual}")
            
            # Match reasons (if resume was provided)
            if job.get('match_reasons'):
                st.markdown("**🎯 Why this matches your profile:**")
                for reason in job.get('match_reasons', []):
                    st.markdown(f"✅ {reason}")
            
            # Benefits
            if job.get('benefits'):
                with st.expander("📋 Benefits & Perks"):
                    for benefit in job.get('benefits', []):
                        st.markdown(f"• {benefit}")
            
            # Action button
            st.button(f"🚀 Apply to {job.get('company', 'Company')}", 
                     key=f"apply_{job.get('id', '')}", 
                     type="primary")

# --- Additional Utility Functions ---
def export_jobs_to_csv(jobs, job_type="scraped"):
    """Export job listings to CSV format."""
    import csv
    import io
    
    output = io.StringIO()
    if not jobs:
        return None
    
    # Get all possible keys from jobs
    all_keys = set()
    for job in jobs:
        all_keys.update(job.keys())
    
    writer = csv.DictWriter(output, fieldnames=sorted(all_keys))
    writer.writeheader()
    
    for job in jobs:
        # Convert lists to strings for CSV
        clean_job = {}
        for k, v in job.items():
            if isinstance(v, list):
                clean_job[k] = '; '.join(map(str, v))
            else:
                clean_job[k] = str(v) if v is not None else ''
        writer.writerow(clean_job)
    
    return output.getvalue()

def add_sidebar_features():
    """Add additional features to sidebar."""
    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 Export Options")
    
    if st.session_state.scraped_jobs:
        csv_data = export_jobs_to_csv(st.session_state.scraped_jobs, "scraped")
        if csv_data:
            st.sidebar.download_button(
                "📥 Download Scraped Jobs (CSV)",
                csv_data,
                file_name=f"scraped_jobs_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv"
            )
    
    if st.session_state.ai_jobs:
        csv_data = export_jobs_to_csv(st.session_state.ai_jobs, "ai")
        if csv_data:
            st.sidebar.download_button(
                "📥 Download AI Jobs (CSV)",
                csv_data,
                file_name=f"ai_jobs_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv"
            )
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("ℹ️ About")
    st.sidebar.info(
        """
        **AI Job Search Assistant v2.0**
        
        Features:
        • 📄 ATS-optimized resume analysis
        • 🔍 Live job scraping from 10+ platforms
        • 🤖 AI-powered job matching
        • 📊 Export capabilities
        
        **Data Sources:**
        • Greenhouse, Lever, Ashby
        • LinkedIn, Indeed, Remote.co
        • Company career pages
        
        **Note:** Scraping is performed in real-time. 
        Heavy usage may result in temporary rate limits.
        """
    )
    
    # Usage statistics
    if st.session_state.scraped_jobs or st.session_state.ai_jobs:
        st.sidebar.markdown("---")
        st.sidebar.subheader("📈 Session Stats")
        st.sidebar.metric("Scraped Jobs", len(st.session_state.scraped_jobs))
        st.sidebar.metric("AI Matches", len(st.session_state.ai_jobs))
        if st.session_state.resume_data:
            st.sidebar.metric("Resume Loaded", "✅ Yes")

if __name__ == "__main__":
    # Add custom CSS
    st.markdown("""
    <style>
    .stContainer > div {
        padding-top: 1rem;
    }
    .metric-container {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .job-container {
        border: 1px solid #e0e0e0;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 0.5rem 0;
        background-color: #fafafa;
    }
    .match-score-high {
        background-color: #d4edda;
        color: #155724;
        padding: 0.25rem 0.5rem;
        border-radius: 0.25rem;
        font-weight: bold;
    }
    .match-score-medium {
        background-color: #fff3cd;
        color: #856404;
        padding: 0.25rem 0.5rem;
        border-radius: 0.25rem;
        font-weight: bold;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
    }
    .stTabs [data-baseweb="tab"] {
        padding-left: 20px;
        padding-right: 20px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Add sidebar features
    add_sidebar_features()
    
    # Run main app
    main()

