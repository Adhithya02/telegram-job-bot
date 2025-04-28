import requests
from bs4 import BeautifulSoup

# Define URLs to scrape
IT_JOBS_URL = "https://www.indeed.com/jobs?q=developer&l="
LINKEDIN_URL = "https://www.linkedin.com/jobs/search/?keywords=developer"
GENERIC_JOBS_URL = "https://www.example-job-site.com/jobs?q=developer"

# Define a function to scrape Indeed job listings
def scrape_indeed_jobs():
    jobs = []
    response = requests.get(IT_JOBS_URL)
    response.raise_for_status()  # Ensure the request was successful
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Inspect Indeed's HTML and adjust the classes/tags accordingly
    job_cards = soup.find_all('div', class_='jobsearch-SerpJobCard')  # Indeed job card class
    for job in job_cards:
        title = job.find('a', class_='jobtitle')
        company = job.find('span', class_='company')
        location = job.find('div', class_='location')
        apply_link = "https://www.indeed.com" + title['href'] if title else None
        
        if title and company and location and apply_link:
            job_info = {
                'title': title.get_text(strip=True),
                'company': company.get_text(strip=True),
                'location': location.get_text(strip=True),
                'apply_link': apply_link
            }
            jobs.append(job_info)
    
    return jobs

# Define a function to scrape LinkedIn job listings
def scrape_linkedin_jobs():
    jobs = []
    response = requests.get(LINKEDIN_URL)
    response.raise_for_status()  # Ensure the request was successful
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # LinkedIn structure might differ, you'll need to find the right tag/class for jobs
    job_cards = soup.find_all('li', class_='result-card')  # Example class for LinkedIn job cards
    for job in job_cards:
        title = job.find('h3', class_='result-card__title')
        company = job.find('h4', class_='result-card__subtitle')
        location = job.find('span', class_='job-result-card__location')
        apply_link = job.find('a', href=True)['href'] if job.find('a', href=True) else None
        
        if title and company and location and apply_link:
            job_info = {
                'title': title.get_text(strip=True),
                'company': company.get_text(strip=True),
                'location': location.get_text(strip=True),
                'apply_link': apply_link
            }
            jobs.append(job_info)
    
    return jobs

# Define a function to scrape a generic IT job site (replace with actual job board URL)
def scrape_generic_jobs():
    jobs = []
    response = requests.get(GENERIC_JOBS_URL)
    response.raise_for_status()  # Ensure the request was successful
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find all job listings based on the structure of the site (adjust class names/tags accordingly)
    job_cards = soup.find_all('div', class_='job-listing')  # Example class
    for job in job_cards:
        title = job.find('h2', class_='job-title')
        company = job.find('div', class_='company-name')
        location = job.find('div', class_='job-location')
        apply_link = job.find('a', href=True)
        
        if title and company and location and apply_link:
            job_info = {
                'title': title.get_text(strip=True),
                'company': company.get_text(strip=True),
                'location': location.get_text(strip=True),
                'apply_link': apply_link['href']
            }
            jobs.append(job_info)
    
    return jobs

# Main function to collect and print job listings from all sources
def get_jobs():
    print("Scraping Indeed jobs...")
    indeed_jobs = scrape_indeed_jobs()
    
    print("Scraping LinkedIn jobs...")
    linkedin_jobs = scrape_linkedin_jobs()
    
    print("Scraping Generic IT jobs...")
    generic_jobs = scrape_generic_jobs()
    
    # Combine all jobs from different sources
    all_jobs = indeed_jobs + linkedin_jobs + generic_jobs
    
    # Display the job listings
    for job in all_jobs:
        print(f"Job Title: {job['title']}")
        print(f"Company: {job['company']}")
        print(f"Location: {job['location']}")
        print(f"Apply Here: {job['apply_link']}")
        print("-" * 40)

# Run the script
if __name__ == "__main__":
    get_jobs()
