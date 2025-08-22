import streamlit as st
import requests
from bs4 import BeautifulSoup
import concurrent.futures
from urllib.parse import quote_plus

# --- Page Configuration ---
st.set_page_config(
    page_title="Live Job Search Engine",
    page_icon=" B",
    layout="wide"
)

# --- CORE SCRAPING FUNCTIONS (NEW IMPLEMENTATION) ---

# Headers to mimic a real browser visit
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
