import requests
from bs4 import BeautifulSoup

def scrape_jobs(query, location=None, num_results=5):
    try:
        # Sample Indeed URL for job search (replace with real URLs)
        base_url = "https://www.indeed.com/jobs"
        params = {'q': query, 'l': location} if location else {'q': query}
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        
        # Make the request to Indeed
        response = requests.get(base_url, params=params, headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Parse the job listings
        job_listings = soup.find_all('div', class_='jobsearch-SerpJobCard')
        jobs = []
        
        for job in job_listings[:num_results]:
            title = job.find('a', class_='jobtitle').text.strip()
            company = job.find('span', class_='company').text.strip() if job.find('span', class_='company') else "N/A"
            location = job.find('div', class_='location').text.strip() if job.find('div', class_='location') else "N/A"
            job_url = 'https://www.indeed.com' + job.find('a', class_='jobtitle')['href']
            
            # Collect job data
            jobs.append({
                'title': title,
                'company': company,
                'location': location,
                'url': job_url
            })
        
        return jobs
    except Exception as e:
        print(f"Error scraping jobs: {e}")
        return []

# Test the function with a job query
jobs = scrape_jobs("Python Developer", "New York")
for job in jobs:
    print(f"Title: {job['title']}")
    print(f"Company: {job['company']}")
    print(f"Location: {job['location']}")
    print(f"Apply: {job['url']}")
