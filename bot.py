import requests
from bs4 import BeautifulSoup

# Define the URL to scrape
IT_JOBS_URL = "https://www.indeed.com/jobs?q=developer&l="

# Define a function to scrape Indeed job listings
def scrape_indeed_jobs():
    jobs = []
    
    # Set custom headers to mimic a browser (avoid 403 Forbidden error)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # Send a GET request with custom headers
        response = requests.get(IT_JOBS_URL, headers=headers)
        
        # Check for successful request
        response.raise_for_status()
        
        # Parse the response HTML using BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all the job cards on the page (inspect the page for correct HTML structure)
        job_cards = soup.find_all('div', class_='jobsearch-SerpJobCard')  # This class is specific to Indeed, adjust as needed
        
        # Loop through job cards and extract relevant details
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
    
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error occurred: {e}")
    except requests.exceptions.RequestException as e:
        print(f"Request Exception occurred: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
    
    return jobs

# Test the function to check if it works
if __name__ == "__main__":
    try:
        # Scrape Indeed job listings
        indeed_jobs = scrape_indeed_jobs()
        
        # Display the job listings
        for job in indeed_jobs:
            print(f"Job Title: {job['title']}")
            print(f"Company: {job['company']}")
            print(f"Location: {job['location']}")
            print(f"Apply Here: {job['apply_link']}")
            print("-" * 40)
    
    except Exception as e:
        print(f"Error: {e}")
