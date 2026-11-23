import time
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from datetime import datetime
import os
import json
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# CONFIGURATION
# ==========================================

START_TIME = time.time()
MAX_DURATION_SECONDS = 21000

TODAY = datetime.now().strftime("%Y-%m-%d")

# ==========================================
# TARGET COUNTRIES
# ==========================================

countries = [
    # Middle East
    "United Arab Emirates",
    "Saudi Arabia",
    "Qatar",
    "Bahrain",
    "Kuwait",
    "Oman",


    # Europe
    "United Kingdom",
    "Ireland",
    "Germany",
    "France",
    "Netherlands",
    "Belgium",
    "Spain",
    "Portugal",
    "Italy",
    "Poland",
    "Romania",
    "Switzerland",
    "Sweden",
    "Denmark",
    "Finland",
    "Norway",
    "turkey"

]

# ==========================================
# JOB KEYWORDS
# ==========================================

keywords_for_scraping = [
    "Virtual Assistant",
    "Remote Assistant",
    "Data Entry",
    "Remote Customer Support",
    "Chat Support",
    "Email Support",
    "Administrative Assistant",
    "Back Office Assistant Remote",
    "Online Assistant"
]

# ==========================================
# SETTINGS
# ==========================================

MAX_PAGES_PER_SEARCH = 2

# LinkedIn work type filter:
# 2 = Remote
REMOTE_ONLY = True

# Jobs posted in the last 24 hours
POSTED_WITHIN = "r86400"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    )
}

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def has_time_expired():
    return time.time() - START_TIME >= MAX_DURATION_SECONDS


def extract_emails(text):
    if not text or text == "Not Found":
        return ""

    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

    emails = re.findall(pattern, text)

    return ", ".join(sorted(set(emails)))


def clean_text(element):
    if element:
        return element.get_text(" ", strip=True)
    return "Not Found"


def get_remote_status(description, title):
    text = f"{title} {description}".lower()

    remote_words = [
        "remote",
        "work from home",
        "working remotely",
        "fully remote",
        "distributed team",
        "home-based",
        "work remotely"
    ]

    if any(word in text for word in remote_words):
        return "Remote"

    return "Remote - LinkedIn Filter"


# ==========================================
# STEP 1: SCRAPE JOB LINKS
# ==========================================

links = []
seen_job_ids = set()

print("=" * 50)
print("STARTING REMOTE JOB SEARCH")
print("=" * 50)

session = requests.Session()
session.headers.update(HEADERS)

total_searches = len(countries) * len(keywords_for_scraping)

search_counter = 0

for country in countries:

    if has_time_expired():
        print("Time limit reached. Stopping searches.")
        break

    for keyword in keywords_for_scraping:

        if has_time_expired():
            break

        search_counter += 1

        print(
            f"[{search_counter}/{total_searches}] "
            f"Searching: {keyword} | {country}"
        )

        for page in range(MAX_PAGES_PER_SEARCH):

            if has_time_expired():
                break

            search_url = (
                "https://www.linkedin.com/jobs-guest/jobs/api/"
                "seeMoreJobPostings/search"
            )

            params = {
                "keywords": keyword,
                "location": country,
                "f_TPR": POSTED_WITHIN,
                "start": page * 25
            }

            if REMOTE_ONLY:
                params["f_WT"] = "2"

            try:
                time.sleep(1)

                response = session.get(
                    search_url,
                    params=params,
                    timeout=15
                )

                if response.status_code != 200:
                    print(f"Search returned HTTP {response.status_code}")
                    continue

                soup = BeautifulSoup(
                    response.text,
                    "html.parser"
                )

                job_links = soup.find_all(
                    "a",
                    class_="base-card__full-link"
                )

                for job in job_links:

                    job_url = job.get("href")

                    if not job_url:
                        continue

                    url_without_params = job_url.split("?")[0]

                    job_id = url_without_params.rstrip("/").split("-")[-1]

                    if job_id.isdigit() and job_id not in seen_job_ids:

                        seen_job_ids.add(job_id)

                        clean_url = (
                            f"https://www.linkedin.com/jobs/view/{job_id}"
                        )

                        api_link = (
                            "https://www.linkedin.com/jobs-guest/"
                            f"jobs/api/jobPosting/{job_id}"
                        )

                        links.append({
                            "clean_url": clean_url,
                            "api_link": api_link,
                            "keyword": keyword,
                            "search_country": country
                        })

            except requests.RequestException as e:
                print(f"Search error: {e}")

print("\nTotal unique job links:", len(links))


# ==========================================
# STEP 2: SCRAPE JOB DETAILS
# ==========================================

all_job_data = []

print("\nSTARTING JOB DETAILS EXTRACTION")

for index, job in enumerate(links, start=1):

    if has_time_expired():
        print("Time limit reached during job extraction.")
        break

    try:

        time.sleep(1)

        response = session.get(
            job["api_link"],
            timeout=15
        )

        if response.status_code != 200:
            continue

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        title = clean_text(
            soup.find(
                "h1",
                class_="top-card-layout__title"
            ) or soup.find(
                "h2",
                class_="top-card-layout__title"
            )
        )

        company = clean_text(
            soup.find(
                "a",
                class_="topcard__org-name-link"
            )
        )

        location = clean_text(
            soup.find(
                "span",
                class_="topcard__flavor--bullet"
            )
        )

        if location == "Not Found":
            location = job["search_country"]

        desc_tag = soup.find(
            "div",
            class_="description__text"
        )

        description = clean_text(desc_tag)

        # Skip invalid job records
        if title == "Not Found" or company == "Not Found":
            continue

        # Remote status
        work_mode = get_remote_status(
            description,
            title
        )

        all_job_data.append({

            "Date": TODAY,

            "title": title,

            "company": company,

            "country": location,

            "work_mode": work_mode,

            "link": job["clean_url"],

            "searched_keyword": job["keyword"],

            "description": description

        })

        print(
            f"[{index}/{len(links)}] "
            f"Collected: {title} | {company}"
        )

    except Exception as e:
        print(
            f"Error scraping {job['clean_url']}: {e}"
        )


# ==========================================
# STEP 3: PROCESS DATA
# ==========================================

if not all_job_data:

    print("No jobs collected. Google Sheets unchanged.")

else:

    df = pd.DataFrame(all_job_data)

    # Remove duplicates
    df = df.drop_duplicates(
        subset=["link"]
    ).reset_index(drop=True)

    # Extract contact emails
    df["Email"] = df["description"].apply(
        extract_emails
    )

    # Final output columns
    final_df = df[[
        "Date",
        "title",
        "company",
        "country",
        "work_mode",
        "link",
        "searched_keyword",
        "Email"
    ]]

    # Sort by company and title
    final_df = final_df.sort_values(
        by=["country", "title"]
    ).reset_index(drop=True)

    print("\nJOBS SUMMARY")
    print("Total jobs:", len(final_df))
    print("Countries:", final_df["country"].nunique())
    print("Companies:", final_df["company"].nunique())

    # ==========================================
    # STEP 4: GOOGLE SHEETS
    # ==========================================

    print("\nConnecting to Google Sheets...")

    service_account_info = json.loads(
        os.environ["GOOGLE_SERVICE_ACCOUNT"]
    )

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    credentials = Credentials.from_service_account_info(
        service_account_info,
        scopes=SCOPES
    )

    client = gspread.authorize(credentials)

    SPREADSHEET_URL = os.environ["SPREADSHEET_URL"]

    WORKSHEET_NAME = "Youssra"

    spreadsheet = client.open_by_url(
        SPREADSHEET_URL
    )

    try:

        sheet = spreadsheet.worksheet(
            WORKSHEET_NAME
        )

    except gspread.WorksheetNotFound:

        sheet = spreadsheet.add_worksheet(
            title=WORKSHEET_NAME,
            rows="2000",
            cols="20"
        )

    print("Updating Google Sheets...")

    # Clear old data, as in your original script
    sheet.clear()

    # Write new data
    sheet.update(
        values=[
            final_df.columns.tolist()
        ] + final_df.fillna("").values.tolist(),
        range_name="A1"
    )

    print("\nSUCCESS: Google Sheets updated!")

    print("Total jobs saved:", len(final_df))


# ==========================================
# FINAL SUMMARY
# ==========================================

elapsed = round(
    (time.time() - START_TIME) / 60,
    2
)

print("\n" + "=" * 50)
print("JOB SCRAPER FINISHED")
print("=" * 50)

print("Total job links found:", len(links))
print("Total jobs extracted:", len(all_job_data))
print("Execution time:", elapsed, "minutes")
