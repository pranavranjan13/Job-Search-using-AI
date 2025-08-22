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
import random

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
    st.error("⚠️ EURI_API_KEY not found. Please add it to your Streamlit secrets.")
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
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'chat_messages' not in st.session_state:
    st.session_state.chat_messages = []

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

# Countries and their common job search terms
COUNTRIES = {
    "United States": {
        "code": "US",
        "job_sites": ["linkedin.com/jobs", "indeed.com", "glassdoor.com", "monster.com"],
        "search_terms": ["jobs", "careers", "hiring", "employment"]
    },
    "United Kingdom": {
        "code": "UK",
        "job_sites": ["linkedin.com/jobs", "indeed.co.uk", "totaljobs.com", "reed.co.uk"],
        "search_terms": ["jobs", "careers", "vacancies", "positions"]
    },
    "Canada": {
        "code": "CA",
        "job_sites": ["linkedin.com/jobs", "indeed.ca", "workopolis.com", "monster.ca"],
        "search_terms": ["jobs", "careers", "employment", "opportunities"]
    },
    "Australia": {
        "code": "AU",
        "job_sites": ["linkedin.com/jobs", "seek.com.au", "indeed.com.au", "careerone.com.au"],
        "search_terms": ["jobs", "careers", "positions", "vacancies"]
    },
    "Germany": {
        "code": "DE",
        "job_sites": ["linkedin.com/jobs", "xing.com", "stepstone.de", "indeed.de"],
        "search_terms": ["jobs", "stellen", "karriere", "arbeit"]
    },
    "France": {
        "code": "FR",
        "job_sites": ["linkedin.com/jobs", "indeed.fr", "apec.fr", "monster.fr"],
        "search_terms": ["emploi", "travail", "carrières", "postes"]
    },
    "India": {
        "code": "IN",
        "job_sites": ["linkedin.com/jobs", "naukri.com", "indeed.co.in", "monster.co.in"],
        "search_terms": ["jobs", "careers", "naukri", "employment"]
    },
    "Singapore": {
        "code": "SG",
        "job_sites": ["linkedin.com/jobs", "indeed.sg", "jobsbank.gov.sg", "monster.com.sg"],
        "search_terms": ["jobs", "careers", "positions", "vacancies"]
    },
    "Netherlands": {
        "code": "NL",
        "job_sites": ["linkedin.com/jobs", "indeed.nl", "nationale-vacaturebank.nl", "monster.nl"],
        "search_terms": ["vacatures", "banen", "werk", "carrière"]
    },
    "Japan": {
        "code": "JP",
        "job_sites": ["linkedin.com/jobs", "indeed.com", "rikunabi.com", "mynavi.jp"],
        "search_terms": ["jobs", "求人", "転職", "採用"]
    }
}

# Enhanced industry and domain options
INDUSTRIES = {
    "Technology": {
        "domains": ["Software Engineering", "Data Science & Analytics", "DevOps & Cloud", "Cybersecurity", 
                   "AI/Machine Learning", "Mobile Development", "Web Development", "Product Management",
                   "UX/UI Design", "QA/Testing", "Technical Writing", "IT Support"],
        "keywords": ["tech", "software", "developer", "engineer", "programming", "coding"]
    },
    "Finance & Banking": {
        "domains": ["Investment Banking", "Financial Analysis", "Risk Management", "Accounting", 
                   "Corporate Finance", "Trading", "Insurance", "Fintech", "Compliance", "Audit"],
        "keywords": ["finance", "banking", "investment", "financial", "accounting", "analyst"]
    },
    "Healthcare & Medical": {
        "domains": ["Clinical Research", "Healthcare IT", "Medical Device", "Pharmaceutical", 
                   "Nursing", "Medical Administration", "Biotech", "Public Health", "Telemedicine"],
        "keywords": ["healthcare", "medical", "clinical", "pharmaceutical", "biotech", "health"]
    },
    "Marketing & Sales": {
        "domains": ["Digital Marketing", "Sales Development", "Brand Management", "Content Marketing",
                   "Social Media", "SEO/SEM", "Marketing Analytics", "Business Development", "PR"],
        "keywords": ["marketing", "sales", "business development", "brand", "digital marketing"]
    },
    "Education": {
        "domains": ["K-12 Teaching", "Higher Education", "Corporate Training", "Instructional Design",
                   "Educational Technology", "Curriculum Development", "Student Services"],
        "keywords": ["education", "teaching", "training", "curriculum", "academic", "instructor"]
    },
    "Consulting": {
        "domains": ["Management Consulting", "IT Consulting", "Strategy Consulting", "Operations",
                   "Change Management", "Business Analysis", "Process Improvement"],
        "keywords": ["consulting", "consultant", "strategy", "management", "advisory"]
    },
    "Manufacturing": {
        "domains": ["Production Management", "Quality Assurance", "Supply Chain", "Industrial Engineering",
                   "Maintenance", "Safety", "Lean Manufacturing", "Operations"],
        "keywords": ["manufacturing", "production", "industrial", "operations", "supply chain"]
    },
    "Media & Entertainment": {
        "domains": ["Content Creation", "Broadcasting", "Gaming", "Film/TV Production", "Music",
                   "Publishing", "Digital Media", "Entertainment Marketing"],
        "keywords": ["media", "entertainment", "content", "creative", "production", "broadcasting"]
    },
    "Retail & E-commerce": {
        "domains": ["E-commerce", "Merchandising", "Inventory Management", "Customer Service",
                   "Store Operations", "Supply Chain", "Online Marketing", "Retail Analytics"],
        "keywords": ["retail", "ecommerce", "merchandising", "customer service", "store"]
    },
    "Non-Profit & Government": {
        "domains": ["Program Management", "Policy Analysis", "Grant Writing", "Community Outreach",
                   "Public Administration", "Social Services", "Advocacy", "Research"],
        "keywords": ["nonprofit", "government", "public service", "policy", "social", "community"]
    }
}

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
        "max_tokens": 1000,
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
def parse_resume_with_ai(resume_text, selected_industry=None):
    """Sends resume text to EURI AI for parsing into a structured JSON."""
    industry_context = ""
    if selected_industry:
        domains = INDUSTRIES.get(selected_industry, {}).get('domains', [])
        industry_context = f"""
        
        Industry Focus: {selected_industry}
        Relevant Domains: {', '.join(domains)}
        
        When analyzing skills and experience, prioritize and highlight elements relevant to {selected_industry}.
        """
    
    prompt = f"""
    Analyze the following resume text and extract the information into a structured JSON format.
    {industry_context}
    
    Requirements:
    - Extract all personal information, skills, experience, education, and achievements
    - Identify ATS optimization opportunities 
    - Provide skill categorization (technical, soft skills, certifications)
    - Format experience with quantifiable achievements where possible
    - Assess industry alignment and suggest improvements
    
    Return a JSON object with these exact keys:
    - "name": string
    - "email": string  
    - "phone": string
    - "location": string
    - "summary": string (2-3 sentences)
    - "skills": array of strings
    - "technical_skills": array of strings  
    - "soft_skills": array of strings
    - "industry_skills": array of strings (industry-specific skills)
    - "experience": array of objects with keys: "title", "company", "duration", "achievements" (array), "technologies" (array)
    - "education": array of objects with keys: "degree", "institution", "year", "gpa" (if available)
    - "certifications": array of strings
    - "projects": array of objects with keys: "name", "description", "technologies"
    - "industry_alignment": number (0-100, how well aligned with selected industry)
    
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
        "industry_skills": [],
        "experience": [],
        "education": [],
        "certifications": [],
        "projects": [],
        "industry_alignment": 0
    }

def generate_resume_insights(resume_data, selected_industry=None):
    """Generate comprehensive ATS-optimized insights for resume improvement."""
    industry_context = ""
    if selected_industry:
        domains = INDUSTRIES.get(selected_industry, {}).get('domains', [])
        keywords = INDUSTRIES.get(selected_industry, {}).get('keywords', [])
        industry_context = f"""
        
        Target Industry: {selected_industry}
        Key Domains: {', '.join(domains)}
        Industry Keywords: {', '.join(keywords)}
        
        Provide industry-specific recommendations for {selected_industry} roles.
        """
    
    prompt = f"""
    Based on this resume data, provide comprehensive ATS optimization insights:
    {industry_context}
    
    Resume Data: {json.dumps(resume_data, indent=2)}
    
    Analyze for:
    1. ATS compatibility issues
    2. Keyword optimization opportunities  
    3. Format and structure improvements
    4. Content enhancement suggestions
    5. Industry-specific recommendations
    6. Skills gap analysis for target industry
    
    Return JSON with these exact keys:
    - "ats_score": number (0-100)
    - "overall_score": number (0-100) 
    - "industry_fit_score": number (0-100, alignment with target industry)
    - "strengths": array of 3-5 detailed strings
    - "ats_issues": array of objects with keys: "issue", "solution", "priority" (High/Medium/Low)
    - "keyword_suggestions": array of strings (relevant industry keywords missing)
    - "skills_to_add": array of strings (in-demand skills for target industry)
    - "format_improvements": array of strings
    - "content_improvements": array of objects with keys: "section", "suggestion", "example"
    - "industry_recommendations": array of strings
    - "action_items": array of prioritized improvement tasks
    - "competitive_analysis": string (how resume compares to industry standards)
    
    IMPORTANT: Return ONLY a valid JSON object. No additional text.
    """
    
    response_text = call_euri_api(prompt)
    if response_text:
        return extract_json_from_response(response_text)
    return None

def search_jobs_with_ai(job_title, country, city="", industry=None, domain=None, resume_data=None):
    """Search for jobs using EURI AI with country-specific context."""
    resume_context = ""
    if resume_data:
        resume_context = f"""
        
        User's Resume Context:
        - Skills: {', '.join(resume_data.get('skills', []))}
        - Experience Level: {len(resume_data.get('experience', []))} positions
        - Technical Skills: {', '.join(resume_data.get('technical_skills', []))}
        - Industry Skills: {', '.join(resume_data.get('industry_skills', []))}
        """
    
    industry_context = ""
    if industry and domain:
        industry_context = f"""
        
        Target Industry: {industry}
        Specific Domain: {domain}
        Industry Keywords: {', '.join(INDUSTRIES.get(industry, {}).get('keywords', []))}
        """
    
    country_info = COUNTRIES.get(country, {})
    location_str = f"{city}, {country}" if city else country
    
    prompt = f"""
    Generate 12 realistic and diverse job listings for "{job_title}" positions in "{location_str}".
    {resume_context}
    {industry_context}
    
    Country Context: {country}
    Country Code: {country_info.get('code', 'N/A')}
    
    Make the jobs realistic with:
    - Real company names from {industry if industry else 'various industries'} with presence in {country}
    - Accurate salary ranges for {country} market in local currency
    - Realistic job descriptions with current industry trends
    - Relevant requirements and qualifications for {domain if domain else 'the role'}
    - Mix of experience levels (entry, mid, senior)
    - Different company sizes and industries
    - Industry-specific technologies and skills
    - Country-specific benefits and work culture
    
    Return JSON with key "jobs" containing an array of job objects:
    - "id": unique string
    - "title": string  
    - "company": string (real company name with presence in {country})
    - "location": string ({location_str})
    - "country": string ({country})
    - "type": string (Full-time/Part-time/Contract)
    - "salary_min": number (in local currency)
    - "salary_max": number (in local currency)
    - "currency": string (local currency code)
    - "description": string (150-200 words with realistic details)
    - "requirements": array of 5-8 realistic requirements
    - "preferred_qualifications": array of 3-5 preferred skills
    - "benefits": array of 4-6 benefits (country-specific)
    - "posted_date": string (recent date)
    - "match_score": number (70-98, higher if resume provided and matches)
    - "match_reasons": array of strings (why it matches user's profile)
    - "company_size": string (Startup/Mid-size/Enterprise)
    - "industry": string
    - "domain": string (specific domain within industry)
    - "key_technologies": array of relevant technologies
    - "visa_sponsorship": boolean (true if company typically sponsors visas)
    
    IMPORTANT: Return ONLY a valid JSON object.
    """
    
    response_text = call_euri_api(prompt)
    if response_text:
        return extract_json_from_response(response_text)
    return None

# --- Enhanced Web Scraping Functions ---
def create_country_job_queries(job_title, country, city="", industry=None, time_filter="qdr:d"):
    """Create country-specific search queries for job scraping."""
    queries = []
    
    country_info = COUNTRIES.get(country, {})
    search_terms = country_info.get('search_terms', ['jobs'])
    job_sites = country_info.get('job_sites', ['linkedin.com/jobs'])
    
    # Location query
    location_query = f'"{country}"'
    if city:
        location_query = f'"{city}" "{country}"'
    
    # Industry keywords
    industry_keywords = []
    if industry and industry in INDUSTRIES:
        industry_keywords = INDUSTRIES[industry]['keywords'][:3]  # Limit to 3 keywords
    
    # Create queries for country-specific job sites
    for site in job_sites[:5]:  # Limit to top 5 sites
        # Basic job title query
        for term in search_terms[:2]:  # Limit to 2 search terms
            base_query = f'"{job_title}" site:{site} {location_query} {term} apply'
            queries.append(base_query.strip())
    
    # Add industry-specific queries
    if industry_keywords:
        for keyword in industry_keywords:
            for site in job_sites[:3]:
                industry_query = f'"{job_title}" {keyword} site:{site} {location_query} hiring'
                queries.append(industry_query.strip())
    
    # General queries without site restriction
    general_queries = [
        f'"{job_title}" {location_query} {search_terms[0]} "apply now"',
        f'"{job_title}" {location_query} careers hiring',
        f'"{job_title}" {location_query} "we\'re hiring"'
    ]
    queries.extend(general_queries)
    
    # Remove duplicates and limit
    unique_queries = list(set(queries))[:12]  # Limit to 12 queries
    return unique_queries

def enhanced_google_scraper(search_query, time_filter="qdr:d"):
    """Enhanced Google scraper with better result extraction."""
    try:
        encoded_query = quote_plus(search_query)
        search_url = f"https://www.google.com/search?q={encoded_query}&tbs={time_filter}&num=15"
        
        # Add random delay to avoid rate limiting
        time.sleep(random.uniform(1.5, 3.5))
        
        session = requests.Session()
        session.headers.update(HEADERS)
        
        response = session.get(search_url, timeout=20)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        jobs = []
        
        # Multiple selectors for different Google layouts
        result_selectors = [
            'div.g',  # Standard results
            'div[data-ved]',  # Alternative layout
            '.rc',  # Classic layout
            'div.MjjYud',  # New layout
        ]
        
        results = []
        for selector in result_selectors:
            results = soup.select(selector)
            if len(results) > 2:
                break
        
        for result in results[:10]:  # Process up to 10 results per query
            try:
                # Find title and link
                title_elem = result.find('h3')
                link_elem = result.find('a')
                
                if not title_elem or not link_elem:
                    continue
                    
                link = link_elem.get('href', '')
                if not link.startswith('http'):
                    continue
                
                title = title_elem.get_text(strip=True)
                
                # Find snippet/description
                snippet_elem = (
                    result.find('span', class_=lambda x: x and any(cls in str(x) for cls in ['aCOpRe', 'VwiC3b', 'IsZvec', 'st'])) or
                    result.find('div', class_=lambda x: x and any(cls in str(x) for cls in ['VwiC3b', 'IsZvec', 's3v9rd']))
                )
                
                snippet = snippet_elem.get_text(strip=True) if snippet_elem else "No description available."
                
                # Enhanced job filtering
                job_indicators = ['job', 'career', 'position', 'hiring', 'vacancy', 'employment', 'work', 'opportunity', 'apply', 'recruit']
                title_lower = title.lower()
                link_lower = link.lower()
                snippet_lower = snippet.lower()
                
                is_job_related = (
                    any(indicator in title_lower for indicator in job_indicators) or
                    any(indicator in link_lower for indicator in job_indicators) or
                    any(indicator in snippet_lower for indicator in job_indicators[:5])  # Check fewer indicators in snippet
                )
                
                # Quality filters
                if (is_job_related and 
                    len(title) > 10 and 
                    len(title) < 150 and  # Not too long
                    not any(spam in title_lower for spam in ['free', 'easy money', 'work from home scam'])):
                    
                    # Determine source
                    source = "Unknown"
                    domain_indicators = {
                        'linkedin': 'LinkedIn',
                        'indeed': 'Indeed',
                        'glassdoor': 'Glassdoor',
                        'monster': 'Monster',
                        'greenhouse': 'Greenhouse',
                        'lever': 'Lever',
                        'workday': 'Workday',
                        'bamboohr': 'BambooHR',
                        'careers': 'Company Career Page'
                    }
                    
                    for indicator, source_name in domain_indicators.items():
                        if indicator in link_lower:
                            source = source_name
                            break
                    
                    jobs.append({
                        "title": title,
                        "link": link,
                        "snippet": snippet[:400] + "..." if len(snippet) > 400 else snippet,
                        "source": source,
                        "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "query": search_query[:50] + "..." if len(search_query) > 50 else search_query
                    })
                    
            except Exception as e:
                logger.warning(f"Error processing result: {e}")
                continue
        
        return jobs
        
    except requests.exceptions.RequestException as e:
        logger.warning(f"Scraping failed for query '{search_query}': {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in scraping: {e}")
        return []

def run_enhanced_job_scraper(job_title, country, city="", industry=None, time_duration="Last 24 hours"):
    """Enhanced job scraping with country focus."""
    time_filter = TIME_FILTERS.get(time_duration, "qdr:d")
    
    search_queries = create_country_job_queries(job_title, country, city, industry, time_filter)
    
    all_jobs = []
    completed_queries = 0
    total_queries = len(search_queries)
    
    progress_placeholder = st.empty()
    
    # Use ThreadPoolExecutor with limited workers
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_to_query = {}
        
        for query in search_queries:
            future = executor.submit(enhanced_google_scraper, query, time_filter)
            future_to_query[future] = query
        
        for future in concurrent.futures.as_completed(future_to_query, timeout=150):
            query = future_to_query[future]
            completed_queries += 1
            
            progress = completed_queries / total_queries
            progress_placeholder.progress(
                progress, 
                text=f"Searching {country}... {completed_queries}/{total_queries} sources checked"
            )
            
            try:
                jobs = future.result(timeout=25)
                if jobs:
                    all_jobs.extend(jobs)
                    logger.info(f"Found {len(jobs)} jobs from: {query}")
                    
            except concurrent.futures.TimeoutError:
                logger.warning(f'Query "{query}" timed out')
            except Exception as exc:
                logger.warning(f'Query "{query}" generated exception: {exc}')
    
    progress_placeholder.empty()
    
    # Enhanced deduplication
    unique_jobs = {}
    for job in all_jobs:
        title_clean = job['title'].lower().strip()
        link_clean = job['link'].lower()
        
        # Create better hash for deduplication
        company_identifier = ""
        if " at " in title_clean:
            company_identifier = title_clean.split(" at ")[-1]
        elif "careers." in link_clean:
            company_identifier = link_clean.split("careers.")[1].split(".")[0]
        elif job['source'] != "Unknown":
            company_identifier = job['source'].lower()
        
        job_hash = hashlib.md5(
            (title_clean[:50] + company_identifier + job['source']).encode()
        ).hexdigest()
        
        if job_hash not in unique_jobs:
            unique_jobs[job_hash] = job
        else:
            # Keep job with better source
            existing_source = unique_jobs[job_hash]['source'].lower()
            new_source = job['source'].lower()
            
            preferred_sources = ['greenhouse', 'lever', 'linkedin', 'company career page', 'indeed']
            if any(source in new_source for source in preferred_sources):
                if not any(source in existing_source for source in preferred_sources):
                    unique_jobs[job_hash] = job
    
    final_jobs = list(unique_jobs.values())
    
    # Relevance scoring
    def calculate_relevance_score(job):
        score = 0
        title_lower = job['title'].lower()
        job_title_lower = job_title.lower()
        snippet_lower = job['snippet'].lower()
        
        # Exact title match
        if job_title_lower in title_lower:
            score += 25
        
        # Word matches
        job_words = job_title_lower.split()
        for word in job_words:
            if len(word) > 2:
                if word in title_lower:
                    score += 8
                elif word in snippet_lower:
                    score += 3
        
        # Country relevance
        if country.lower() in title_lower or country.lower() in snippet_lower:
            score += 5
        
        # Industry relevance
        if industry and industry in INDUSTRIES:
            industry_keywords = INDUSTRIES[industry]['keywords']
            for keyword in industry_keywords:
                if keyword in title_lower or keyword in snippet_lower:
                    score += 4
        
        # Source quality bonus
        source_lower = job['source'].lower()
        if 'linkedin' in source_lower:
            score += 8
        elif any(x in source_lower for x in ['greenhouse', 'lever', 'company career']):
            score += 6
        elif 'indeed' in source_lower:
            score += 4
        
        # Penalize very long titles (likely spam)
        if len(job['title']) > 120:
            score -= 8
        
        return max(0, score)
    
    # Sort by relevance score
    final_jobs.sort(key=calculate_relevance_score, reverse=True)
    
    return final_jobs

# --- Chat Functions ---
def chat_about_resume(user_message, resume_data=None):
    """Handle chat queries about the user's resume."""
    if not resume_data:
        return "I'd be happy to help you with your resume! Please upload your resume first in the Resume Analyzer section, and then I can answer specific questions about it."
    
    resume_context = f"""
    User's Resume Information:
    Name: {resume_data.get('name', 'N/A')}
    Email: {resume_data.get('email', 'N/A')}
    Location: {resume_data.get('location', 'N/A')}
    
    Summary: {resume_data.get('summary', 'N/A')}
    
    Skills: {', '.join(resume_data.get('skills', []))}
    Technical Skills: {', '.join(resume_data.get('technical_skills', []))}
    Industry Skills: {', '.join(resume_data.get('industry_skills', []))}
    
    Experience:
    {json.dumps(resume_data.get('experience', []), indent=2)}
    
    Education:
    {json.dumps(resume_data.get('education', []), indent=2)}
    
    Certifications: {', '.join(resume_data.get('certifications', []))}
    
    Projects:
    {json.dumps(resume_data.get('projects', []), indent=2)}
    
    Industry Alignment Score: {resume_data.get('industry_alignment', 0)}%
    """
    
    prompt = f"""
    You are an expert career counselor and resume advisor. The user has uploaded their resume and wants to ask questions about it.
    
    Here is their resume information:
    {resume_context}
    
    User's question: {user_message}
    
    Please provide helpful, specific, and actionable advice based on their actual resume data. Be encouraging but honest about areas for improvement. If they ask about job search strategies, salary negotiations, interview tips, or career advice, provide practical guidance tailored to their background.
    
    Keep your response conversational, helpful, and under 300 words unless they specifically ask for detailed information.
    """
    
    return call_euri_api(prompt)

# --- Streamlit UI ---
def main():
    st.title("🤖 AI-Powered Job Search Assistant")
    st.markdown("*Find your next opportunity with AI-enhanced resume analysis, global job search, and career chat*")
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Choose a feature:",
        ["📄 Resume Analyzer", "🔍 Global Job Search", "💼 AI Job Matching", "💬 Career Chat"]
    )
    
    if page == "📄 Resume Analyzer":
        render_resume_analyzer()
    elif page == "🔍 Global Job Search":
        render_global_job_search()
    elif page == "💼 AI Job Matching":
        render_ai_job_matching()
    else:
        render_career_chat()

def render_resume_analyzer():
    st.header("📄 Resume Analysis & ATS Optimization")
    st.markdown("Upload your resume for comprehensive AI analysis and ATS optimization tips.")
    
    # Industry selection
    col1, col2 = st.columns(2)
    with col1:
        selected_industry = st.selectbox(
            "Target Industry",
            ["None"] + list(INDUSTRIES.keys()),
            help="Select your target industry for tailored analysis"
        )
    
    with col2:
        selected_domain = None
        if selected_industry != "None":
            domains = INDUSTRIES[selected_industry]['domains']
            selected_domain = st.selectbox(
                "Specific Domain",
                ["Any"] + domains,
                help="Choose a specific domain within your industry"
            )
    
    uploaded_file = st.file_uploader(
        "Choose your resume file",
        type=['pdf', 'docx', 'txt'],
        help="Supported formats: PDF, DOCX, TXT"
    )
    
    if uploaded_file is not None:
        st.info(f"📎 File: {uploaded_file.name} ({uploaded_file.size} bytes)")
        
        if st.button("🚀 Analyze Resume", type="primary"):
            with st.spinner("🤖 AI is analyzing your resume... This may take 30-60 seconds."):
                file_content = get_text_from_file(uploaded_file)
                
                if file_content and len(file_content.strip()) > 50:
                    industry_for_analysis = selected_industry if selected_industry != "None" else None
                    resume_data = parse_resume_with_ai(file_content, industry_for_analysis)
                    
                    if resume_data and resume_data.get('name') != 'Could not extract':
                        st.session_state.resume_data = resume_data
                        
                        insights = generate_resume_insights(resume_data, industry_for_analysis)
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

def render_global_job_search():
    st.header("🌍 Global Job Search Engine")
    st.markdown("Search for jobs across different countries with localized results")
    
    with st.form("global_job_search"):
        col1, col2 = st.columns(2)
        
        with col1:
            job_title = st.text_input("Job Title", "Software Engineer", 
                                    help="Enter the specific job title you're looking for")
            
            selected_industry = st.selectbox(
                "Industry",
                ["Any Industry"] + list(INDUSTRIES.keys()),
                help="Select industry for targeted job search"
            )
        
        with col2:
            country = st.selectbox(
                "Country",
                list(COUNTRIES.keys()),
                help="Select the country where you want to work"
            )
            
            city = st.text_input(
                "City (Optional)", 
                placeholder="e.g., London, Toronto, Sydney",
                help="Specify a city for more targeted results"
            )
        
        col3, col4 = st.columns(2)
        with col3:
            time_duration = st.selectbox(
                "Time Range",
                list(TIME_FILTERS.keys()),
                help="How far back to search for job postings"
            )
        
        with col4:
            # Domain selection (conditional)
            selected_domain = None
            if selected_industry != "Any Industry":
                domains = INDUSTRIES[selected_industry]['domains']
                selected_domain = st.selectbox(
                    f"{selected_industry} Domain",
                    ["Any Domain"] + domains,
                    help=f"Choose a specific domain within {selected_industry}"
                )
        
        submitted = st.form_submit_button("🌍 Search Global Jobs", type="primary")
    
    if submitted:
        industry_param = selected_industry if selected_industry != "Any Industry" else None
        
        # Show search parameters
        search_params = []
        search_params.append(f"**Job Title:** {job_title}")
        search_params.append(f"**Country:** {country}")
        if city:
            search_params.append(f"**City:** {city}")
        if industry_param:
            search_params.append(f"**Industry:** {industry_param}")
        if selected_domain and selected_domain != "Any Domain":
            search_params.append(f"**Domain:** {selected_domain}")
        search_params.append(f"**Time Range:** {time_duration}")
        
        country_info = COUNTRIES.get(country, {})
        st.info(f"🔍 **Searching in {country}:**\n" + " • ".join(search_params))
        st.caption(f"📍 Using {country} job sites: {', '.join(country_info.get('job_sites', [])[:3])}")
        
        with st.spinner(f"🌍 Searching for jobs in {country}..."):
            found_jobs = run_enhanced_job_scraper(
                job_title, country, city, industry_param, time_duration
            )
            
            st.session_state.scraped_jobs = found_jobs
            
            if found_jobs:
                st.success(f"✅ Found {len(found_jobs)} job listings in {country}!")
                display_scraped_jobs(found_jobs, industry_param, country)
            else:
                st.warning(f"⚠️ No job listings found in {country} matching your criteria from the {time_duration.lower()}.")
                
                st.markdown("**💡 Try these suggestions:**")
                st.markdown("• Use broader job titles (e.g., 'Engineer' instead of 'Senior Backend Engineer')")
                st.markdown("• Extend the time range to 'Last week' or 'Last month'")
                st.markdown("• Try 'Any Industry' if you selected a specific industry")
                st.markdown("• Remove the city filter to search the entire country")
                st.markdown("• Try related job titles or synonyms")

def render_ai_job_matching():
    st.header("💼 AI Job Matching")
    st.markdown("Get personalized job recommendations powered by AI with global reach")
    
    # Show resume status
    if st.session_state.resume_data:
        st.success("✅ Resume loaded - AI will provide personalized matches!")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.info(f"👤 {st.session_state.resume_data.get('name', 'User')}")
        with col2:
            st.info(f"🎯 {len(st.session_state.resume_data.get('skills', []))} skills detected")
        with col3:
            industry_alignment = st.session_state.resume_data.get('industry_alignment', 0)
            st.info(f"📊 Industry fit: {industry_alignment}%")
    else:
        st.info("💡 Upload your resume in the Resume Analyzer for personalized matches!")
    
    with st.form("ai_job_search"):
        col1, col2 = st.columns(2)
        
        with col1:
            # Smart default based on resume
            default_title = "Software Engineer"
            if st.session_state.resume_data:
                experience = st.session_state.resume_data.get('experience', [])
                if experience and experience[0].get('title'):
                    default_title = experience[0]['title']
            
            job_title = st.text_input(
                "Job Title",
                value=default_title,
                help="AI will find jobs matching this title"
            )
            
            selected_industry = st.selectbox(
                "Target Industry",
                ["Any Industry"] + list(INDUSTRIES.keys()),
                help="Select industry for focused job matching"
            )
        
        with col2:
            country = st.selectbox(
                "Preferred Country",
                list(COUNTRIES.keys()),
                help="Choose your preferred country to work in"
            )
            
            city = st.text_input(
                "City (Optional)",
                placeholder="e.g., Berlin, Toronto, Singapore",
                help="Specify a city for more targeted results"
            )
        
        col3, col4 = st.columns(2)
        with col3:
            selected_domain = None
            if selected_industry != "Any Industry":
                domains = INDUSTRIES[selected_industry]['domains']
                selected_domain = st.selectbox(
                    f"{selected_industry} Domain",
                    ["Any Domain"] + domains,
                    help=f"Choose specific domain within {selected_industry}"
                )
        
        submitted = st.form_submit_button("🤖 Get AI Job Matches", type="primary")
    
    if submitted:
        industry_param = selected_industry if selected_industry != "Any Industry" else None
        domain_param = selected_domain if selected_domain and selected_domain != "Any Domain" else None
        
        with st.spinner(f"🤖 AI is finding the best job matches for you in {country}..."):
            jobs_data = search_jobs_with_ai(
                job_title, country, city, industry_param, domain_param, st.session_state.resume_data
            )
            
            if jobs_data and jobs_data.get("jobs"):
                st.session_state.ai_jobs = jobs_data["jobs"]
                st.success(f"✅ AI found {len(jobs_data['jobs'])} personalized job matches in {country}!")
                display_ai_jobs(jobs_data["jobs"], industry_param, country)
            else:
                st.error("❌ AI job search failed. Please try again with different parameters.")

def render_career_chat():
    st.header("💬 Career Chat Assistant")
    st.markdown("Ask questions about your resume, career advice, interview tips, and job search strategies")
    
    # Show resume status
    if st.session_state.resume_data:
        st.success("✅ Your resume is loaded - I can provide personalized advice!")
        with st.expander("📋 Your Resume Summary"):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Name", st.session_state.resume_data.get('name', 'N/A'))
            with col2:
                st.metric("Experience", f"{len(st.session_state.resume_data.get('experience', []))} positions")
            with col3:
                st.metric("Skills", f"{len(st.session_state.resume_data.get('skills', []))} total")
    else:
        st.info("💡 Upload your resume in the Resume Analyzer for personalized career advice!")
    
    # Chat interface
    st.subheader("🗣️ Chat with Career Assistant")
    
    # Display chat history
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask me anything about your resume or career..."):
        # Add user message to chat history
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate assistant response
        with st.chat_message("assistant"):
            with st.spinner("🤖 Thinking..."):
                response = chat_about_resume(prompt, st.session_state.resume_data)
                if response:
                    st.markdown(response)
                    st.session_state.chat_messages.append({"role": "assistant", "content": response})
                else:
                    error_msg = "I'm having trouble connecting to the AI service. Please try again."
                    st.markdown(error_msg)
                    st.session_state.chat_messages.append({"role": "assistant", "content": error_msg})
    
    # Suggested questions
    if not st.session_state.chat_messages:
        st.markdown("### 💭 Suggested Questions")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("How can I improve my resume?", key="q1"):
                st.session_state.chat_messages.append({"role": "user", "content": "How can I improve my resume?"})
                st.rerun()
            
            if st.button("What salary should I expect?", key="q2"):
                st.session_state.chat_messages.append({"role": "user", "content": "Based on my experience, what salary range should I expect?"})
                st.rerun()
            
            if st.button("Interview tips for my background?", key="q3"):
                st.session_state.chat_messages.append({"role": "user", "content": "What interview tips can you give me based on my background?"})
                st.rerun()
        
        with col2:
            if st.button("Skills I should learn?", key="q4"):
                st.session_state.chat_messages.append({"role": "user", "content": "What skills should I learn to advance my career?"})
                st.rerun()
            
            if st.button("Career change advice?", key="q5"):
                st.session_state.chat_messages.append({"role": "user", "content": "I'm considering a career change. What advice do you have?"})
                st.rerun()
            
            if st.button("Industry trends?", key="q6"):
                st.session_state.chat_messages.append({"role": "user", "content": "What are the current trends in my industry?"})
                st.rerun()
    
    # Clear chat button
    if st.session_state.chat_messages:
        if st.button("🗑️ Clear Chat", key="clear_chat"):
            st.session_state.chat_messages = []
            st.rerun()

def display_resume_analysis():
    """Display resume analysis results with industry insights."""
    resume_data = st.session_state.resume_data
    insights = st.session_state.resume_insights
    
    st.subheader("📊 Resume Overview")
    
    # Basic info in columns
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Name", resume_data.get('name', 'N/A'))
    with col2:
        st.metric("Experience", f"{len(resume_data.get('experience', []))} positions")
    with col3:
        st.metric("Skills", f"{len(resume_data.get('skills', []))} total")
    with col4:
        industry_alignment = resume_data.get('industry_alignment', 0)
        st.metric("Industry Fit", f"{industry_alignment}%", 
                 delta="Strong" if industry_alignment > 70 else "Needs Work")
    
    # Scores and insights
    if insights:
        st.subheader("🎯 Comprehensive Scoring")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            ats_score = insights.get('ats_score', 0)
            st.metric("ATS Compatibility", f"{ats_score}%", 
                     delta="Good" if ats_score > 70 else "Needs Work")
        with col2:
            overall_score = insights.get('overall_score', 0)
            st.metric("Overall Score", f"{overall_score}%",
                     delta="Excellent" if overall_score > 80 else "Room for Improvement")
        with col3:
            industry_fit = insights.get('industry_fit_score', 0)
            st.metric("Industry Alignment", f"{industry_fit}%",
                     delta="Great Fit" if industry_fit > 75 else "Could Improve")
        
        # Industry-specific skills
        if resume_data.get('industry_skills'):
            st.subheader("🎯 Industry-Relevant Skills")
            skills_cols = st.columns(3)
            industry_skills = resume_data.get('industry_skills', [])
            for i, skill in enumerate(industry_skills[:9]):
                with skills_cols[i % 3]:
                    st.success(f"✅ {skill}")
        
        # Detailed insights in tabs
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["🎯 ATS Issues", "💪 Strengths", "🔧 Improvements", "📈 Skills Gap", "📝 Action Items"])
        
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
            st.subheader("Skills Development Recommendations")
            
            st.markdown("**🔑 Missing Industry Keywords:**")
            keywords = insights.get('keyword_suggestions', [])
            if keywords:
                keyword_cols = st.columns(3)
                for i, keyword in enumerate(keywords):
                    with keyword_cols[i % 3]:
                        st.info(keyword)
            else:
                st.success("Great keyword coverage!")
            
            st.markdown("**🚀 In-Demand Skills to Consider:**")
            skills_to_add = insights.get('skills_to_add', [])
            if skills_to_add:
                for skill in skills_to_add:
                    st.markdown(f"📈 {skill}")
            else:
                st.success("Skills align well with industry demands!")
        
        with tab5:
            st.subheader("Prioritized Action Items")
            action_items = insights.get('action_items', [])
            for i, item in enumerate(action_items, 1):
                st.markdown(f"{i}. {item}")
            
            if insights.get('competitive_analysis'):
                st.subheader("📊 Market Position")
                st.info(insights['competitive_analysis'])
    
    with st.expander("📄 Extracted Resume Details"):
        st.json(resume_data)

def display_scraped_jobs(jobs, industry=None, country=None):
    """Display scraped job results with enhanced filtering."""
    if not jobs:
        return
    
    st.markdown(f"### 📋 Found {len(jobs)} Job Listings in {country}")
    
    # Enhanced filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        source_options = list(set([job['source'] for job in jobs]))
        source_filter = st.multiselect(
            "Filter by Source",
            options=source_options,
            default=source_options,
            help="Select job sources to include"
        )
    
    with col2:
        search_filter = st.text_input(
            "Search in titles", 
            placeholder="e.g., senior, remote, python",
            help="Search within job titles"
        )
    
    with col3:
        sort_option = st.selectbox(
            "Sort by",
            ["Relevance (Default)", "Source A-Z", "Title A-Z", "Recently Scraped"],
            help="Choose how to sort the results"
        )
    
    # Apply filters
    filtered_jobs = jobs
    
    if source_filter:
        filtered_jobs = [job for job in filtered_jobs if job['source'] in source_filter]
    
    if search_filter:
        search_terms = search_filter.lower().split()
        filtered_jobs = [
            job for job in filtered_jobs 
            if any(term in job['title'].lower() or term in job['snippet'].lower() 
                  for term in search_terms)
        ]
    
    # Apply sorting
    if sort_option == "Source A-Z":
        filtered_jobs.sort(key=lambda x: x['source'])
    elif sort_option == "Title A-Z":
        filtered_jobs.sort(key=lambda x: x['title'])
    elif sort_option == "Recently Scraped":
        filtered_jobs.sort(key=lambda x: x['scraped_at'], reverse=True)
    
    if not filtered_jobs:
        st.warning("No jobs match your current filters. Try adjusting the criteria.")
        return
    
    st.markdown(f"*Showing {len(filtered_jobs)} of {len(jobs)} jobs*")
    
    # Display jobs
    for i, job in enumerate(filtered_jobs):
        with st.container():
            if i > 0:
                st.markdown("---")
            
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.markdown(f"**{job['title']}**")
                
                if industry:
                    title_lower = job['title'].lower()
                    industry_keywords = INDUSTRIES.get(industry, {}).get('keywords', [])
                    relevant_keywords = [kw for kw in industry_keywords if kw in title_lower]
                    if relevant_keywords:
                        st.markdown(f"🎯 *Matches: {', '.join(relevant_keywords)}*")
            
            with col2:
                st.markdown(f"**Source:** {job['source']}")
            
            with col3:
                st.link_button("📄 View & Apply", job['link'], use_container_width=True)
            
            if job.get('snippet') and job['snippet'] != "No description available.":
                with st.expander("📖 Job Description Preview"):
                    st.markdown(job['snippet'])
            
            st.caption(f"⏰ Scraped: {job.get('scraped_at', 'Unknown')} | 🔍 From: {country}")

def display_ai_jobs(jobs, industry=None, country=None):
    """Display AI-generated job matches with enhanced features."""
    if not jobs:
        return
    
    jobs_sorted = sorted(jobs, key=lambda x: x.get('match_score', 0), reverse=True)
    
    st.markdown(f"### 🎯 AI Job Matches in {country}")
    
    # Enhanced filter options
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        min_salary = st.number_input("Min Salary", min_value=0, max_value=500000, value=0, step=5000)
    with col2:
        company_size_filter = st.multiselect(
            "Company Size",
            ["Startup", "Mid-size", "Enterprise"],
            default=["Startup", "Mid-size", "Enterprise"]
        )
    with col3:
        visa_sponsorship = st.checkbox("Visa Sponsorship Available", value=False)
    with col4:
        min_match_score = st.slider("Min Match Score", 0, 100, 70, help="Filter by minimum match percentage")
    
    # Apply filters
    filtered_jobs = []
    for job in jobs_sorted:
        if (job.get('salary_min', 0) >= min_salary and 
            job.get('company_size', '') in company_size_filter and
            job.get('match_score', 0) >= min_match_score and
            (not visa_sponsorship or job.get('visa_sponsorship', False))):
            filtered_jobs.append(job)
    
    if not filtered_jobs:
        st.warning("No jobs match your current filters. Try adjusting the criteria.")
        return
    
    st.markdown(f"*Showing {len(filtered_jobs)} of {len(jobs)} jobs*")
    
    # Display jobs
    for job in filtered_jobs:
        with st.container():
            st.markdown("---")
            
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"### {job.get('title', 'N/A')}")
                
                company_info = f"🏢 **{job.get('company', 'N/A')}**"
                if job.get('company_size'):
                    company_info += f" ({job.get('company_size')})"
                
                location_info = f"📍 {job.get('location', 'N/A')}"
                if job.get('visa_sponsorship'):
                    location_info += " 🌍 Visa Sponsorship"
                
                st.markdown(f"{company_info} • {location_info}")
                
                if job.get('industry') or job.get('domain'):
                    tags = []
                    if job.get('industry'):
                        tags.append(f"🏭 {job.get('industry')}")
                    if job.get('domain'):
                        tags.append(f"🎯 {job.get('domain')}")
                    st.markdown(" • ".join(tags))
            
            with col2:
                match_score = job.get('match_score', 0)
                score_color = "🟢" if match_score > 85 else "🟡" if match_score > 75 else "🔴"
                st.metric("Match Score", f"{match_score}%", delta=score_color)
            
            # Salary and posting info
            col1, col2, col3 = st.columns(3)
            with col1:
                currency = job.get('currency', 'USD')
                salary_range = f"{currency} {job.get('salary_min', 0):,} - {job.get('salary_max', 0):,}"
                st.markdown(f"💰 **Salary:** {salary_range}")
            with col2:
                st.markdown(f"📅 **Posted:** {job.get('posted_date', 'N/A')}")
            with col3:
                st.markdown(f"⚡ **Type:** {job.get('type', 'Full-time')}")
            
            # Key technologies
            if job.get('key_technologies'):
                st.markdown("**🔧 Key Technologies:**")
                tech_cols = st.columns(min(len(job['key_technologies']), 4))
                for i, tech in enumerate(job['key_technologies'][:4]):
                    with tech_cols[i]:
                        st.code(tech)
            
            st.markdown("**Job Description:**")
            st.markdown(job.get('description', 'No description available.'))
            
            # Requirements and qualifications
            col1, col2 = st.columns(2)
            with col1:
                with st.expander("📋 Requirements"):
                    for req in job.get('requirements', []):
                        st.markdown(f"• {req}")
            
            with col2:
                with st.expander("⭐ Preferred Qualifications"):
                    for qual in job.get('preferred_qualifications', []):
                        st.markdown(f"• {qual}")
            
            # Match reasons
            if job.get('match_reasons'):
                with st.expander("🎯 Why this matches your profile"):
                    for reason in job.get('match_reasons', []):
                        st.markdown(f"✅ {reason}")
            
            # Benefits
            if job.get('benefits'):
                with st.expander("🎁 Benefits & Perks"):
                    benefit_cols = st.columns(2)
                    for i, benefit in enumerate(job.get('benefits', [])):
                        with benefit_cols[i % 2]:
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
    st.sidebar.subheader("🌍 Countries Supported")
    
    with st.sidebar.expander("View All Countries"):
        for country, details in COUNTRIES.items():
            st.markdown(f"**{country}** ({details['code']})")
            st.caption(f"Job sites: {len(details['job_sites'])}")
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("🏭 Industries Supported")
    
    with st.sidebar.expander("View All Industries"):
        for industry, details in INDUSTRIES.items():
            st.markdown(f"**{industry}**")
            st.caption(f"{len(details['domains'])} domains available")
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("ℹ️ About")
    st.sidebar.info(
        """
        **AI Job Search Assistant v3.0**
        
        **New Features:**
        • 🌍 10 Country support
        • 💬 Career chat assistant
        • 🎯 Enhanced AI matching
        • 📊 Better resume analysis
        • 🔍 Improved job scraping
        
        **Supported Countries:**
        🇺🇸 US, 🇬🇧 UK, 🇨🇦 Canada, 🇦🇺 Australia, 
        🇩🇪 Germany, 🇫🇷 France, 🇮🇳 India, 
        🇸🇬 Singapore, 🇳🇱 Netherlands, 🇯🇵 Japan
        
        **Data Sources:**
        • Country-specific job sites
        • ATS platforms
        • Company career pages
        
        **Note:** Heavy usage may result in 
        temporary rate limits from search engines.
        """
    )
    
    # Usage statistics
    if st.session_state.scraped_jobs or st.session_state.ai_jobs or st.session_state.chat_messages:
        st.sidebar.markdown("---")
        st.sidebar.subheader("📈 Session Stats")
        st.sidebar.metric("Scraped Jobs", len(st.session_state.scraped_jobs))
        st.sidebar.metric("AI Matches", len(st.session_state.ai_jobs))
        st.sidebar.metric("Chat Messages", len(st.session_state.chat_messages))
        
        if st.session_state.resume_data:
            st.sidebar.success("✅ Resume Analyzed")
            industry_fit = st.session_state.resume_data.get('industry_alignment', 0)
            st.sidebar.metric("Industry Alignment", f"{industry_fit}%")

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
    .industry-tag {
        background-color: #e3f2fd;
        color: #1976d2;
        padding: 0.25rem 0.5rem;
        border-radius: 0.25rem;
        font-size: 0.8rem;
        margin: 0.1rem;
    }
    .chat-message {
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 0.5rem;
    }
    .user-message {
        background-color: #e3f2fd;
        margin-left: 2rem;
    }
    .assistant-message {
        background-color: #f5f5f5;
        margin-right: 2rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Add sidebar features
    add_sidebar_features()
    
    # Run main app
    main()