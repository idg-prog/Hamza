import time
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from datetime import datetime, timedelta
import os
import json
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# --- TIME TRACKING CONFIGURATION (SAFEGUARD) ---
# ==========================================
START_TIME = time.time()
# 5.5 hours = 5.5 * 60 * 60 = 19,800 seconds
MAX_DURATION_SECONDS = 21000 

def has_time_expired():
    """Returns True if the script has been running for more than 5.5 hours."""
    elapsed = time.time() - START_TIME
    return elapsed >= MAX_DURATION_SECONDS

# ==========================================
# --- HELPER FUNCTIONS ---
# ==========================================
def extract_emails(text):
    """Extracts unique email addresses from a text block using regex."""
    if not text or text == "Not Found":
        return ""
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    found_emails = re.findall(email_pattern, text)
    # Deduplicate and format as a comma-separated string
    return ", ".join(sorted(list(set(found_emails))))

# ==========================================
# --- CONFIGURATION & SEARCH CRITERIA ---
# ==========================================
yesterday = datetime.now() - timedelta(days=1)
today_date_str = datetime.now().strftime('%Y-%m-%d') # Use today's date for counts

countries = [
    "Saudi Arabia", "United Arab Emirates", "Dubai","Abu Dhabi",
    "Luxembourg", "Switzerland", "Estonia", "Denmark", "Finland", "Sweden", "Norway", "austria", "Latvia", "Lithuania", "Ireland",
    "Czech Republic", "Hungary", "Romania", "Slovakia", "Cyprus", "Iceland", "European Economic Area",
    "Morocco", "Qatar", "Oman", "Kuwait", "Bahrain",
    "Japan", "South Korea", "Hong Kong SAR", "Singapore", "Australia", "New Zealand", "Turkey", "Canada",
    "Bosnia and Herzegovina", "Albania", "Ukraine", "Russia", "South Africa", "Mauritius", "Greenland",
]

excluded_countries = ["United States", "USA", "États-Unis", "India", "Pakistan", "Philippines", "Israel", "Vietnam"]

keywords_for_scraping = [ # Keywords used to search on LinkedIn
    "AI", "IA", "ai automation", "prompt", "workflow", "automatisation", "automation", "FDE",
    "python", "no code", "low code", "no-code", "low-code", "Data", "RPA", "n8n", "llm",
    "GTM", "Marketing", "zapier", "GEO",
]

# Keywords for the "Linkedin Worldwide" sheet filter
linkedin_worldwide_filter_keywords = [
    "n8n", "zapier", "make.com", "integromat"
]

# ==========================================
# --- SKILL CATEGORIES & DICTIONARIES ---
# ==========================================
skill_categories = {
    "Data Analyst": [
        "VBA", "power query", "DAX", "power bi", "tableau", "Excel",
        "data visualization", "data analysis", "web scraping",
        "looker", "qlik", "Streamlit", "Real-time analytics", "Microsoft Fabric"
    ],
    "Data Engineer": [
        "etl", "airflow", "dbt", "Apache", "kafka", "hadoop", "snowflake", "databricks", "redshift", "bigquery", "Databricks",
        "batch processing", "stream processing", "data modeling", "data pipelines", "SQL", "Nosql", "MLflow", "Lakehouse architecture", "Kubeflow", "CI/CD" 
    ],
    "Data Scientist": [
        "predictive modeling", "model evaluation",
        "statistics", "nlp", "computer vision",
        "scikit-learn", "tensorflow", "pytorch", "keras", "xgboost", "lightgbm", "MCP",
        "time series", "a/b testing"
    ],
    "AI/ML Engineer": [
        "llm", "prompt engineering", 'context engineering', "Local llm",
        "fine-tuning", "fine tuning", "rag", "genai", "gen ai", "MLOPS", "Machine learning",
        "retrieval augmented generation", "hugging face", "openai", "gemini",
        "deepseek", "claude", "transformers", "bert", "llama", "ollama",
        "Hugging Face ", "AutoML ", "MLOps", "Few-shot learning",
        "Reinforcement learning", "MLflow", "LangChain", "Langraph", "crewai", "tenseflow", "keras", "sckit-learn", "sckit learn"
    ],
    "AI Automation/RPA/No-Code": [
        "n8n", "zapier", "make.com", "integromat", "uipath", "power automate", "workato",
        "power apps", "mendix", "automation anywhere", "rpa", "appian", "servicenow",
        "Bubble", "Webflow", "Framer", "Glide", "Retool", "Lovable", "Bolt", "Replit",
        "Openclaw", "Hermes", "Claude Code", "Claude Cowork", "Antigravity", "copilot studio", "Claude SDK", "OpenAI SDK","Semantic Kernel"
    ],
    "Programming Languages": [
        "python", "javascript", "go", "java", "c#", "scala",
        "kotlin", "swift", "php", "ruby", "rust", "HTML", "CSS", "sql", "nosql",
        "typescript", "bash", "shell scripting", "R"
    ],
    "DevOps": [
        "docker", "kubernetes", "ci/cd", "github actions", "jenkins", "Kafka",
        "terraform", "ansible", "helm", "prometheus", "grafana", "git", "Apache"
    ],
    "Cloud Platforms": [
        "aws", "azure", "gcp",
        "AWS Bedrock", "Azure OpenAI Service", "GCP Vertex AI"
    ],
    "Databases": [
        "postgresql", "mysql", "mongodb", "redis", "cassandra", "sqlite",
        "Neo4j", "Amazon QLDB", "CockroachDB", "YugabyteDB", "TimescaleDB", "DynamoDB", "cloud-native DB",
        "Pinecone", "Weaviate", "Qdrant", "pgvector"
    ],
    "Frontend/UI/UX": [
        "React", "Next.js", "Vue.js", "Nuxt.js", "Angular", "SvelteKit", "SolidJS", "Astro",
        "TailwindCSS", "CSS", "Framer Motion", "GSAP",
        "Figma", "Adobe", "Canva", "Framer", "Capcut",
        "Three.js", "WebGL", "React Three Fiber", "blender"
    ],
    "Backend/API Development": [
        "node.js", "express.js", "nestjs", "ASP.net",
        "spring boot", "django", "flask", "fastapi", "asp.net", "Deno",
        "REST API", "GraphQL", "gRPC", "tRPC", "Async",
        "WebSockets", "Kafka", "OAuth 2.0", "JWT", "API"
    ],
    "Project / Product Management": [
        "Agile", "Scrum", "Kanban", "Scrum@Scale", "SAFe",
        "hybrid project frameworks", "OKRs", "PMP", "Trello",
        "Jira", "Linear", "ClickUp", "Notion", "Asana", "Ms Project",
        "product roadmapping", "backlog grooming", "stakeholder management",
        "risk management", "product analytics"
    ],
    "Cybersecurity": [
        "penetration", "ethical hacking", "OWASP",
        "SIEM", "SOC",
        "vulnerability assessment", "zero-trust architecture",
        "IAM", "OAuth",
        "API security", "CSPM", "container security",
        "DevSecOps", "secrets management",
        "threat modeling", "incident response"
    ],
    "Business Intelligence & Strategy": [
        "market research", "competitive analysis", "strategic planning",
        "business case writing", "ROI",
        "decision making", "KPI",
        "veille stratégique",
        "Lean Six Sigma", "HSE",
        "ISO", "QHSE", "ESG"
    ],
    "Ads / Growth Marketing": [
        "Google Ads", "Meta Ads", "Instagram Ads", "TikTok Ads", "LinkedIn Ads",
        "Chatgpt ads",
        "Google Tag Manager", "search console", "Ahrefs", "Semrush", "Moz",
        "Google Analytics", "Looker"
    ],
    "ERP Systems": [
        "SAP", "Salesforce", "Oracle", "Google sheets",
        "Microsoft Dynamics", "Microsoft 365", "Odoo", "NetSuite", "HubSpot", "Zoho", "Monday CRM",
        "Pipedrive", "Freshsales"
    ]
}

# Consolidate all skills into a single list for scraping and create a skill-to-tag map
count_skills_keywords = []
skill_to_tag_map = {}
for tag, skills in skill_categories.items():
    for skill in skills:
        count_skills_keywords.append(skill)
        skill_to_tag_map[skill] = tag # Map each skill to its primary tag

# Ensure unique skills in the consolidated list
count_skills_keywords = list(set(count_skills_keywords))


# ==========================================
# --- STEP 1 — SCRAPE JOB LINKS ---
# ==========================================
links = [] # Will now store tuples: (clean_url, api_link, keyword)
seen_job_ids = set() # O(1) lookups: fixes the CPU freezing issue
break_step1 = False

print("🚀 Starting Step 1: Scraping job links...")
for country in countries:
    if break_step1:
        break
    for keyword in keywords_for_scraping:
        if break_step1:
            break
        for i in range(0, 3):  
            
            # --- Safetime Check ---
            if has_time_expired():
                print("⚠️ Approaching 5.5 hours limit during Step 1! Breaking out early.")
                break_step1 = True
                break

            url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={keyword}&location={country}&f_TPR=r86400&start={i*25}"
            headers = {"User-Agent": "Mozilla/5.0"}

            time.sleep(1)
            try:
                # FIX 1: Added timeout=10 so the script doesn't hang forever if LinkedIn blocks it
                response = requests.get(url, headers=headers, timeout=10)
                soup = BeautifulSoup(response.text, "html.parser")
                job_links = soup.find_all("a", class_="base-card__full-link")

                for job in job_links:
                    job_url = job.get("href")
                    if not job_url: 
                        continue
                    
                    # FIX 2: Safely extract purely the numerical Job ID to ignore tracking parameters
                    url_without_params = job_url.split('?')[0]
                    job_id = url_without_params.split('-')[-1]
                    
                    if job_id.isdigit():
                        # FIX 3: Set lookups are instant, fixing the CPU bottleneck
                        if job_id not in seen_job_ids:
                            seen_job_ids.add(job_id)
                            clean_url = f"https://www.linkedin.com/jobs/view/{job_id}"
                            api_link = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
                            links.append((clean_url, api_link, keyword))
            except Exception as e:
                print(f"Error fetching search page: {e}")

print(f"Total unique job links found: {len(links)}")

# ==========================================
# --- STEP 2 — SCRAPE JOB DETAILS ---
# ==========================================
all_job_data = [] 
headers = {"User-Agent": "Mozilla/5.0"}

print("🚀 Starting Step 2: Scraping specific job profiles...")
for clean_url, api_link, searched_keyword in links:
    
    # --- Safetime Check ---
    if has_time_expired():
        print(f"⚠️ Reached the 5.5 hours benchmark during Step 2. Activating fallback script to process existing ({len(all_job_data)}) records.")
        break

    try:
        time.sleep(1)
        # FIX 4: Requesting the API link instead of full webpage + Added Timeout
        response = requests.get(api_link, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        title_tag = soup.find('h1', class_='top-card-layout__title') or soup.find('h2', class_='top-card-layout__title')
        title = title_tag.text.strip() if title_tag else "Not Found"

        company_tag = soup.find('a', class_='topcard__org-name-link')
        company = company_tag.text.strip() if company_tag else "Not Found"

        country_tag = soup.find('span', class_='topcard__flavor--bullet')
        country = country_tag.text.strip() if country_tag else "Not Found"

        desc_tag = soup.find('div', class_='description__text--rich')
        desc = desc_tag.text.strip() if desc_tag else "Not Found"

        # Skip excluded countries
        if any(excluded.lower() in country.lower() for excluded in excluded_countries):
            continue

        all_job_data.append({
            "Date": today_date_str,
            "title": title,
            "company": company,
            "country": country,
            "link": clean_url, # Now saving the beautiful clean URL to your sheet
            "searched_keyword": searched_keyword,
            "description": desc 
        })

    except Exception as e:
        print(f"Error scraping details for {clean_url}: {e}")


# ==========================================
# --- STEP 3 TO 6 — PROCESS & SAVE DATA ---
# ==========================================
if not all_job_data:
    print("❌ No data was parsed during this execution window. Google Sheets will remain unchanged.")
else:
    # --- Step 3 — Create DataFrame from all scraped data ---
    df_all_jobs = pd.DataFrame(all_job_data)
    df_all_jobs = df_all_jobs.drop_duplicates(subset=['link']).reset_index(drop=True)
    print(f"Total unique jobs scraped (after initial deduplication): {len(df_all_jobs)}")

    # --- Step 4 — Process for "Linkedin Worldwide" sheet ---
    def check_worldwide_keywords(description):
        found_world_keywords = [k for k in linkedin_worldwide_filter_keywords if re.search(r'\b' + re.escape(k) + r'\b', description, flags=re.IGNORECASE)]
        return ", ".join(found_world_keywords) if found_world_keywords else ""

    # Extract emails & filter keywords from description
    df_all_jobs['Email'] = df_all_jobs['description'].apply(extract_emails)
    df_all_jobs['found_linkedin_worldwide_keywords'] = df_all_jobs['description'].apply(check_worldwide_keywords)
    
    filtered_worldwide_df = df_all_jobs[df_all_jobs['found_linkedin_worldwide_keywords'] != ""].copy()

    # Select and reorder columns for "Linkedin Worldwide" sheet (including Email)
    filtered_worldwide_df = filtered_worldwide_df[[
        "Date", "title", "company", "country", "link", "Email", "searched_keyword", "found_linkedin_worldwide_keywords"
    ]].rename(columns={"found_linkedin_worldwide_keywords": "Found Keywords"})

    print(f"Jobs for 'Linkedin Worldwide' sheet (unique and filtered): {len(filtered_worldwide_df)}")

    # --- Step 5 — Process for "Count Skills" sheet ---
    skill_counts = {skill: 0 for skill in count_skills_keywords}

    for index, row in df_all_jobs.iterrows():
        description = row['description']
        for skill in count_skills_keywords:
            # Use regex for whole word matching
            if re.search(r'\b' + re.escape(skill) + r'\b', description, flags=re.IGNORECASE):
                skill_counts[skill] += 1

    # Convert skill counts to a DataFrame
    df_skill_counts_list = []
    for skill, count in skill_counts.items():
        tag = skill_to_tag_map.get(skill, "Other") # Get the tag for the skill, default to "Other"
        df_skill_counts_list.append({"Date": today_date_str, "Skill": skill, "Tag": tag, "Count": count})

    df_skill_counts = pd.DataFrame(df_skill_counts_list)
    df_skill_counts = df_skill_counts[['Date', 'Tag', 'Skill', 'Count']] # Reorder columns to place Tag after Date

    print(f"\nSkill counts for today ({today_date_str}):")
    print(df_skill_counts)

    # --- Step 6: Connect and Update Google Sheets ---
    service_account_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT"])
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
    client = gspread.authorize(credentials)

    SPREADSHEET_URL = os.environ["SPREADSHEET_URL"]

    # --- Update "Linkedin Worldwide" Sheet ---
    WORKSHEET_NAME_WORLDWIDE = 'Linkedin Worldwide'
    try:
        sheet_worldwide = client.open_by_url(SPREADSHEET_URL).worksheet(WORKSHEET_NAME_WORLDWIDE)
    except gspread.WorksheetNotFound:
        sheet_worldwide = client.open_by_url(SPREADSHEET_URL).add_worksheet(title=WORKSHEET_NAME_WORLDWIDE, rows="1000", cols="20")

    print(f"\nUpdating '{WORKSHEET_NAME_WORLDWIDE}' sheet...")
    sheet_worldwide.clear() # Clear existing data
    
    # Avoid gspread updates with completely empty structures
    if not filtered_worldwide_df.empty:
        sheet_worldwide.update(
            [filtered_worldwide_df.columns.values.tolist()] +
            filtered_worldwide_df.values.tolist()
        )
    else:
        sheet_worldwide.update([["Date", "title", "company", "country", "link", "Email", "searched_keyword", "Found Keywords"]])
    print(f"✅ Data successfully updated in '{WORKSHEET_NAME_WORLDWIDE}'!")

    # --- Update "Count Skills" Sheet ---
    WORKSHEET_NAME_COUNT_SKILLS = 'Count Skills'
    try:
        sheet_count_skills = client.open_by_url(SPREADSHEET_URL).worksheet(WORKSHEET_NAME_COUNT_SKILLS)
    except gspread.WorksheetNotFound:
        sheet_count_skills = client.open_by_url(SPREADSHEET_URL).add_worksheet(title=WORKSHEET_NAME_COUNT_SKILLS, rows="1000", cols="20")

    print(f"\nUpdating '{WORKSHEET_NAME_COUNT_SKILLS}' sheet...")

    # Get existing data from the sheet to append
    existing_data = sheet_count_skills.get_all_values()
    if existing_data:
        # Check if headers match, if not, update headers
        if existing_data[0] != df_skill_counts.columns.tolist():
            sheet_count_skills.clear()
            sheet_count_skills.update([df_skill_counts.columns.tolist()])
    else:
        # Sheet is empty, add headers first
        sheet_count_skills.update([df_skill_counts.columns.tolist()])

    # Append new data securely
    sheet_count_skills.append_rows(df_skill_counts.values.tolist(), value_input_option='RAW', insert_data_option='INSERT_ROWS')
    print(f"✅ Data successfully appended to '{WORKSHEET_NAME_COUNT_SKILLS}'!")

print(f"🏁 Execution finished gracefully. Total time elapsed: {round((time.time() - START_TIME) / 60, 2)} minutes.")
