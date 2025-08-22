import streamlit as st
import requests
import json
import io
import PyPDF2
import docx
from datetime import datetime, timedelta
import logging
import hashlib
import time
import re
from urllib.parse import urlparse

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
SERPAPI_URL = "https://serpapi.com/search"

# Securely fetch API keys from Streamlit Secrets
try:
    EURI_API_KEY = st.secrets["EURI_API_KEY"]
    SERPAPI_KEY = st.secrets["SERPAPI_KEY"]
except (KeyError, FileNotFoundError):
    st.error("⚠️ API Keys not found. Please add EURI_API_KEY and SERPAPI_KEY to your Streamlit secrets.")
    st.info("Add your API keys to `.streamlit/secrets.toml` file or Streamlit Cloud secrets.")
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
if 'chat_messages' not in st.session_state:
    st.session_state.chat_messages = []

# --- Enhanced Constants ---
TIME_FILTERS = {
    "Past hour": "h",
    "Past 24 hours": "d", 
    "Past week": "w",
    "Past month": "m",
    "Past year": "y",
    "Any time": ""
}

COUNTRIES = {
    "United States": {
        "code": "us",
        "job_sites": ["linkedin.com/jobs", "indeed.com", "glassdoor.com", "greenhouse.io", "lever.co", "workday.com"],
        "search_terms": ["jobs", "careers", "hiring", "employment", "opportunities"]
    },
    "United Kingdom": {
        "code": "uk", 
        "job_sites": ["linkedin.com/jobs", "indeed.co.uk", "totaljobs.com", "reed.co.uk", "cv-library.co.uk"],
        "search_terms": ["jobs", "careers", "vacancies", "positions", "opportunities"]
    },
    "Canada": {
        "code": "ca",
        "job_sites": ["linkedin.com/jobs", "indeed.ca", "workopolis.com", "monster.ca"],
        "search_terms": ["jobs", "careers", "employment", "opportunities", "hiring"]
    },
    "Germany": {
        "code": "de",
        "job_sites": ["linkedin.com/jobs", "xing.com", "stepstone.de", "indeed.de", "jobs.de"],
        "search_terms": ["jobs", "stellen", "karriere", "arbeit", "stellenangebote"]
    },
    "Australia": {
        "code": "au",
        "job_sites": ["linkedin.com/jobs", "seek.com.au", "indeed.com.au", "careerone.com.au"],
        "search_terms": ["jobs", "careers", "positions", "vacancies", "opportunities"]
    },
    "France": {
        "code": "fr",
        "job_sites": ["linkedin.com/jobs", "indeed.fr", "apec.fr", "monster.fr"],
        "search_terms": ["emploi", "travail", "carrières", "postes"]
    },
    "India": {
        "code": "in",
        "job_sites": ["linkedin.com/jobs", "naukri.com", "indeed.co.in", "monster.co.in"],
        "search_terms": ["jobs", "careers", "naukri", "employment"]
    },
    "Singapore": {
        "code": "sg",
        "job_sites": ["linkedin.com/jobs", "indeed.sg", "jobsbank.gov.sg"],
        "search_terms": ["jobs", "careers", "positions", "vacancies", "opportunities"]
    }
}

INDUSTRIES = {
    "Technology": {
        "domains": ["Software Engineering", "Data Science & Analytics", "DevOps & Cloud", "Cybersecurity", 
                   "AI/Machine Learning", "Mobile Development", "Web Development", "Product Management"],
        "keywords": ["tech", "software", "developer", "engineer", "programming", "coding", "data", "cloud"]
    },
    "Finance & Banking": {
        "domains": ["Investment Banking", "Financial Analysis", "Risk Management", "Accounting", 
                   "Corporate Finance", "Trading", "Insurance", "Fintech"],
        "keywords": ["finance", "banking", "investment", "financial", "accounting", "analyst", "fintech"]
    },
    "Healthcare": {
        "domains": ["Clinical Research", "Healthcare IT", "Medical Device", "Pharmaceutical", 
                   "Nursing", "Medical Administration", "Biotech"],
        "keywords": ["healthcare", "medical", "clinical", "pharmaceutical", "biotech", "health"]
    },
    "Marketing & Sales": {
        "domains": ["Digital Marketing", "Sales Development", "Brand Management", "Content Marketing",
                   "Social Media", "SEO/SEM", "Marketing Analytics", "Business Development"],
        "keywords": ["marketing", "sales", "business development", "brand", "digital", "growth"]
    },
    "Consulting": {
        "domains": ["Management Consulting", "IT Consulting", "Strategy Consulting", "Operations"],
        "keywords": ["consulting", "consultant", "strategy", "management", "advisory"]
    },
    "Education": {
        "domains": ["K-12 Teaching", "Higher Education", "Corporate Training", "Instructional Design"],
        "keywords": ["education", "teaching", "training", "curriculum", "academic", "instructor"]
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
    """Safely extracts a JSON object from a string with enhanced error handling."""
    try:
        # Remove markdown code blocks
        text = text.replace('```json', '').replace('```', '').strip()
        
        # Remove thinking tags that some AI models include
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        text = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL)
        
        # Remove any text before the first { and after the last }
        json_start = text.find('{')
        if json_start == -1:
            logger.error("No JSON object found in response")
            return None
            
        # Find the matching closing brace
        brace_count = 0
        json_end = json_start
        
        for i in range(json_start, len(text)):
            if text[i] == '{':
                brace_count += 1
            elif text[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    json_end = i + 1
                    break
        
        if brace_count != 0:
            logger.error("Unmatched braces in JSON")
            # Try to find the last complete JSON object
            last_brace = text.rfind('}')
            if last_brace > json_start:
                json_end = last_brace + 1
            else:
                return None
            
        json_str = text[json_start:json_end]
        
        # Clean up common JSON issues
        json_str = clean_json_string(json_str)
        
        # Validate JSON before returning
        parsed = json.loads(json_str)
        return parsed
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {e}")
        logger.error(f"Problematic JSON snippet: {text[max(0, json_start):json_start+200]}...")
        
        # Try to fix common JSON issues and retry
        try:
            fixed_json = fix_common_json_issues(text)
            if fixed_json:
                return json.loads(fixed_json)
        except Exception as fix_error:
            logger.error(f"JSON fix attempt failed: {fix_error}")
            
    except Exception as e:
        logger.error(f"Unexpected error in JSON extraction: {e}")
    
    return None

def clean_json_string(json_str):
    """Clean up common JSON formatting issues."""
    # Remove trailing commas before closing braces/brackets
    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
    
    # Fix unescaped quotes in strings (basic attempt)
    json_str = re.sub(r'(?<!\\)"(?=[^"]*"[^"]*:)', r'\\"', json_str)
    
    # Remove any null bytes
    json_str = json_str.replace('\x00', '')
    
    # Fix newlines in string values
    json_str = re.sub(r':\s*"([^"]*)\n([^"]*)"', r': "\1 \2"', json_str)
    
    # Remove any remaining thinking tags
    json_str = re.sub(r'</?think[^>]*>', '', json_str)
    
    return json_str.strip()

def fix_common_json_issues(text):
    """Attempt to fix common JSON formatting issues."""
    try:
        # Remove thinking tags first
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        text = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL)
        
        # Find JSON boundaries
        json_start = text.find('{')
        if json_start == -1:
            return None
            
        # Take everything from first { to last }
        json_end = text.rfind('}') + 1
        if json_end <= json_start:
            return None
            
        json_str = text[json_start:json_end]
        
        # Fix common issues
        json_str = clean_json_string(json_str)
        
        # Try to validate
        json.loads(json_str)
        return json_str
        
    except Exception as e:
        logger.error(f"JSON fix failed: {e}")
        return None

def call_euri_api(prompt, max_retries=3):
    """Call the EURI API with retry logic."""
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
            response = requests.post(EURI_API_URL, headers=headers, json=payload, timeout=90)
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"API Request Failed (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    return None

# --- SerpAPI Job Search Functions ---
def create_serpapi_queries(job_title, country, city="", industry=None, time_filter="d"):
    """Create optimized search queries for SerpAPI."""
    queries = []
    country_info = COUNTRIES.get(country, {})
    job_sites = country_info.get('job_sites', ['linkedin.com/jobs', 'indeed.com'])
    
    # Location context
    location_parts = []
    if city:
        location_parts.append(f'"{city}"')
    location_parts.append(f'"{country}"')
    location_context = " ".join(location_parts)
    
    # Primary site-specific queries
    for site in job_sites[:6]:  # Top 6 sites
        queries.extend([
            f'"{job_title}" site:{site} {location_context}',
            f'{job_title} site:{site} {location_context} apply',
            f'"{job_title}" site:{site} {location_context} hiring'
        ])
    
    # Industry-specific queries
    if industry and industry in INDUSTRIES:
        industry_keywords = INDUSTRIES[industry]['keywords'][:3]
        for keyword in industry_keywords:
            for site in job_sites[:3]:
                queries.append(f'"{job_title}" {keyword} site:{site} {location_context}')
    
    # General job search queries
    queries.extend([
        f'"{job_title}" {location_context} jobs apply',
        f'"{job_title}" {location_context} careers hiring',
        f'{job_title} {location_context} "job opening"',
        f'{job_title} {location_context} "we are hiring"'
    ])
    
    return list(set(queries))[:12]  # Remove duplicates, limit to 12

def search_jobs_with_serpapi(query, country, time_filter="d", num_results=20):
    """Search for jobs using SerpAPI."""
    try:
        country_info = COUNTRIES.get(country, {})
        country_code = country_info.get('code', 'us')
        
        params = {
            'api_key': SERPAPI_KEY,
            'engine': 'google',
            'q': query,
            'gl': country_code,  # Country for search results
            'hl': 'en',  # Language
            'num': num_results,
            'no_cache': 'true'
        }
        
        # Add time filter if specified
        if time_filter:
            params['tbs'] = f'qdr:{time_filter}'
        
        logger.info(f"SerpAPI search: {query} (country: {country_code}, time: {time_filter})")
        
        response = requests.get(SERPAPI_URL, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        if 'error' in data:
            logger.error(f"SerpAPI error: {data['error']}")
            return []
        
        organic_results = data.get('organic_results', [])
        logger.info(f"SerpAPI returned {len(organic_results)} results for query: {query}")
        
        jobs = []
        for result in organic_results:
            try:
                title = result.get('title', '')
                link = result.get('link', '')
                snippet = result.get('snippet', '')
                
                if not title or not link:
                    continue
                
                # Enhanced job filtering
                if is_job_related(title, link, snippet):
                    source = determine_job_source(link)
                    
                    jobs.append({
                        'title': title,
                        'link': link,
                        'snippet': snippet,
                        'source': source,
                        'scraped_at': datetime.now().strftime("%Y-%m-%d %H:%M"),
                        'query': query,
                        'country': country,
                        'serpapi_position': result.get('position', 0)
                    })
            except Exception as e:
                logger.warning(f"Error processing SerpAPI result: {e}")
                continue
        
        return jobs
        
    except requests.exceptions.RequestException as e:
        logger.error(f"SerpAPI request failed: {e}")
        return []
    except Exception as e:
        logger.error(f"SerpAPI search error: {e}")
        return []

def is_job_related(title, link, snippet):
    """Determine if a search result is job-related."""
    title_lower = title.lower()
    link_lower = link.lower()
    snippet_lower = snippet.lower()
    
    # Job site indicators
    job_sites = [
        'linkedin.com/jobs', 'indeed.', 'glassdoor.', 'monster.',
        'greenhouse.io', 'lever.co', 'workday.', 'bamboohr.',
        'smartrecruiters.', 'jobvite.', '/careers', '/jobs'
    ]
    
    # Job content indicators
    job_indicators = [
        'job', 'career', 'position', 'hiring', 'vacancy', 
        'employment', 'opportunity', 'apply', 'recruit', 'opening'
    ]
    
    # Check if it's from a job site
    is_job_site = any(site in link_lower for site in job_sites)
    
    # Check if it has job-related content
    has_job_content = any(indicator in title_lower for indicator in job_indicators)
    has_job_snippet = any(indicator in snippet_lower for indicator in job_indicators[:5])
    
    # Exclude obvious non-job content
    exclude_terms = ['wikipedia', 'linkedin.com/in/', 'facebook.com', 'twitter.com', 'youtube.com']
    is_excluded = any(term in link_lower for term in exclude_terms)
    
    return (is_job_site or has_job_content or has_job_snippet) and not is_excluded

def determine_job_source(link):
    """Determine the job source from URL."""
    link_lower = link.lower()
    
    source_mapping = {
        'linkedin.com/jobs': 'LinkedIn',
        'indeed.': 'Indeed',
        'glassdoor.': 'Glassdoor',
        'monster.': 'Monster',
        'greenhouse.io': 'Greenhouse',
        'lever.co': 'Lever',
        'workday.': 'Workday',
        'bamboohr.': 'BambooHR',
        'smartrecruiters.': 'SmartRecruiters',
        'jobvite.': 'Jobvite',
        'greenhouse.': 'Greenhouse',
        '/careers': 'Company Career Page',
        '/jobs': 'Company Jobs Page'
    }
    
    for indicator, source_name in source_mapping.items():
        if indicator in link_lower:
            return source_name
    
    # Extract domain as fallback
    try:
        domain = urlparse(link).netloc.replace('www.', '')
        return domain.title()
    except:
        return 'Unknown'

def run_serpapi_job_search(job_title, country, city="", industry=None, time_duration="Past 24 hours"):
    """Run comprehensive job search using SerpAPI."""
    time_filter = TIME_FILTERS.get(time_duration, "d")
    
    queries = create_serpapi_queries(job_title, country, city, industry, time_filter)
    
    st.info(f"🔍 Searching with {len(queries)} optimized queries via SerpAPI...")
    
    all_jobs = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, query in enumerate(queries):
        progress = (i + 1) / len(queries)
        progress_bar.progress(progress)
        status_text.text(f"Searching: {query[:70]}...")
        
        try:
            jobs = search_jobs_with_serpapi(query, country, time_filter)
            if jobs:
                all_jobs.extend(jobs)
                logger.info(f"Query {i+1}: Found {len(jobs)} jobs")
            
            # Brief pause to respect rate limits
            time.sleep(0.5)
            
        except Exception as e:
            logger.warning(f"Query {i+1} failed: {e}")
            continue
    
    progress_bar.empty()
    status_text.empty()
    
    # Deduplicate jobs
    unique_jobs = deduplicate_jobs(all_jobs)
    
    # Sort by relevance
    sorted_jobs = sort_jobs_by_relevance(unique_jobs, job_title, industry)
    
    return sorted_jobs

def deduplicate_jobs(jobs):
    """Remove duplicate job listings."""
    unique_jobs = {}
    
    for job in jobs:
        # Create hash based on title and company
        title_clean = re.sub(r'[^\w\s]', '', job['title'].lower()).strip()
        
        # Extract company name
        company_name = ""
        if " at " in job['title']:
            company_name = job['title'].split(" at ")[-1].strip().lower()
        elif " - " in job['title']:
            company_name = job['title'].split(" - ")[-1].strip().lower()
        
        hash_string = f"{title_clean[:50]}{company_name[:30]}{job['source'].lower()}"
        job_hash = hashlib.md5(hash_string.encode()).hexdigest()
        
        if job_hash not in unique_jobs:
            unique_jobs[job_hash] = job
        else:
            # Keep job with better source priority
            source_priority = {
                'Greenhouse': 9, 'Lever': 8, 'LinkedIn': 7, 'Company Career Page': 6,
                'Indeed': 5, 'Glassdoor': 4, 'Monster': 3, 'Workday': 8
            }
            
            existing_priority = source_priority.get(unique_jobs[job_hash]['source'], 1)
            new_priority = source_priority.get(job['source'], 1)
            
            if new_priority > existing_priority:
                unique_jobs[job_hash] = job
    
    return list(unique_jobs.values())

def sort_jobs_by_relevance(jobs, job_title, industry=None):
    """Sort jobs by relevance score."""
    def calculate_score(job):
        score = 0
        title_lower = job['title'].lower()
        job_title_lower = job_title.lower()
        snippet_lower = job['snippet'].lower()
        
        # Exact title match
        if job_title_lower in title_lower:
            score += 30
        
        # Word matching
        job_words = job_title_lower.split()
        for word in job_words:
            if len(word) > 2:
                if word in title_lower:
                    score += 10
                elif word in snippet_lower:
                    score += 5
        
        # Source quality
        source_scores = {
            'Greenhouse': 15, 'Lever': 12, 'LinkedIn': 10, 'Company Career Page': 8,
            'Indeed': 6, 'Glassdoor': 4, 'Workday': 12
        }
        score += source_scores.get(job['source'], 2)
        
        # SerpAPI position bonus (higher positions are better)
        position = job.get('serpapi_position', 10)
        score += max(0, 20 - position)
        
        return score
    
    return sorted(jobs, key=calculate_score, reverse=True)

# --- Resume Analysis Functions ---
def parse_resume_with_ai(resume_text, selected_industry=None):
    """Parse resume using AI with improved error handling and fallbacks."""
    industry_context = ""
    if selected_industry:
        domains = INDUSTRIES.get(selected_industry, {}).get('domains', [])
        industry_context = f"Industry Focus: {selected_industry}\nRelevant Domains: {', '.join(domains[:5])}"
    
    # Create a more explicit prompt that discourages thinking tags
    prompt = f"""
    Extract information from this resume and format it as a JSON object. Do not include any explanations, thinking process, or additional text - return ONLY the JSON object.
    
    {industry_context}
    
    JSON Format Required (copy this structure exactly):
    {{
        "name": "Full Name Here",
        "email": "email@domain.com",
        "phone": "phone number",
        "location": "city, state/country",
        "summary": "Brief professional summary",
        "skills": ["skill1", "skill2", "skill3"],
        "technical_skills": ["tech1", "tech2"],
        "experience": [
            {{
                "title": "Job Title",
                "company": "Company Name",
                "duration": "Start - End dates",
                "achievements": ["achievement1", "achievement2"]
            }}
        ],
        "education": [
            {{
                "degree": "Degree Name",
                "institution": "School Name",
                "year": "Graduation Year"
            }}
        ],
        "certifications": ["cert1", "cert2"],
        "industry_alignment": 75
    }}
    
    Resume Text:
    {resume_text[:2500]}
    
    IMPORTANT: Return ONLY the JSON object. No thinking, no explanations, no markdown - just pure JSON starting with {{ and ending with }}.
    """
    
    # Try with different model parameters to reduce thinking
    for attempt in range(3):
        try:
            # Modify the API call to discourage reasoning
            headers = {
                "Authorization": f"Bearer {EURI_API_KEY}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "deepseek-r1-distill-llama-70b",
                "messages": [
                    {
                        "role": "system", 
                        "content": "You are a JSON data extractor. Return only valid JSON objects with no additional text, explanations, or thinking process."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                "max_tokens": 800,  # Reduced to limit thinking
                "temperature": 0.1,  # Lower temperature for more consistent output
                "stop": ["<think>", "</think>", "```"]  # Stop sequences to prevent thinking
            }
            
            response = requests.post(EURI_API_URL, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            result = response.json()
            ai_response = result['choices'][0]['message']['content']
            
            # Log the raw response for debugging
            logger.info(f"AI Response attempt {attempt + 1} (first 100 chars): {ai_response[:100]}...")
            
            # Extract and validate JSON
            parsed = extract_json_from_response(ai_response)
            if parsed and validate_resume_data(parsed):
                logger.info("Successfully parsed resume with AI")
                return parsed
            else:
                logger.warning(f"Failed to parse JSON on attempt {attempt + 1}")
            
            # Modify prompt for retry
            if attempt < 2:
                prompt = prompt.replace("Return ONLY the JSON object", 
                                      "Output must be valid JSON format only. No text before or after the JSON.")
                
        except Exception as e:
            logger.error(f"Resume parsing attempt {attempt + 1} failed: {e}")
    
    # Fallback: Basic text extraction
    logger.warning("AI parsing failed completely, using fallback extraction")
    return extract_resume_fallback(resume_text, selected_industry)

def validate_resume_data(data):
    """Validate that parsed resume data has required fields."""
    required_fields = ['name', 'email', 'phone', 'location', 'summary', 'skills', 'experience', 'education']
    
    if not isinstance(data, dict):
        return False
    
    for field in required_fields:
        if field not in data:
            logger.warning(f"Missing required field: {field}")
            return False
    
    # Check that arrays are actually arrays
    array_fields = ['skills', 'experience', 'education']
    for field in array_fields:
        if not isinstance(data.get(field), list):
            logger.warning(f"Field {field} is not an array")
            return False
    
    return True

def extract_resume_fallback(resume_text, selected_industry=None):
    """Fallback resume extraction using basic text processing."""
    logger.info("Using fallback resume extraction")
    
    lines = resume_text.split('\n')
    
    # Basic extraction
    name = "Name not found"
    email = "Email not found"
    phone = "Phone not found"
    location = "Location not found"
    
    # Look for email
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    email_match = re.search(email_pattern, resume_text)
    if email_match:
        email = email_match.group()
    
    # Look for phone
    phone_pattern = r'(\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})'
    phone_match = re.search(phone_pattern, resume_text)
    if phone_match:
        phone = phone_match.group()
    
    # Extract name (usually first non-empty line)
    for line in lines[:5]:
        line = line.strip()
        if line and len(line) < 50 and not any(char.isdigit() for char in line):
            name = line
            break
    
    # Basic skills extraction
    skills_keywords = ['python', 'java', 'javascript', 'sql', 'excel', 'powerbi', 'tableau', 
                      'project management', 'data analysis', 'machine learning', 'aws', 'azure']
    found_skills = []
    resume_lower = resume_text.lower()
    
    for skill in skills_keywords:
        if skill in resume_lower:
            found_skills.append(skill.title())
    
    return {
        "name": name,
        "email": email,
        "phone": phone,
        "location": location,
        "summary": resume_text[:300] + "..." if len(resume_text) > 300 else resume_text,
        "skills": found_skills,
        "technical_skills": found_skills[:5],
        "experience": [{"title": "Experience parsing failed", "company": "Unknown", "duration": "Unknown", "achievements": []}],
        "education": [{"degree": "Education parsing failed", "institution": "Unknown", "year": "Unknown"}],
        "certifications": [],
        "industry_alignment": 50
    }

def generate_resume_insights(resume_data, selected_industry=None):
    """Generate resume insights using AI with improved error handling."""
    industry_context = ""
    if selected_industry:
        keywords = INDUSTRIES.get(selected_industry, {}).get('keywords', [])
        industry_context = f"Target Industry: {selected_industry}\nKey Keywords: {', '.join(keywords[:8])}"
    
    # Create a simpler prompt that avoids thinking responses
    prompt = f"""
    Analyze this resume and return insights as JSON. No explanations or thinking process - only JSON output.
    
    {industry_context}
    
    Resume Summary:
    - Name: {resume_data.get('name', 'N/A')}
    - Skills: {len(resume_data.get('skills', []))} skills listed
    - Experience: {len(resume_data.get('experience', []))} positions
    - Education: {len(resume_data.get('education', []))} entries
    
    Return this exact JSON structure:
    {{
        "ats_score": 75,
        "overall_score": 80,
        "strengths": ["strength1", "strength2", "strength3"],
        "improvements": ["improvement1", "improvement2"],
        "missing_keywords": ["keyword1", "keyword2"],
        "recommendations": ["rec1", "rec2", "rec3"]
    }}
    
    JSON output only - no additional text.
    """
    
    try:
        # Use the same approach as resume parsing with stop sequences
        headers = {
            "Authorization": f"Bearer {EURI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek-r1-distill-llama-70b",
            "messages": [
                {
                    "role": "system", 
                    "content": "You are a JSON generator for resume analysis. Output only valid JSON with no explanations."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            "max_tokens": 600,
            "temperature": 0.1,
            "stop": ["<think>", "</think>", "```", "\n\n"]
        }
        
        response = requests.post(EURI_API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        ai_response = result['choices'][0]['message']['content']
        
        logger.info(f"Insights AI Response (first 100 chars): {ai_response[:100]}...")
        
        parsed = extract_json_from_response(ai_response)
        
        if parsed and validate_insights_data(parsed):
            return parsed
        else:
            logger.warning("Failed to parse insights JSON, using fallback")
        
        # Fallback insights
        return generate_fallback_insights(resume_data, selected_industry)
        
    except Exception as e:
        logger.error(f"Resume insights generation failed: {e}")
        return generate_fallback_insights(resume_data, selected_industry)

def validate_insights_data(data):
    """Validate insights data structure."""
    required_fields = ['ats_score', 'overall_score', 'strengths', 'improvements', 'recommendations']
    
    if not isinstance(data, dict):
        return False
    
    for field in required_fields:
        if field not in data:
            logger.warning(f"Missing insights field: {field}")
            return False
    
    # Validate score ranges
    for score_field in ['ats_score', 'overall_score']:
        score = data.get(score_field, 0)
        if not isinstance(score, (int, float)) or not (0 <= score <= 100):
            logger.warning(f"Invalid score for {score_field}: {score}")
            return False
    
    return True

def generate_fallback_insights(resume_data, selected_industry=None):
    """Generate basic insights as fallback."""
    skills_count = len(resume_data.get('skills', []))
    experience_count = len(resume_data.get('experience', []))
    
    # Calculate basic scores
    ats_score = min(90, 50 + (skills_count * 3) + (experience_count * 10))
    overall_score = min(95, 60 + (skills_count * 2) + (experience_count * 8))
    
    strengths = []
    if skills_count > 5:
        strengths.append(f"Strong skill set with {skills_count} listed competencies")
    if experience_count > 2:
        strengths.append(f"Solid work history with {experience_count} positions")
    if resume_data.get('education'):
        strengths.append("Educational background provided")
    
    if not strengths:
        strengths = ["Resume structure is readable", "Contact information present"]
    
    improvements = []
    if skills_count < 5:
        improvements.append("Add more relevant skills to strengthen your profile")
    if experience_count < 2:
        improvements.append("Include more work experience or projects")
    if not resume_data.get('certifications'):
        improvements.append("Consider adding relevant certifications")
    
    recommendations = [
        "Quantify achievements with specific numbers and metrics",
        "Use action verbs to start bullet points",
        "Tailor resume keywords to job descriptions",
        "Keep resume to 1-2 pages maximum"
    ]
    
    missing_keywords = []
    if selected_industry and selected_industry in INDUSTRIES:
        industry_keywords = INDUSTRIES[selected_industry]['keywords']
        resume_text = str(resume_data).lower()
        missing_keywords = [kw for kw in industry_keywords[:5] if kw not in resume_text]
    
    return {
        "ats_score": ats_score,
        "overall_score": overall_score,
        "strengths": strengths[:5],
        "improvements": improvements[:4],
        "missing_keywords": missing_keywords,
        "recommendations": recommendations[:5]
    }

# --- Chat Function ---
def chat_about_career(user_message, resume_data=None):
    """Handle career chat."""
    context = ""
    if resume_data:
        context = f"""
        User's Resume Context:
        - Name: {resume_data.get('name', 'N/A')}
        - Skills: {', '.join(resume_data.get('skills', [])[:10])}
        - Experience: {len(resume_data.get('experience', []))} positions
        """
    
    prompt = f"""
    You are a career advisor. Answer this question helpfully and concisely.
    {context}
    
    Question: {user_message}
    
    Provide practical, actionable advice in under 200 words.
    """
    
    return call_euri_api(prompt)

# --- UI Functions ---
def main():
    st.title("🤖 AI Job Search Assistant (SerpAPI Powered)")
    st.markdown("*Reliable job search with SerpAPI integration for guaranteed results*")
    
    # Display API status
    col1, col2 = st.columns(2)
    with col1:
        st.success("✅ SerpAPI Connected")
    with col2:
        st.success("✅ EURI AI Connected")
    
    # Navigation
    st.sidebar.title("🧭 Navigation")
    page = st.sidebar.radio(
        "Choose a feature:",
        ["🌍 Job Search", "📄 Resume Analyzer", "💬 Career Chat"]
    )
    
    if page == "🌍 Job Search":
        render_job_search()
    elif page == "📄 Resume Analyzer":
        render_resume_analyzer()
    else:
        render_career_chat()

def render_job_search():
    st.header("🌍 Global Job Search (SerpAPI)")
    st.markdown("Search for jobs worldwide with guaranteed results using SerpAPI")
    
    # Show previous results stats
    if st.session_state.scraped_jobs:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Jobs Found", len(st.session_state.scraped_jobs))
        with col2:
            sources = set([job['source'] for job in st.session_state.scraped_jobs])
            st.metric("Sources", len(sources))
        with col3:
            recent_jobs = len([j for j in st.session_state.scraped_jobs 
                              if 'linkedin' in j.get('source', '').lower() or 'greenhouse' in j.get('source', '').lower()])
            st.metric("Premium Sources", recent_jobs)
    
    with st.form("serpapi_job_search"):
        col1, col2 = st.columns(2)
        
        with col1:
            job_title = st.text_input(
                "Job Title", 
                value="Software Engineer",
                help="Enter specific job title for best results"
            )
            
            country = st.selectbox(
                "Country",
                list(COUNTRIES.keys()),
                help="Select your target country"
            )
        
        with col2:
            city = st.text_input(
                "City (Optional)", 
                placeholder="e.g., San Francisco, London",
                help="Specify city for local results"
            )
            
            industry = st.selectbox(
                "Industry",
                ["Any Industry"] + list(INDUSTRIES.keys()),
                help="Select industry for targeted results"
            )
        
        col3, col4 = st.columns(2)
        with col3:
            time_duration = st.selectbox(
                "Time Range",
                list(TIME_FILTERS.keys()),
                index=1,  # Default to "Past 24 hours"
                help="Filter by posting date"
            )
        
        with col4:
            max_queries = st.slider(
                "Search Intensity",
                min_value=5,
                max_value=15,
                value=10,
                help="More queries = more comprehensive results"
            )
        
        submitted = st.form_submit_button("🚀 Search Jobs with SerpAPI", type="primary")
    
    if submitted:
        industry_param = industry if industry != "Any Industry" else None
        
        # Show search configuration
        st.info(f"🎯 Searching for '{job_title}' in {country} using SerpAPI...")
        
        with st.spinner("🔍 SerpAPI is searching for jobs..."):
            try:
                jobs = run_serpapi_job_search(job_title, country, city, industry_param, time_duration)
                
                st.session_state.scraped_jobs = jobs
                
                if jobs:
                    st.success(f"✅ Found {len(jobs)} job opportunities!")
                    
                    # Quick analytics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        linkedin_jobs = len([j for j in jobs if 'linkedin' in j.get('source', '').lower()])
                        st.metric("LinkedIn", linkedin_jobs)
                    with col2:
                        greenhouse_jobs = len([j for j in jobs if 'greenhouse' in j.get('source', '').lower()])
                        st.metric("Greenhouse", greenhouse_jobs)
                    with col3:
                        company_jobs = len([j for j in jobs if 'company' in j.get('source', '').lower()])
                        st.metric("Company Sites", company_jobs)
                    with col4:
                        other_jobs = len(jobs) - linkedin_jobs - greenhouse_jobs - company_jobs
                        st.metric("Other Sources", other_jobs)
                    
                    display_job_results(jobs)
                    
                else:
                    st.warning("⚠️ No jobs found. Try different search terms or expand the time range.")
                    
            except Exception as e:
                st.error(f"❌ Search failed: {str(e)}")
                logger.error(f"SerpAPI job search error: {e}")

def display_job_results(jobs):
    """Display job search results with filtering and export options."""
    if not jobs:
        return
    
    st.markdown("---")
    st.subheader("📋 Job Results")
    
    # Filtering options
    col1, col2, col3 = st.columns(3)
    
    with col1:
        sources = sorted(list(set([job['source'] for job in jobs])))
        source_filter = st.multiselect(
            "Filter by Source",
            options=sources,
            default=sources,
            key="source_filter"
        )
    
    with col2:
        search_filter = st.text_input(
            "Search in titles",
            placeholder="e.g., senior, remote, python",
            key="title_search"
        )
    
    with col3:
        sort_by = st.selectbox(
            "Sort by",
            ["Relevance", "Source", "Title A-Z"],
            key="sort_option"
        )
    
    # Apply filters
    filtered_jobs = jobs
    
    if source_filter:
        filtered_jobs = [job for job in filtered_jobs if job['source'] in source_filter]
    
    if search_filter:
        search_terms = search_filter.lower().split()
        filtered_jobs = [
            job for job in filtered_jobs 
            if any(term in job['title'].lower() or term in job.get('snippet', '').lower() 
                  for term in search_terms)
        ]
    
    # Apply sorting
    if sort_by == "Source":
        filtered_jobs.sort(key=lambda x: x['source'])
    elif sort_by == "Title A-Z":
        filtered_jobs.sort(key=lambda x: x['title'])
    
    if not filtered_jobs:
        st.warning("No jobs match your filters.")
        return
    
    st.write(f"**Showing {len(filtered_jobs)} of {len(jobs)} jobs**")
    
    # Display jobs
    for i, job in enumerate(filtered_jobs[:50]):  # Limit to 50 for performance
        with st.container():
            if i > 0:
                st.markdown("---")
            
            # Job header
            col1, col2, col3 = st.columns([4, 2, 1])
            
            with col1:
                st.markdown(f"### {job['title']}")
                
                # Highlight search matches
                if search_filter:
                    title_lower = job['title'].lower()
                    matches = [term for term in search_filter.lower().split() if term in title_lower]
                    if matches:
                        st.markdown(f"🎯 *Matches: {', '.join(matches)}*")
            
            with col2:
                # Source with styling
                source_icons = {
                    'LinkedIn': '💼', 'Indeed': '🔍', 'Glassdoor': '🏢',
                    'Greenhouse': '🌱', 'Lever': '⚡', 'Workday': '💻',
                    'Company Career Page': '🏛️', 'Company Jobs Page': '🏢'
                }
                icon = source_icons.get(job['source'], '🌐')
                st.markdown(f"{icon} **{job['source']}**")
                st.caption(f"Position: #{job.get('serpapi_position', 'N/A')}")
            
            with col3:
                st.link_button(
                    "📄 Apply Now", 
                    job['link'], 
                    use_container_width=True, 
                    type="primary"
                )
            
            # Job details
            if job.get('snippet'):
                with st.expander("📖 Job Description", expanded=False):
                    snippet = job['snippet']
                    if len(snippet) > 600:
                        snippet = snippet[:600] + "..."
                    st.markdown(snippet)
            
            # Metadata
            col1, col2, col3 = st.columns(3)
            with col1:
                st.caption(f"🕒 Found: {job.get('scraped_at', 'Unknown')}")
            with col2:
                st.caption(f"🌍 Country: {job.get('country', 'Unknown')}")
            with col3:
                st.caption(f"🔍 Via: SerpAPI")
    
    # Export and analytics
    if filtered_jobs:
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📊 Export to CSV"):
                csv_data = export_jobs_to_csv(filtered_jobs)
                st.download_button(
                    "💾 Download CSV",
                    csv_data,
                    file_name=f"serpapi_jobs_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv"
                )
        
        with col2:
            if st.button("📈 View Analytics"):
                show_job_analytics(filtered_jobs)
        
        with col3:
            if st.button("🔗 Copy All Links"):
                links = "\n".join([f"{job['title']} - {job['link']}" for job in filtered_jobs])
                st.text_area("Job Links (Copy All)", links, height=200)

def show_job_analytics(jobs):
    """Show analytics for job search results."""
    st.subheader("📈 Job Search Analytics")
    
    # Source distribution
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Sources Distribution**")
        source_counts = {}
        for job in jobs:
            source = job.get('source', 'Unknown')
            source_counts[source] = source_counts.get(source, 0) + 1
        
        for source, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(jobs)) * 100
            st.write(f"• {source}: {count} jobs ({percentage:.1f}%)")
    
    with col2:
        st.markdown("**Search Performance**")
        st.metric("Total Jobs Found", len(jobs))
        
        unique_companies = len(set([
            job['title'].split(' at ')[-1] if ' at ' in job['title'] 
            else job['title'].split(' - ')[-1] if ' - ' in job['title']
            else 'Unknown' for job in jobs
        ]))
        st.metric("Estimated Companies", unique_companies)
        
        avg_position = sum([job.get('serpapi_position', 10) for job in jobs]) / len(jobs)
        st.metric("Avg. Search Position", f"{avg_position:.1f}")

def export_jobs_to_csv(jobs):
    """Export jobs to CSV format."""
    import csv
    import io
    
    output = io.StringIO()
    fieldnames = ['title', 'source', 'link', 'snippet', 'country', 'scraped_at', 'serpapi_position']
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    
    for job in jobs:
        row = {}
        for field in fieldnames:
            value = job.get(field, '')
            if field == 'snippet' and value:
                value = value.replace('\n', ' ').replace('\r', ' ')
            row[field] = str(value)
        writer.writerow(row)
    
    return output.getvalue()

def render_resume_analyzer():
    """Resume analysis interface."""
    st.header("📄 AI Resume Analyzer")
    st.markdown("Upload your resume for AI-powered analysis and optimization tips")
    
    col1, col2 = st.columns(2)
    with col1:
        selected_industry = st.selectbox(
            "Target Industry",
            ["None"] + list(INDUSTRIES.keys()),
            help="Select industry for tailored analysis"
        )
    
    with col2:
        if selected_industry != "None":
            domains = INDUSTRIES[selected_industry]['domains']
            selected_domain = st.selectbox(
                "Domain",
                ["Any"] + domains,
                help="Specific domain within industry"
            )
    
    uploaded_file = st.file_uploader(
        "Upload Resume",
        type=['pdf', 'docx', 'txt'],
        help="Supported: PDF, DOCX, TXT"
    )
    
    if uploaded_file:
        st.info(f"📎 {uploaded_file.name} ({uploaded_file.size} bytes)")
        
        if st.button("🔍 Analyze Resume", type="primary"):
            with st.spinner("🤖 Analyzing resume..."):
                content = get_text_from_file(uploaded_file)
                
                if content and len(content.strip()) > 50:
                    industry_param = selected_industry if selected_industry != "None" else None
                    resume_data = parse_resume_with_ai(content, industry_param)
                    
                    if resume_data and resume_data.get('name') != 'Could not extract':
                        st.session_state.resume_data = resume_data
                        insights = generate_resume_insights(resume_data, industry_param)
                        st.session_state.resume_insights = insights
                        st.success("✅ Resume analyzed!")
                    else:
                        st.error("❌ Failed to parse resume")
                else:
                    st.error("❌ Could not extract text from file")
    
    # Display results
    if st.session_state.resume_data:
        display_resume_analysis()

def display_resume_analysis():
    """Display resume analysis results."""
    resume_data = st.session_state.resume_data
    insights = st.session_state.resume_insights
    
    st.subheader("📊 Resume Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Name", resume_data.get('name', 'N/A'))
    with col2:
        st.metric("Experience", f"{len(resume_data.get('experience', []))} roles")
    with col3:
        st.metric("Skills", f"{len(resume_data.get('skills', []))}")
    with col4:
        alignment = resume_data.get('industry_alignment', 0)
        st.metric("Industry Fit", f"{alignment}%")
    
    if insights:
        st.subheader("🎯 AI Insights")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("ATS Score", f"{insights.get('ats_score', 0)}%")
        with col2:
            st.metric("Overall Score", f"{insights.get('overall_score', 0)}%")
        
        tab1, tab2, tab3 = st.tabs(["💪 Strengths", "🔧 Improvements", "📈 Recommendations"])
        
        with tab1:
            strengths = insights.get('strengths', [])
            for strength in strengths:
                st.success(f"✅ {strength}")
        
        with tab2:
            improvements = insights.get('improvements', [])
            for improvement in improvements:
                st.warning(f"⚠️ {improvement}")
        
        with tab3:
            recommendations = insights.get('recommendations', [])
            for rec in recommendations:
                st.info(f"💡 {rec}")
            
            keywords = insights.get('missing_keywords', [])
            if keywords:
                st.markdown("**Missing Keywords:**")
                keyword_cols = st.columns(3)
                for i, keyword in enumerate(keywords[:9]):
                    with keyword_cols[i % 3]:
                        st.code(keyword)
    
    # Raw data
    with st.expander("📄 Extracted Data"):
        st.json(resume_data)

def render_career_chat():
    """Career chat interface."""
    st.header("💬 Career Chat Assistant")
    st.markdown("Get personalized career advice and job search guidance")
    
    if st.session_state.resume_data:
        st.success("✅ Resume loaded - personalized advice available!")
        name = st.session_state.resume_data.get('name', 'User')
        skills_count = len(st.session_state.resume_data.get('skills', []))
        st.info(f"👤 {name} | 🎯 {skills_count} skills identified")
    else:
        st.info("💡 Upload your resume for personalized career guidance!")
    
    # Chat interface
    st.subheader("💭 Ask Your Career Questions")
    
    # Display chat history
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask about your career, resume, job search..."):
        # Add user message
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("🤖 Thinking..."):
                response = chat_about_career(prompt, st.session_state.resume_data)
                if response:
                    st.markdown(response)
                    st.session_state.chat_messages.append({"role": "assistant", "content": response})
                else:
                    error_msg = "Sorry, I'm having trouble connecting. Please try again."
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
                st.session_state.chat_messages.append({"role": "user", "content": "What salary should I expect for my role?"})
                st.rerun()
        
        with col2:
            if st.button("Interview tips for my background?", key="q3"):
                st.session_state.chat_messages.append({"role": "user", "content": "What interview tips do you have for my background?"})
                st.rerun()
            
            if st.button("Skills I should learn?", key="q4"):
                st.session_state.chat_messages.append({"role": "user", "content": "What skills should I learn to advance my career?"})
                st.rerun()
    
    # Clear chat
    if st.session_state.chat_messages:
        if st.button("🗑️ Clear Chat"):
            st.session_state.chat_messages = []
            st.rerun()

# Sidebar information
def add_sidebar_info():
    """Add sidebar information and stats."""
    st.sidebar.markdown("---")
    st.sidebar.subheader("🚀 SerpAPI Benefits")
    st.sidebar.success("""
    ✅ **Guaranteed Results**
    ✅ **No Rate Limiting Issues**  
    ✅ **Real-time Data**
    ✅ **Global Coverage**
    ✅ **High Success Rate**
    """)
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("🌍 Supported Countries")
    for country, info in COUNTRIES.items():
        st.sidebar.write(f"🇺🇸 **{country}** ({info['code'].upper()})")
    
    if st.session_state.scraped_jobs:
        st.sidebar.markdown("---")
        st.sidebar.subheader("📊 Session Stats")
        
        jobs_count = len(st.session_state.scraped_jobs)
        st.sidebar.metric("Jobs Found", jobs_count)
        
        sources = set([job['source'] for job in st.session_state.scraped_jobs])
        st.sidebar.metric("Sources Used", len(sources))
        
        premium_sources = len([j for j in st.session_state.scraped_jobs 
                              if any(premium in j.get('source', '').lower() 
                                   for premium in ['linkedin', 'greenhouse', 'lever'])])
        st.sidebar.metric("Premium Sources", premium_sources)
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("ℹ️ About")
    st.sidebar.info("""
    **AI Job Search Assistant v4.0**
    
    **Powered by:**
    • SerpAPI for reliable search results
    • EURI AI for resume analysis
    • Global job market coverage
    
    **Features:**
    • Real job listings from 8+ countries
    • AI resume optimization
    • Career guidance chat
    • Export capabilities
    
    **Note:** Requires valid SerpAPI and EURI API keys
    """)

if __name__ == "__main__":
    # Custom CSS
    st.markdown("""
    <style>
    .stContainer > div {
        padding-top: 1rem;
    }
    
    .job-card {
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 1.5rem;
        margin: 1rem 0;
        background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 8px;
        text-align: center;
        margin: 0.5rem 0;
    }
    
    .source-badge {
        background: #e3f2fd;
        color: #1976d2;
        padding: 0.3rem 0.6rem;
        border-radius: 15px;
        font-size: 0.85rem;
        font-weight: 500;
    }
    
    .success-metric {
        background: linear-gradient(135deg, #4caf50 0%, #45a049 100%);
        color: white;
        padding: 0.8rem;
        border-radius: 8px;
        text-align: center;
    }
    
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    }
    
    .chat-message {
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 10px;
        border-left: 4px solid #667eea;
        background: #f8f9fa;
    }
    </style>
    """, unsafe_allow_html=True)
    
    add_sidebar_info()
    main()