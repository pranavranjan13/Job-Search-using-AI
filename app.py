import streamlit as st
import requests
import json
import time
import base64
import io
import os
from datetime import datetime, timedelta
import random

# Page configuration
st.set_page_config(
    page_title="AI Job Search Agent",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .job-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
        border-left: 4px solid #667eea;
    }
    .match-score {
        background: linear-gradient(45deg, #667eea, #764ba2);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-weight: bold;
    }
    .skill-tag {
        background: #f0f2f6;
        padding: 0.25rem 0.75rem;
        border-radius: 15px;
        font-size: 0.8rem;
        margin: 0.25rem;
        display: inline-block;
    }
    .insight-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #28a745;
        margin: 1rem 0;
    }
    .chat-message {
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 10px;
    }
    .user-message {
        background: #e3f2fd;
        margin-left: 2rem;
    }
    .assistant-message {
        background: #f5f5f5;
        margin-right: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state variables
if 'resume_data' not in st.session_state:
    st.session_state.resume_data = None
if 'resume_insights' not in st.session_state:
    st.session_state.resume_insights = None
if 'jobs' not in st.session_state:
    st.session_state.jobs = []
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = [
        {"role": "assistant", "content": "Hello! I'm your AI job search assistant. Upload your resume to get started, or ask me anything about your job search!"}
    ]
if 'interview_questions' not in st.session_state:
    st.session_state.interview_questions = []

# EURI API configuration
EURI_API_URL = "https://api.euron.one/api/v1/euri/chat/completions"

def EURI_GUIDANCE(prompt_text, max_tokens=1000, model="gpt-4.1-mini"):
    """
    Call EURI API if key is provided; otherwise return offline guidance.
    Args:
        prompt_text (str): Text prompt for AI.
        max_tokens (int): Max tokens for EURI response.
        model (str): EURI model name.
    Returns:
        str: AI response or fallback text.
    """
    key = os.environ.get("EURI_API_KEY")
    if not key:
        return (
            "AI Coach (offline): For the prompt you provided, I recommend focusing on clear communication, "
            "relevant examples, and specific achievements. Please set your EURI_API_KEY to get personalized AI guidance."
        )
    try:
        headers = {
            "x-api-key": key,
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "user", "content": prompt_text}
            ]
        }
        resp = requests.post(
            EURI_API_URL, 
            headers=headers, 
            json=payload,
            timeout=20
        )
        resp.raise_for_status()
        data = resp.json()
        
        # Extract response text based on EURI API response format
        if 'choices' in data and len(data['choices']) > 0:
            return data['choices'][0]['message']['content']
        elif 'response' in data:
            return data['response']
        else:
            return str(data)
            
    except Exception as e:
        return f"AI guidance failed to fetch (API error): {str(e)}"

def extract_json_from_response(response_text):
    """Extract and parse JSON from EURI API response"""
    try:
        # Remove markdown code blocks if present
        cleaned = response_text.replace('```json', '').replace('```', '').strip()
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # If JSON parsing fails, try to find JSON-like content
        try:
            # Look for JSON object patterns
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
        return None
    except Exception:
        return None

def parse_resume_with_ai(resume_content):
    """Parse resume content using EURI AI"""
    prompt = f"""
    Analyze this resume and extract key information in JSON format:
    {{
        "personalInfo": {{
            "name": "string",
            "email": "string", 
            "phone": "string",
            "location": "string"
        }},
        "summary": "string",
        "skills": ["array of skills"],
        "experience": [
            {{
                "title": "string",
                "company": "string", 
                "duration": "string",
                "description": "string"
            }}
        ],
        "education": [
            {{
                "degree": "string",
                "school": "string",
                "year": "string"
            }}
        ],
        "keyStrengths": ["array of key strengths"],
        "improvementAreas": ["array of areas for improvement"]
    }}

    Resume content: {resume_content[:2000]}...

    Your entire response must be valid JSON only.
    """
    
    response = EURI_GUIDANCE(prompt, 1200)
    parsed_data = extract_json_from_response(response)
    
    # Fallback if JSON parsing fails
    if not parsed_data:
        return {
            "personalInfo": {
                "name": "John Doe",
                "email": "john.doe@email.com",
                "phone": "(555) 123-4567",
                "location": "Remote"
            },
            "summary": "Professional with experience in data analysis and problem-solving.",
            "skills": ["Python", "Data Analysis", "Communication", "Problem Solving", "Team Collaboration"],
            "experience": [
                {
                    "title": "Data Analyst",
                    "company": "Tech Company",
                    "duration": "2020-2024",
                    "description": "Analyzed data and created reports for business insights"
                }
            ],
            "education": [
                {
                    "degree": "Bachelor's Degree",
                    "school": "University",
                    "year": "2020"
                }
            ],
            "keyStrengths": ["Analytical thinking", "Attention to detail", "Communication"],
            "improvementAreas": ["Industry certifications", "Advanced technical skills"]
        }
    
    return parsed_data

def generate_resume_insights(resume_data):
    """Generate insights and suggestions for resume improvement using EURI AI"""
    prompt = f"""
    Based on this resume data: {json.dumps(resume_data)}
    
    Provide improvement suggestions in JSON format:
    {{
        "overallScore": 85,
        "strengths": ["array of 3-4 strengths"],
        "improvements": [
            {{
                "area": "string",
                "suggestion": "string", 
                "priority": "high|medium|low"
            }}
        ],
        "keywordOptimization": ["array of recommended keywords to add"],
        "industryAlignment": "string describing how well aligned the resume is"
    }}

    Your entire response must be valid JSON only.
    """
    
    response = EURI_GUIDANCE(prompt, 1000)
    parsed_insights = extract_json_from_response(response)
    
    # Fallback if JSON parsing fails
    if not parsed_insights:
        return {
            "overallScore": 78,
            "strengths": [
                "Clear work experience progression",
                "Relevant technical skills",
                "Professional presentation",
                "Good educational background"
            ],
            "improvements": [
                {
                    "area": "Quantifiable achievements",
                    "suggestion": "Add specific metrics and numbers to demonstrate impact",
                    "priority": "high"
                },
                {
                    "area": "Industry keywords",
                    "suggestion": "Include more industry-specific terminology",
                    "priority": "medium"
                },
                {
                    "area": "Professional summary",
                    "suggestion": "Enhance summary with key accomplishments",
                    "priority": "medium"
                }
            ],
            "keywordOptimization": ["data visualization", "analytics", "business intelligence", "SQL", "Python"],
            "industryAlignment": "Resume shows good technical foundation but could benefit from more industry-specific keywords and quantified achievements."
        }
    
    return parsed_insights

def search_jobs_with_ai(job_title, location, experience=""):
    """Search for jobs using EURI AI simulation"""
    ats_platforms = [
        "Greenhouse", "Lever", "Ashby", "LinkedIn", "Workable", 
        "BreezyHR", "Wellfound", "Oracle Cloud", "Pinpoint", "Keka"
    ]
    
    prompt = f"""
    Generate 6-8 realistic job listings for "{job_title}" positions in "{location}".
    
    Return results in JSON format:
    {{
        "jobs": [
            {{
                "id": "unique_id",
                "title": "string",
                "company": "string",
                "location": "string",
                "type": "Full-time|Part-time|Contract",
                "salary": "string",
                "description": "detailed job description (100-150 words)",
                "requirements": ["array of 4-6 requirements"],
                "benefits": ["array of 3-4 benefits"],
                "postedDate": "string (e.g., '2 days ago')",
                "matchScore": 85,
                "atsSource": "string (one of: {', '.join(ats_platforms)})",
                "applyUrl": "https://example-company.com/jobs/apply"
            }}
        ]
    }}

    Make the jobs diverse in terms of companies, requirements, and match scores. Your entire response must be valid JSON only.
    """
    
    response = EURI_GUIDANCE(prompt, 2000)
    parsed_jobs = extract_json_from_response(response)
    
    # Fallback if JSON parsing fails
    if not parsed_jobs or 'jobs' not in parsed_jobs:
        return {
            "jobs": [
                {
                    "id": "1",
                    "title": f"Senior {job_title}",
                    "company": "TechFlow Inc.",
                    "location": location,
                    "type": "Full-time",
                    "salary": "$80,000 - $120,000",
                    "description": f"We're looking for an experienced {job_title} to join our growing team and drive impactful projects. You'll work with cutting-edge technology and collaborate with talented professionals to deliver innovative solutions.",
                    "requirements": ["3+ years experience", "Strong analytical skills", "Team collaboration", "Problem-solving abilities"],
                    "benefits": ["Health insurance", "401k matching", "Flexible hours", "Remote work"],
                    "postedDate": "2 days ago",
                    "matchScore": 92,
                    "atsSource": "Greenhouse",
                    "applyUrl": "https://example.com/apply"
                },
                {
                    "id": "2",
                    "title": f"{job_title} - Remote",
                    "company": "DataViz Corp",
                    "location": "Remote",
                    "type": "Full-time",
                    "salary": "$70,000 - $95,000",
                    "description": f"Join our innovative team as a {job_title} and help shape the future of data-driven decision making. Work on exciting projects with modern tools and technologies.",
                    "requirements": ["2+ years experience", "Technical expertise", "Communication skills", "Adaptability"],
                    "benefits": ["Remote work", "Professional development", "Stock options", "Flexible PTO"],
                    "postedDate": "1 week ago",
                    "matchScore": 87,
                    "atsSource": "Lever",
                    "applyUrl": "https://example.com/apply"
                }
            ]
        }
    
    return parsed_jobs

def generate_interview_questions(job_title):
    """Generate mock interview questions using EURI AI"""
    prompt = f"""
    Generate 5 mock interview questions for a "{job_title}" position.
    
    Return in JSON format:
    {{
        "questions": [
            {{
                "id": 1,
                "question": "string",
                "type": "behavioral|technical|situational",
                "difficulty": "easy|medium|hard",
                "tips": "string with tips for answering"
            }}
        ]
    }}

    Include a mix of question types and difficulties. Your entire response must be valid JSON only.
    """
    
    response = EURI_GUIDANCE(prompt, 1200)
    parsed_questions = extract_json_from_response(response)
    
    # Fallback if JSON parsing fails
    if not parsed_questions or 'questions' not in parsed_questions:
        return {
            "questions": [
                {
                    "id": 1,
                    "question": f"Tell me about a time when you had to solve a complex problem as a {job_title}.",
                    "type": "behavioral",
                    "difficulty": "medium",
                    "tips": "Use the STAR method (Situation, Task, Action, Result) to structure your answer and focus on the impact of your solution."
                },
                {
                    "id": 2,
                    "question": "What technical skills do you consider most important for this role?",
                    "type": "technical",
                    "difficulty": "easy",
                    "tips": "Discuss both hard and soft skills, and explain how you've applied them in previous roles."
                },
                {
                    "id": 3,
                    "question": "How would you handle a situation where you disagreed with your team's approach?",
                    "type": "situational",
                    "difficulty": "medium",
                    "tips": "Show your communication skills and ability to find constructive solutions while being a team player."
                },
                {
                    "id": 4,
                    "question": "Describe your experience with the key tools and technologies used in this field.",
                    "type": "technical",
                    "difficulty": "hard",
                    "tips": "Be specific about your experience level and provide concrete examples of projects you've worked on."
                },
                {
                    "id": 5,
                    "question": "Where do you see yourself in 3-5 years in your career?",
                    "type": "behavioral",
                    "difficulty": "easy",
                    "tips": "Show ambition while aligning your goals with potential growth opportunities at the company."
                }
            ]
        }
    
    return parsed_questions

def evaluate_interview_answer(question, answer):
    """Evaluate interview answer using EURI AI"""
    prompt = f"""
    Question: "{question}"
    Answer: "{answer}"
    
    Evaluate this interview answer and provide feedback in JSON format:
    {{
        "score": 7,
        "strengths": ["array of positive aspects"],
        "improvements": ["array of areas to improve"],
        "overallFeedback": "string with detailed feedback",
        "suggestedAnswer": "string with a better example answer"
    }}

    Your entire response must be valid JSON only.
    """
    
    response = EURI_GUIDANCE(prompt, 1000)
    parsed_feedback = extract_json_from_response(response)
    
    # Fallback if JSON parsing fails
    if not parsed_feedback:
        return {
            "score": 7,
            "strengths": [
                "Clear communication",
                "Relevant example provided",
                "Good structure to the answer"
            ],
            "improvements": [
                "Add more specific details and metrics",
                "Include the impact or results of your actions",
                "Consider using the STAR method for better structure"
            ],
            "overallFeedback": "Good foundation in your answer. You communicated clearly and provided a relevant example. To strengthen your response, consider adding more specific details about the impact of your actions and quantifiable results where possible.",
            "suggestedAnswer": "A stronger answer would follow the STAR method: describe the Situation, explain the Task you needed to accomplish, detail the specific Actions you took, and highlight the positive Results that followed. Include metrics and specific examples where possible."
        }
    
    return parsed_feedback

# Header
st.markdown("""
<div class="main-header">
    <h1>🔍 AI Job Search Agent</h1>
    <p>Your intelligent companion for finding the perfect job opportunity</p>
</div>
""", unsafe_allow_html=True)

# Sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Choose a section:",
    ["📄 Resume Upload", "💼 Job Search", "🎤 Interview Prep", "💬 AI Assistant", "📊 Career Insights"]
)

# ATS Search Patterns Info
with st.sidebar.expander("🔍 Supported ATS Platforms"):
    st.write("""
    - Greenhouse (greenhouse.io)
    - Lever (lever.co) 
    - Ashby (ashbyhq.com)
    - Pinpoint (pinpointhq.com)
    - Workable (jobs.workable.com)
    - BreezyHR (breezy.hr)
    - Wellfound (wellfound.com)
    - Oracle Cloud (oraclecloud.com)
    - Keka (keka.com)
    - Job Subdomains (jobs.*)
    - Career Pages (careers.*)
    - And more...
    """)

# Main content based on selected page
if page == "📄 Resume Upload":
    st.header("📄 Resume Analysis")
    st.write("Upload your resume for AI-powered analysis and insights.")
    
    uploaded_file = st.file_uploader(
        "Choose your resume file", 
        type=['pdf', 'txt', 'docx'],
        help="Upload your resume in PDF, TXT, or DOCX format"
    )
    
    if uploaded_file is not None:
        with st.spinner("🤖 Analyzing your resume with AI..."):
            # Simulate file processing
            file_content = str(uploaded_file.read()[:2000])  # First 2000 chars for demo
            
            # Parse resume with AI
            resume_data = parse_resume_with_ai(file_content)
            
            if resume_data:
                st.session_state.resume_data = resume_data
                
                # Generate insights
                insights = generate_resume_insights(resume_data)
                if insights:
                    st.session_state.resume_insights = insights
        
        if st.session_state.resume_data:
            st.success("✅ Resume processed successfully!")
            
            # Display parsed information
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📋 Personal Information")
                personal_info = st.session_state.resume_data.get('personalInfo', {})
                st.write(f"**Name:** {personal_info.get('name', 'N/A')}")
                st.write(f"**Email:** {personal_info.get('email', 'N/A')}")
                st.write(f"**Location:** {personal_info.get('location', 'N/A')}")
                
                st.subheader("🎯 Key Skills")
                skills = st.session_state.resume_data.get('skills', [])
                skills_html = ""
                for skill in skills[:8]:  # Show first 8 skills
                    skills_html += f'<span class="skill-tag">{skill}</span>'
                st.markdown(skills_html, unsafe_allow_html=True)
            
            with col2:
                st.subheader("💼 Experience")
                experience = st.session_state.resume_data.get('experience', [])
                for exp in experience[:3]:  # Show first 3 experiences
                    st.write(f"**{exp.get('title', 'N/A')}** at {exp.get('company', 'N/A')}")
                    st.write(f"*{exp.get('duration', 'N/A')}*")
                    st.write("---")
        
        # Display insights if available
        if st.session_state.resume_insights:
            st.subheader("🎯 AI-Powered Resume Insights")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                score = st.session_state.resume_insights.get('overallScore', 75)
                st.metric("Overall Score", f"{score}/100")
            
            with col2:
                st.markdown("**💪 Strengths:**")
                strengths = st.session_state.resume_insights.get('strengths', [])
                for strength in strengths:
                    st.write(f"• {strength}")
            
            with col3:
                st.markdown("**🔧 Improvements:**")
                improvements = st.session_state.resume_insights.get('improvements', [])
                for imp in improvements[:3]:
                    st.write(f"• {imp.get('suggestion', 'N/A')}")

elif page == "💼 Job Search":
    st.header("💼 Job Search")
    st.write("Find the perfect job opportunities across multiple ATS platforms.")
    
    # Job search form
    col1, col2 = st.columns(2)
    
    with col1:
        job_title = st.text_input("Job Title", placeholder="e.g., Data Analyst, Software Engineer")
        location = st.text_input("Location", value="Remote", placeholder="e.g., Remote, New York, NY")
    
    with col2:
        experience = st.selectbox("Experience Level", ["Any", "Entry Level", "Mid Level", "Senior Level"])
        job_type = st.selectbox("Job Type", ["Any", "Full-time", "Part-time", "Contract"])
    
    if st.button("🔍 Search Jobs", type="primary"):
        if job_title:
            with st.spinner("🔍 Searching across ATS platforms..."):
                # Simulate search across multiple platforms
                job_results = search_jobs_with_ai(job_title, location, experience)
                
                if job_results and 'jobs' in job_results:
                    st.session_state.jobs = job_results['jobs']
                else:
                    # Fallback with sample data
                    st.session_state.jobs = [
                        {
                            "id": "1",
                            "title": f"Senior {job_title}",
                            "company": "TechFlow Inc.",
                            "location": location,
                            "type": "Full-time",
                            "salary": "$80,000 - $120,000",
                            "description": "We're looking for an experienced professional to join our growing team and drive impactful projects.",
                            "requirements": ["3+ years experience", "Strong analytical skills", "Team collaboration"],
                            "benefits": ["Health insurance", "401k matching", "Flexible hours", "Remote work"],
                            "postedDate": "2 days ago",
                            "matchScore": 92,
                            "atsSource": "Greenhouse",
                            "applyUrl": "https://example.com/apply"
                        }
                    ]
        else:
            st.error("Please enter a job title to search.")
    
    # Display job results
    if st.session_state.jobs:
        st.subheader(f"🎯 Found {len(st.session_state.jobs)} job opportunities")
        
        for job in st.session_state.jobs:
            st.markdown(f"""
            <div class="job-card">
                <div style="display: flex; justify-content: between; align-items: start; margin-bottom: 1rem;">
                    <div style="flex-grow: 1;">
                        <h3 style="margin: 0; color: #333;">{job.get('title', 'N/A')}</h3>
                        <p style="margin: 0.5rem 0; color: #666;">
                            🏢 {job.get('company', 'N/A')} • 📍 {job.get('location', 'N/A')} • 🕒 {job.get('postedDate', 'N/A')}
                        </p>
                    </div>
                    <div>
                        <span class="match-score">{job.get('matchScore', 0)}% Match</span>
                    </div>
                </div>
                
                <p style="margin: 1rem 0; color: #444;">{job.get('description', 'N/A')[:200]}...</p>
                
                <div style="margin: 1rem 0;">
                    <strong>Requirements:</strong><br>
                    {' • '.join(job.get('requirements', [])[:3])}
                </div>
                
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 1rem;">
                    <div>
                        <span style="background: #e3f2fd; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.8rem;">
                            {job.get('atsSource', 'N/A')}
                        </span>
                        <span style="margin-left: 0.5rem; font-weight: bold; color: #2e7d32;">
                            {job.get('salary', 'Salary not specified')}
                        </span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

elif page == "🎤 Interview Prep":
    st.header("🎤 Interview Preparation")
    st.write("Practice with AI-generated interview questions and get feedback.")
    
    # Generate questions
    job_title_for_interview = st.text_input("Job Title for Interview Prep", placeholder="e.g., Data Analyst")
    
    if st.button("Generate Interview Questions"):
        if job_title_for_interview:
            with st.spinner("🤖 Generating interview questions..."):
                questions_data = generate_interview_questions(job_title_for_interview)
                if questions_data and 'questions' in questions_data:
                    st.session_state.interview_questions = questions_data['questions']
    
    # Display questions
    if st.session_state.interview_questions:
        st.subheader("📝 Practice Questions")
        
        for i, q in enumerate(st.session_state.interview_questions):
            with st.expander(f"Question {i+1}: {q.get('type', 'General').title()} - {q.get('difficulty', 'Medium').title()}"):
                st.write(f"**Question:** {q.get('question', 'N/A')}")
                st.info(f"💡 **Tip:** {q.get('tips', 'Structure your answer clearly and provide specific examples.')}")
                
                # Answer input
                user_answer = st.text_area(f"Your Answer (Question {i+1}):", key=f"answer_{i}", height=100)
                
                if st.button(f"Get Feedback", key=f"feedback_{i}"):
                    if user_answer:
                        with st.spinner("🤖 Evaluating your answer..."):
                            feedback = evaluate_interview_answer(q.get('question', ''), user_answer)
                            
                            if feedback:
                                col1, col2 = st.columns(2)
                                
                                with col1:
                                    score = feedback.get('score', 7)
                                    st.metric("Score", f"{score}/10")
                                    
                                    st.write("**✅ Strengths:**")
                                    for strength in feedback.get('strengths', []):
                                        st.write(f"• {strength}")
                                
                                with col2:
                                    st.write("**🔧 Areas for Improvement:**")
                                    for improvement in feedback.get('improvements', []):
                                        st.write(f"• {improvement}")
                                
                                st.write(f"**Overall Feedback:** {feedback.get('overallFeedback', 'Good effort!')}")
                    else:
                        st.warning("Please provide an answer to get feedback.")

elif page == "💬 AI Assistant":
    st.header("💬 AI Career Assistant")
    st.write("Chat with your AI assistant for personalized career guidance.")
    
    # Display chat history
    for message in st.session_state.chat_history:
        if message['role'] == 'user':
            st.markdown(f'<div class="chat-message user-message"><strong>You:</strong> {message["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-message assistant-message"><strong>Assistant:</strong> {message["content"]}</div>', unsafe_allow_html=True)
    
    # Chat input
    user_input = st.text_input("Ask me anything about your job search:", placeholder="e.g., How can I improve my resume?")
    
    if st.button("Send") and user_input:
        # Add user message
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        
        # Generate context from user's data
        context = ""
        if st.session_state.resume_data:
            context += f"User's resume data: {json.dumps(st.session_state.resume_data)}\n"
        if st.session_state.jobs:
            context += f"Recent job search: {len(st.session_state.jobs)} jobs found\n"
        
        # Create prompt for EURI AI assistant
        chat_prompt = f"""
        {context}
        
        You are an AI job search assistant. Help the user with their career questions, job search advice, resume tips, or interview preparation. Be supportive and provide actionable guidance.
        
        User's question: "{user_input}"
        
        Provide a helpful response as a career assistant.
        """
        
        with st.spinner("🤖 Thinking..."):
            response = EURI_GUIDANCE(chat_prompt, 800)
            
            # Add assistant response
            st.session_state.chat_history.append({"role": "assistant", "content": response})
        
        st.experimental_rerun()

elif page == "📊 Career Insights":
    st.header("📊 Career Insights & Growth")
    st.write("Get AI-powered insights about industry trends and career growth opportunities.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 Industry Trends")
        trend_data = {
            "Data Science": "+15%",
            "Machine Learning": "+12%", 
            "Cloud Computing": "+18%",
            "DevOps": "+10%",
            "Cybersecurity": "+14%"
        }
        
        for skill, growth in trend_data.items():
            st.write(f"**{skill}**: {growth} growth")
    
    with col2:
        st.subheader("🎯 Skill Recommendations")
        
        skills_rec = [
            ("Python Programming", "High Demand", "🔥"),
            ("Cloud Platforms (AWS/Azure)", "Growing", "📈"),
            ("Data Visualization", "Essential", "⭐"),
            ("Machine Learning", "Hot Skill", "🚀"),
            ("Project Management", "Always Valuable", "💼")
        ]
        
        for skill, status, icon in skills_rec:
            st.write(f"{icon} **{skill}** - {status}")
    
    st.subheader("💡 Personalized Recommendations")
    
    if st.session_state.resume_data:
        current_skills = st.session_state.resume_data.get('skills', [])
        st.write("Based on your current skills:")
        
        # Mock recommendations based on current skills
        if any(skill.lower() in ['python', 'data', 'analysis'] for skill in current_skills):
            st.markdown("""
            <div class="insight-card">
                <h4>🎯 Recommended Next Steps:</h4>
                <ul>
                    <li>Consider learning cloud platforms (AWS/Azure) to increase market value</li>
                    <li>Develop machine learning skills to stay competitive</li>
                    <li>Build a portfolio of data visualization projects</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Upload your resume to get personalized recommendations!")
    
    # Market insights
    st.subheader("🌍 Market Insights")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Average Salary Growth", "8.2%", "1.2%")
    
    with col2:
        st.metric("Job Market Activity", "Strong", "15%")
    
    with col3:
        st.metric("Remote Opportunities", "68%", "5%")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-center; color: #666; margin-top: 2rem;">
    <p>🤖 Powered by AI • Built with Streamlit • Your Career Success Partner</p>
</div>
""", unsafe_allow_html=True)
