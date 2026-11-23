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
today_date_str = datetime.now().strftime('%Y-%m-%d')

countries = [
    "Switzerland", "Denmark", "Finland", "Sweden", "Norway", "Greenland", "Iceland",
    "Australia", "New Zealand", "Ireland", "Turkey",
    "Canada", "United Kingdom", "Germany", "Belgium", 
    "European Economic Area", "EMEA"
]

excluded_countries = ["United States", "USA", "États-Unis", "India", "Pakistan", "Philippines", "Israel", "Vietnam", "Russia", "Ukraine"]

keywords_for_scraping = [    
    "Warehouse", "Construction", "Labourer", "Fruit Picker", "Demolition Worker",
    "Office Installer", "Event Setup Crew", "Furniture Removalist", "Landscaping",
    "Utility Worker", "Trade Assistant", "Mechanical Fitter", "Boilermaker",
    "Dump Truck Operator", "Rope Access Technician", "Kitchenhand", "Driller's Offsider",
    "Storeperson", "Maintenance Offsider", "Scaffolder's Offsider", "Mine Site Labourer"
]

# ==========================================
# --- STEP 1 — SCRAPE JOB LINKS ---
# ==========================================
links = [] # Stores tuples: (clean_url, api_link, keyword)
seen_job_ids = set() # O(1) lookups: prevents duplicate API calls
break_step1 = False

print("🚀 Starting Step 1: Scraping job links...")
for country in countries:
    if break_step1:
        break
    for keyword in keywords_for_scraping:
        if break_step1:
            break
        for i in range(0, 2):  
            
            # --- Safetime Check ---
            if has_time_expired():
                print("⚠️ Approaching 5.5 hours limit during Step 1! Breaking out early.")
                break_step1 = True
                break

            url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={keyword}&location={country}&f_TPR=r86400&start={i*25}"
            headers = {"User-Agent": "Mozilla/5.0"}

            time.sleep(1)
            try:
                response = requests.get(url, headers=headers, timeout=10)
                soup = BeautifulSoup(response.text, "html.parser")
                job_links = soup.find_all("a", class_="base-card__full-link")

                for job in job_links:
                    job_url = job.get("href")
                    if not job_url: 
                        continue
                    
                    url_without_params = job_url.split('?')[0]
                    job_id = url_without_params.split('-')[-1]
                    
                    if job_id.isdigit():
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
        print(f"⚠️ Reached the 5.5 hours benchmark during Step 2. Processing existing ({len(all_job_data)}) records.")
        break

    try:
        time.sleep(1)
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
            "link": clean_url,
            "searched_keyword": searched_keyword,
            "description": desc 
        })

    except Exception as e:
        print(f"Error scraping details for {clean_url}: {e}")

# ==========================================
# --- STEP 3 — PROCESS & SAVE TO GOOGLE SHEETS ---
# ==========================================
if not all_job_data:
    print("❌ No data was parsed during this execution window. Google Sheets will remain unchanged.")
else:
    # Create DataFrame from all scraped data
    df_all_jobs = pd.DataFrame(all_job_data)
    df_all_jobs = df_all_jobs.drop_duplicates(subset=['link']).reset_index(drop=True)
    print(f"Total unique jobs scraped (after initial deduplication): {len(df_all_jobs)}")

    # Extract emails from description
    df_all_jobs['Email'] = df_all_jobs['description'].apply(extract_emails)
    
    # Select and reorder final columns for Google Sheets output
    final_df = df_all_jobs[[
        "Date", "title", "company", "country", "link", "searched_keyword", "Email"
    ]]

    print(f"Jobs ready to write to Google Sheets: {len(final_df)}")

    # Connect to Google Sheets via Service Account
    service_account_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT"])
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
    client = gspread.authorize(credentials)

    SPREADSHEET_URL = os.environ["SPREADSHEET_URL"]

    # Target Worksheet: "Sheet1"
    WORKSHEET_NAME = 'Sheet1'
    try:
        sheet = client.open_by_url(SPREADSHEET_URL).worksheet(WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        sheet = client.open_by_url(SPREADSHEET_URL).add_worksheet(title=WORKSHEET_NAME, rows="1000", cols="20")

    print(f"\nUpdating '{WORKSHEET_NAME}' sheet...")
    sheet.clear() # Clear existing data
    
    # Update sheet content
    if not final_df.empty:
        sheet.update(
            [final_df.columns.values.tolist()] +
            final_df.values.tolist()
        )
    else:
        sheet.update([["Date", "title", "company", "country", "link", "searched_keyword", "Email"]])
        
    print(f"✅ Data successfully updated in '{WORKSHEET_NAME}'!")

print(f"🏁 Execution finished gracefully. Total time elapsed: {round((time.time() - START_TIME) / 60, 2)} minutes.")
