# 🤖 AI Job Search Assistant

A comprehensive AI-powered job search platform that combines real-time job scraping, intelligent resume analysis, and personalized career guidance. Built with Streamlit and powered by SerpAPI for reliable job data and EURI AI for resume insights.

## ✨ Features

### 🌍 Global Job Search
- **Real-time job scraping** from 50+ job platforms using SerpAPI
- **8 countries supported**: US, UK, Canada, Australia, Germany, France, India, Singapore
- **Smart filtering** by time range, industry, location, and source
- **Multiple job sources**: LinkedIn, Indeed, Glassdoor, Greenhouse, Lever, company career pages
- **Export capabilities** to CSV with full job metadata

### 📄 AI Resume Analyzer
- **Intelligent parsing** of PDF, DOCX, and TXT resume formats
- **ATS optimization** scoring and recommendations
- **Industry-specific analysis** across 6+ major industries
- **Skills gap identification** and keyword suggestions
- **Actionable improvement recommendations**

### 💬 Career Chat Assistant
- **AI-powered career guidance** using EURI's advanced language models
- **Personalized advice** based on uploaded resume data
- **Interview preparation** tips and salary guidance
- **Career transition** planning and skill development recommendations

### 📊 Advanced Analytics
- **Job market insights** with source distribution analysis
- **Search performance metrics** and relevance scoring
- **Resume strength assessment** across multiple dimensions
- **Industry alignment** scoring and recommendations

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- SerpAPI account (100 free searches/month)
- EURI AI API access
- Streamlit

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/ai-job-search-assistant.git
cd ai-job-search-assistant
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Set up API keys**

Create `.streamlit/secrets.toml`:
```toml
EURI_API_KEY = "your_euri_api_key_here"
SERPAPI_KEY = "your_serpapi_key_here"
```

Or set environment variables:
```bash
export EURI_API_KEY="your_euri_api_key_here"
export SERPAPI_KEY="your_serpapi_key_here"
```

4. **Run the application**
```bash
streamlit run app.py
```

5. **Open your browser**
Navigate to `http://localhost:8501`

## 📦 Dependencies

```txt
streamlit>=1.28.0
requests>=2.31.0
beautifulsoup4>=4.12.0
PyPDF2>=3.0.0
python-docx>=0.8.11
pandas>=2.0.0
plotly>=5.15.0
```

## 🔧 Configuration

### API Keys Required

#### SerpAPI (Job Search)
- **Free tier**: 100 searches/month
- **Sign up**: [serpapi.com](https://serpapi.com)
- **Purpose**: Reliable Google search results for job listings

#### EURI AI (Resume Analysis & Chat)
- **Purpose**: Advanced language model for resume parsing and career advice
- **Sign up**: [euron.one](https://euron.one)

### Supported Countries & Job Sites

| Country | Code | Primary Job Sites |
|---------|------|-------------------|
| 🇺🇸 United States | `us` | LinkedIn, Indeed, Glassdoor, Greenhouse, Lever |
| 🇬🇧 United Kingdom | `uk` | LinkedIn, Indeed, Totaljobs, Reed, CV-Library |
| 🇨🇦 Canada | `ca` | LinkedIn, Indeed, Workopolis, Monster |
| 🇦🇺 Australia | `au` | LinkedIn, Seek, Indeed, CareerOne |
| 🇩🇪 Germany | `de` | LinkedIn, XING, StepStone, Indeed |
| 🇫🇷 France | `fr` | LinkedIn, Indeed, APEC, Monster |
| 🇮🇳 India | `in` | LinkedIn, Naukri, Indeed, Monster |
| 🇸🇬 Singapore | `sg` | LinkedIn, Indeed, JobsBank |

### Industry Coverage

- **Technology**: Software Engineering, Data Science, DevOps, Cybersecurity, AI/ML
- **Finance & Banking**: Investment Banking, Financial Analysis, Risk Management, Fintech
- **Healthcare**: Clinical Research, Healthcare IT, Medical Device, Pharmaceutical
- **Marketing & Sales**: Digital Marketing, Sales Development, Brand Management
- **Consulting**: Management Consulting, IT Consulting, Strategy Consulting
- **Education**: K-12 Teaching, Higher Education, Corporate Training

## 📖 Usage Guide

### 1. Job Search

1. **Navigate to "Job Search"** in the sidebar
2. **Enter job details**:
   - Job title (e.g., "Software Engineer", "Data Analyst")
   - Target country and city (optional)
   - Industry and domain (optional)
   - Time range (past hour to past year)
3. **Configure search intensity** (5-15 queries)
4. **Click "Search Jobs"** and wait for results
5. **Filter and sort** results by source, keywords, relevance
6. **Export to CSV** or copy job links

### 2. Resume Analysis

1. **Navigate to "Resume Analyzer"**
2. **Select target industry** (optional but recommended)
3. **Upload resume** (PDF, DOCX, or TXT)
4. **Click "Analyze Resume"**
5. **Review insights**:
   - ATS compatibility score
   - Strengths and weaknesses
   - Missing keywords
   - Improvement recommendations

### 3. Career Chat

1. **Navigate to "Career Chat"**
2. **Upload resume** for personalized advice (optional)
3. **Ask questions** about:
   - Resume improvement
   - Interview preparation
   - Salary expectations
   - Career transitions
   - Skill development

## 🎯 Key Features Explained

### SerpAPI Integration
- **Reliable results**: No rate limiting or blocking issues
- **Global coverage**: Works consistently across all supported countries
- **Rich metadata**: Search position, relevance scores, source identification
- **Professional grade**: 99.9% uptime with fast response times

### AI Resume Analysis
- **Multi-format support**: PDF, DOCX, TXT with intelligent text extraction
- **Fallback parsing**: If AI fails, uses regex-based extraction
- **Industry optimization**: Tailored analysis for specific industries
- **ATS scoring**: Applicant Tracking System compatibility assessment

### Smart Job Filtering
- **Relevance scoring**: Intelligent ranking based on title match, source quality, position
- **Deduplication**: Removes duplicate listings across sources
- **Source prioritization**: Prefers direct company sites and premium platforms
- **Quality filtering**: Removes spam and irrelevant results

## 🛠️ Development

### Project Structure
```
ai-job-search-assistant/
├── app.py                 # Main Streamlit application
├── requirements.txt       # Python dependencies
├── .streamlit/
│   └── secrets.toml      # API keys (not in repo)
├── README.md             # This file

```

### Key Functions

#### Job Search (`run_serpapi_job_search`)
- Creates optimized search queries for each country
- Executes parallel searches via SerpAPI
- Deduplicates and ranks results by relevance
- Returns structured job data with metadata

#### Resume Parsing (`parse_resume_with_ai`)
- Extracts text from multiple file formats
- Uses AI to parse structured data from resume text
- Implements fallback regex-based extraction
- Validates and cleans extracted data

#### Career Chat (`chat_about_career`)
- Maintains conversation context with resume data
- Provides personalized career advice
- Handles multiple conversation threads
- Integrates with EURI AI for intelligent responses

### Error Handling
- **JSON parsing**: Robust error recovery with multiple retry attempts
- **API failures**: Graceful degradation with fallback methods
- **File processing**: Handles corrupted or unsupported files
- **Rate limiting**: Intelligent delays and retry logic

## 🚦 Deployment

### Streamlit Cloud
1. Fork this repository
2. Connect to Streamlit Cloud
3. Add secrets in Streamlit Cloud dashboard:
   - `EURI_API_KEY`
   - `SERPAPI_KEY`
4. Deploy automatically

### Local Production
```bash
# Install production dependencies
pip install -r requirements.txt

# Set environment variables
export STREAMLIT_SERVER_PORT=8501
export STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Run with production settings
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

### Docker (Optional)
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

## 📊 Performance & Limits

### SerpAPI Limits
- **Free tier**: 100 searches/month
- **Paid plans**: Up to 40,000 searches/month
- **Rate limit**: 1 request/second (handled automatically)

### Application Performance
- **Job search**: 15-30 seconds for comprehensive results
- **Resume analysis**: 30-60 seconds depending on complexity
- **Chat responses**: 3-10 seconds per message

### Optimization Tips
- Use specific job titles for better results
- Limit search intensity for faster results
- Upload clean, well-formatted resumes
- Use industry filters for targeted searches

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines:

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Commit your changes**: `git commit -m 'Add amazing feature'`
4. **Push to the branch**: `git push origin feature/amazing-feature`
5. **Open a Pull Request**

### Development Setup
```bash
# Clone your fork
git clone https://github.com/yourusername/ai-job-search-assistant.git
cd ai-job-search-assistant

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests
pytest tests/

# Run linting
flake8 app.py
black app.py
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **SerpAPI** for reliable Google search access
- **EURI AI** for advanced language model capabilities
- **Streamlit** for the amazing web framework
- **Open source community** for the excellent Python libraries

## 🔄 Changelog

### v4.0.0 (Latest)
- ✅ Added SerpAPI integration for reliable job search
- ✅ Enhanced resume parsing with fallback mechanisms
- ✅ Improved error handling and validation
- ✅ Added 8 country support with localized job sites
- ✅ Implemented advanced job filtering and analytics

### v3.0.0
- ✅ Added AI-powered career chat
- ✅ Enhanced resume analysis with industry-specific insights
- ✅ Improved UI/UX with better navigation

### v2.0.0
- ✅ Added resume upload and analysis
- ✅ Implemented job export functionality
- ✅ Enhanced search filtering options

### v1.0.0
- ✅ Initial release with basic job search
- ✅ Multi-country support
- ✅ Basic web scraping functionality

---


*Helping job seekers find their next opportunity with the power of AI*
