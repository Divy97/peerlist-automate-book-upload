import os
import json
import time
import random
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import google.generativeai as genai
from PIL import Image
from urllib.parse import urlparse, parse_qs, quote_plus
import re
import cloudscraper
from peerlist_selenium import PeerlistSelenium
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize Flask App
app = Flask(__name__)
CORS(app) 

# --- Configure Google API ---
try:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set.")
    genai.configure(api_key=api_key)
except ValueError as e:
    print(e)
    exit(1)

# --- Peerlist Configuration ---
PEERLIST_AUTHORIZATION = os.getenv("PEERLIST_AUTHORIZATION")
PEERLIST_COLLECTION_ID = os.getenv("PEERLIST_COLLECTION_ID")
PEERLIST_COOKIES = os.getenv("PEERLIST_COOKIES")
PEERLIST_USERNAME = os.getenv("PEERLIST_USERNAME")

# Network Configuration (Optional - will be auto-detected if not set)
PEERLIST_IPV4 = os.getenv("PEERLIST_IPV4")
PEERLIST_IPV6 = os.getenv("PEERLIST_IPV6")

# Auto-detect IP addresses if not provided
def get_public_ip():
    """Get public IP address if not set in environment."""
    try:
        response = requests.get('https://api.ipify.org?format=json', timeout=5)
        return response.json().get('ip')
    except:
        return None

if not PEERLIST_IPV4:
    detected_ip = get_public_ip()
    if detected_ip:
        PEERLIST_IPV4 = detected_ip
        print(f"Auto-detected IPv4: {PEERLIST_IPV4}")

# Validate required environment variables
if not PEERLIST_AUTHORIZATION:
    print("Warning: PEERLIST_AUTHORIZATION environment variable not set.")
if not PEERLIST_COLLECTION_ID:
    print("Warning: PEERLIST_COLLECTION_ID environment variable not set.")
if not PEERLIST_COOKIES:
    print("Warning: PEERLIST_COOKIES environment variable not set.")
if not PEERLIST_USERNAME:
    print("Warning: PEERLIST_USERNAME environment variable not set.")

# Initialize Cloudscraper session
scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'linux',
        'desktop': True
    }
)

# Initialize Selenium Peerlist client
peerlist_selenium = None

def get_peerlist_selenium():
    """Get or create the Selenium Peerlist client."""
    global peerlist_selenium
    if peerlist_selenium is None:
        peerlist_selenium = PeerlistSelenium()
        # Login to Peerlist
        if not peerlist_selenium.login_to_peerlist(PEERLIST_COOKIES):
            print("❌ Failed to login to Peerlist with Selenium")
            return None
    return peerlist_selenium

def parse_cookies(cookie_string):
    """
    Parse cookie string into a dictionary, handling cookies with values containing '='.
    """
    cookies = {}
    if not cookie_string:
        return cookies
    
    # Split by '; ' to get individual cookies
    cookie_pairs = cookie_string.split('; ')
    
    for pair in cookie_pairs:
        if '=' in pair:
            # Find the first '=' to separate name from value
            first_equals = pair.find('=')
            name = pair[:first_equals]
            value = pair[first_equals + 1:]
            
            # Skip empty names
            if name:
                cookies[name] = value
    
    return cookies

def search_goodreads_direct_simple(title, author):
    """
    Direct Goodreads search as fallback when Google/DuckDuckGo fail.
    """
    try:
        # Create search query
        if author and author != "Unknown":
            search_query = f'"{title}" by {author} Goodreads'
        else:
            search_query = f'"{title}" Goodreads'
        
        encoded_query = quote_plus(search_query)
        search_url = f"https://www.goodreads.com/search?q={encoded_query}"
        
        print(f"    > Searching Goodreads directly: {search_url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        response = requests.get(search_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for book links in search results
        for link in soup.find_all('a', href=re.compile(r'/book/show/\d+')):
            href = link.get('href')
            if href:
                if not href.startswith('http'):
                    href = f"https://www.goodreads.com{href}"
                
                print(f"    > Found Goodreads URL (direct): {href}")
                return href
        
        print(f"    > No book links found on Goodreads search page")
        
    except Exception as e:
        print(f"    > Direct Goodreads search failed: {e}")
    
    return None

def search_google_simple(title, author):
    """
    Simple Google search: "title by author goodreads" and get first Goodreads link.
    """
    try:
        # Create search query in the exact format that works: "title" by author goodreads
        if author and author != "Unknown":
            search_query = f'"{title}" by {author} goodreads'
        else:
            search_query = f'"{title}" goodreads'
        
        encoded_query = quote_plus(search_query)
        search_url = f"https://www.google.com/search?q={encoded_query}&ie=UTF-8"
        
        print(f"    > Searching Google: {search_url}")
        
        # Use more realistic browser headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }
        
        # Add a small delay to avoid rate limiting
        time.sleep(1)
        
        response = requests.get(search_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Check if we got blocked
        if 'enablejs' in response.text or 'support.google.com' in response.text:
            print(f"    > Google blocked the request, trying alternative method...")
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for Google's redirect URLs containing Goodreads links
        found_links = []
        for link in soup.find_all('a'):
            href = link.get('href')
            if href and 'goodreads.com/book/show' in href:
                found_links.append(href)
                print(f"    > Found Goodreads link: {href}")
                
                if href.startswith('/url?q=https://www.goodreads.com/book/show'):
                    # Extract the actual URL from Google's redirect
                    parsed_url = urlparse(href)
                    actual_url = parse_qs(parsed_url.query).get('q', [None])[0]
                    if actual_url:
                        print(f"    > Extracted URL: {actual_url}")
                        return actual_url
                elif href.startswith('https://www.goodreads.com/book/show'):
                    print(f"    > Direct Goodreads URL: {href}")
                    return href
        
        if not found_links:
            print(f"    > No Goodreads links found in Google results")
            # Print first few links to debug
            all_links = soup.find_all('a', href=True)
            print(f"    > First 5 links found:")
            for i, link in enumerate(all_links[:5]):
                print(f"      {i+1}. {link.get('href')}")
                    
    except Exception as e:
        print(f"    > Google search failed: {e}")
    
    return None

def search_duckduckgo_simple(title, author):
    """
    Simple DuckDuckGo search: "title by author goodreads" and get first Goodreads link.
    """
    try:
        # Create search query in the exact format that works: "title" by author goodreads
        if author and author != "Unknown":
            search_query = f'"{title}" by {author} goodreads'
        else:
            search_query = f'"{title}" goodreads'
        
        encoded_query = quote_plus(search_query)
        search_url = f"https://duckduckgo.com/html/?q={encoded_query}"
        
        print(f"    > Searching DuckDuckGo: {search_url}")
        
        # Use more realistic browser headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
        }
        
        # Add a small delay to avoid rate limiting
        time.sleep(1)
        
        response = requests.get(search_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for Goodreads links in search results
        found_links = []
        for link in soup.find_all('a'):
            href = link.get('href')
            if href and 'goodreads.com/book/show' in href:
                found_links.append(href)
                print(f"    > Found Goodreads link: {href}")
                
                # DuckDuckGo uses redirect URLs, extract the actual URL
                if href.startswith('/l/?uddg='):
                    # Extract the actual URL from DuckDuckGo's redirect
                    actual_url = href.split('/l/?uddg=')[1]
                    if actual_url:
                        print(f"    > Extracted URL: {actual_url}")
                        return actual_url
                elif href.startswith('https://www.goodreads.com'):
                    print(f"    > Direct Goodreads URL: {href}")
                    return href
        
        if not found_links:
            print(f"    > No Goodreads links found in DuckDuckGo results")
            # Print first few links to debug
            all_links = soup.find_all('a', href=True)
            print(f"    > First 5 links found:")
            for i, link in enumerate(all_links[:5]):
                print(f"      {i+1}. {link.get('href')}")
                    
    except Exception as e:
        print(f"    > DuckDuckGo search failed: {e}")
    
    return None

def get_goodreads_url(title, author):
    """
    Simple and reliable method: search for "book title goodreads" and get the first result.
    """
    if not title or title == "Unknown":
        return None  # Cannot search without a title

    print(f"Searching for: \"{title}\" by {author}")
    
    # Method 1: Try Google search for "title goodreads"
    url = search_google_simple(title, author)
    if url:
        return url
    
    # Method 2: Try DuckDuckGo as fallback
    url = search_duckduckgo_simple(title, author)
    if url:
        return url
    
    # Method 3: Try direct Goodreads search as last resort
    url = search_goodreads_direct_simple(title, author)
    if url:
        return url
    
    print(f"  > No Goodreads URL found for '{title}' by {author}")
    return None


def get_book_metadata_from_goodreads(goodreads_url):
    """
    Fallback method to get book metadata directly from Goodreads.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        
        response = requests.get(goodreads_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract title
        title_elem = soup.find('h1', {'id': 'bookTitle'})
        title = title_elem.get_text().strip() if title_elem else None
        
        # Extract author
        author_elem = soup.find('a', {'class': 'authorName'})
        author = author_elem.get_text().strip() if author_elem else None
        
        # Extract image
        image_elem = soup.find('img', {'id': 'coverImage'})
        image_url = image_elem.get('src') if image_elem else None
        
        # Extract description
        desc_elem = soup.find('div', {'id': 'description'})
        description = desc_elem.get_text().strip() if desc_elem else None
        
        if title:
            metadata = {
                'title': title,
                'author': author,
                'image': image_url,
                'description': description,
                'url': goodreads_url
            }
            print(f"    > Extracted metadata from Goodreads: {title}")
            return metadata
        
        return None
        
    except Exception as e:
        print(f"    > Error extracting from Goodreads: {e}")
        return None

def get_peerlist_metadata(goodreads_url):
    """
    Get book metadata from Peerlist API using Selenium to bypass Cloudflare.
    """
    try:
        # Get the Selenium client
        selenium_client = get_peerlist_selenium()
        if not selenium_client:
            print("❌ Selenium client not available")
            return None
        
        # Use Selenium to get metadata
        metadata = selenium_client.get_book_metadata(goodreads_url)
        
        # If Peerlist fails, try direct Goodreads extraction
        if not metadata:
            print("    > Peerlist API failed, trying direct Goodreads extraction...")
            metadata = get_book_metadata_from_goodreads(goodreads_url)
        
        return metadata
            
    except Exception as e:
        print(f"Error getting Peerlist metadata for {goodreads_url}: {e}")
        # Try direct Goodreads extraction as fallback
        return get_book_metadata_from_goodreads(goodreads_url)

def add_book_to_peerlist_collection(book_data):
    """
    Add a book to the Peerlist collection using Selenium.
    """
    try:
        # Get the Selenium client
        selenium_client = get_peerlist_selenium()
        if not selenium_client:
            print("❌ Selenium client not available")
            return False, None
        
        # Use Selenium to add book to collection
        success = selenium_client.add_book_to_collection(book_data, PEERLIST_COLLECTION_ID)
        if success:
            return True, "added_via_selenium"
        else:
            return False, None
            
    except Exception as e:
        print(f"Error adding book to Peerlist: {e}")
        return False, None

# === API ENDPOINTS ===

@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('index.html')

@app.route('/extract_books', methods=['POST'])
def extract_books_from_image():
    """
    STEP 1: Receives an image, uses Gemini to extract book titles and authors,
    and returns them as JSON.
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    try:
        image = Image.open(file.stream)
        model = genai.GenerativeModel('gemini-1.5-flash') 
        
        prompt = """
        Analyze this image of a bookshelf. Identify each book. For each one, extract its title and author.
        Return the result ONLY as a valid JSON array of objects. Each object must have a "title" and "author" key.
        If a title or author is unreadable or not visible, use the string "Unknown".
        Do not include any text or markdown formatting before or after the JSON array.
        Example: [{"title": "Shoe Dog", "author": "Phil Knight"}, {"title": "The Silent Patient", "author": "Alex Michaelides"}]
        """

        response = model.generate_content([prompt, image])
        
        # Clean up the response to get pure JSON
        cleaned_text = response.text.strip().replace("```json", "").replace("```", "")
        books = json.loads(cleaned_text)
        
        return jsonify(books)

    except Exception as e:
        print(f"An error occurred during extraction: {e}")
        return jsonify({"error": str(e)}), 500



@app.route('/find_urls', methods=['POST'])
def find_goodreads_urls():
    """
    STEP 2: Receives a JSON list of books and finds the Goodreads URL for each one.
    """
    books = request.get_json()
    if not books:
        return jsonify({"error": "No book data provided"}), 400

    books_with_urls = []
    for book in books:
        # This function calls our HELPER function below
        url = get_goodreads_url(book.get('title'), book.get('author'))
        
        updated_book = {
            "title": book.get('title', 'Unknown'),
            "author": book.get('author', 'Unknown'),
            "goodreads_url": url or "Not Found"
        }
        books_with_urls.append(updated_book)
        
        time.sleep(random.randint(2, 4)) 
    
    return jsonify(books_with_urls)

@app.route('/add_to_peerlist', methods=['POST'])
def add_to_peerlist():
    """
    STEP 3: Adds books to Peerlist collection using Selenium.
    """
    books = request.get_json()
    if not books:
        return jsonify({"error": "No book data provided"}), 400

    added_count = 0
    failed_books = []

    for book in books:
        if not book.get('goodreads_url') or book.get('goodreads_url') == 'Not Found':
            continue

        print(f"Processing book for Peerlist: {book['title']} by {book['author']}")
        
        # Get metadata from Peerlist API using Selenium
        metadata = get_peerlist_metadata(book['goodreads_url'])
        if not metadata:
            print(f"Failed to get metadata for {book['title']}")
            failed_books.append(book['title'])
            continue

        # Prepare book data for Peerlist
        book_data = {
            'title': metadata.get('title', book['title']),
            'author': metadata.get('author', [book['author']])[0] if isinstance(metadata.get('author'), list) else metadata.get('author', book['author']),
            'image': metadata.get('image', ''),
            'description': metadata.get('description', ''),
            'url': book['goodreads_url']
        }

        # Add to Peerlist collection using Selenium
        success, item_id = add_book_to_peerlist_collection(book_data)
        if success:
            added_count += 1
            print(f"Successfully added {book['title']} to Peerlist (ID: {item_id})")
        else:
            failed_books.append(book['title'])
            print(f"Failed to add {book['title']} to Peerlist")

        # Be respectful with API calls
        time.sleep(1)

    return jsonify({
        "success": True,
        "added_count": added_count,
        "total_books": len(books),
        "failed_books": failed_books
    })

@app.route('/test_selenium', methods=['GET'])
def test_selenium():
    """
    Test endpoint to verify Selenium setup is working.
    """
    try:
        selenium_client = get_peerlist_selenium()
        if selenium_client:
            return jsonify({
                "success": True,
                "message": "Selenium setup is working correctly",
                "status": "ready"
            })
        else:
            return jsonify({
                "success": False,
                "message": "Failed to initialize Selenium client",
                "status": "error"
            })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error testing Selenium: {str(e)}",
            "status": "error"
        })

if __name__ == '__main__':
    # Make sure to set the host to '0.0.0.0' to make it accessible
    # on your local network if you want to test from your phone.
    app.run(debug=True, host='0.0.0.0')