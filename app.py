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


# Initialize Flask App
app = Flask(__name__)
CORS(app) # Allows our frontend to talk to our backend

# --- Configure Gemini API ---
try:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set.")
    genai.configure(api_key=api_key)
except ValueError as e:
    print(e)
    # Exit or handle the case where the API key is not set
    # For now, we'll just print and continue, but the API calls will fail.

# --- Helper Functions for Step 2 ---
def get_goodreads_url(title, author):
    """
    Searches for a book and returns the first Goodreads URL found using multiple methods.
    """
    if not title or title == "Unknown":
        return None  # Cannot search without a title

    print(f"Searching for: \"{title}\" by {author}")
    
    # Method 1: Try direct Goodreads search
    url = search_goodreads_direct(title, author)
    if url:
        return url
    
    # Method 2: Try DuckDuckGo search (more reliable than Google)
    url = search_duckduckgo(title, author)
    if url:
        return url
    
    # Method 3: Try Google search as fallback
    url = search_google(title, author)
    if url:
        return url
    
    print(f"  > No Goodreads URL found for '{title}' by {author}")
    return None

def search_goodreads_direct(title, author):
    """
    Search directly on Goodreads website.
    """
    try:
        # Clean the title and author for search
        clean_title = re.sub(r'[^\w\s]', '', title).strip()
        clean_author = re.sub(r'[^\w\s]', '', author).strip() if author and author != "Unknown" else ""
        
        # Create search query
        search_query = clean_title
        if clean_author:
            search_query += f" {clean_author}"
        
        # URL encode the search query
        encoded_query = quote_plus(search_query)
        search_url = f"https://www.goodreads.com/search?q={encoded_query}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for book links in search results
        book_links = soup.find_all('a', href=re.compile(r'/book/show/\d+'))
        
        if book_links:
            # Get the first book link
            book_url = book_links[0]['href']
            if not book_url.startswith('http'):
                book_url = f"https://www.goodreads.com{book_url}"
            print(f"  > Found Goodreads URL (direct search): {book_url}")
            return book_url
            
    except Exception as e:
        print(f"  > Direct Goodreads search failed: {e}")
    
    return None

def search_duckduckgo(title, author):
    """
    Search using DuckDuckGo (more reliable than Google for scraping).
    """
    try:
        # Create search query
        search_query = f'"{title}" "{author}" site:goodreads.com'
        encoded_query = quote_plus(search_query)
        search_url = f"https://duckduckgo.com/html/?q={encoded_query}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for Goodreads links in search results
        for link in soup.find_all('a'):
            href = link.get('href')
            if href and 'goodreads.com/book/show' in href:
                # DuckDuckGo uses redirect URLs, extract the actual URL
                if href.startswith('/l/?uddg='):
                    # Extract the actual URL from DuckDuckGo's redirect
                    actual_url = href.split('/l/?uddg=')[1]
                    if actual_url:
                        print(f"  > Found Goodreads URL (DuckDuckGo): {actual_url}")
                        return actual_url
                elif href.startswith('https://www.goodreads.com'):
                    print(f"  > Found Goodreads URL (DuckDuckGo): {href}")
                    return href
                    
    except Exception as e:
        print(f"  > DuckDuckGo search failed: {e}")
    
    return None

def search_google(title, author):
    """
    Search using Google as a fallback method.
    """
    try:
        # Create search query
        search_query = f'"{title}" "{author}" site:goodreads.com'
        encoded_query = quote_plus(search_query)
        search_url = f"https://www.google.com/search?q={encoded_query}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for Google's redirect URLs containing Goodreads links
        for link in soup.find_all('a'):
            href = link.get('href')
            if href and href.startswith('/url?q=https://www.goodreads.com/book/show'):
                # Extract the actual URL from Google's redirect
                parsed_url = urlparse(href)
                actual_url = parse_qs(parsed_url.query).get('q', [None])[0]
                if actual_url:
                    print(f"  > Found Goodreads URL (Google): {actual_url}")
                    return actual_url
                    
    except Exception as e:
        print(f"  > Google search failed: {e}")
    
    return None

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
        model = genai.GenerativeModel('gemini-1.5-flash') # Using the fast model
        
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
        
        # Be a good citizen and don't spam the search engines
        time.sleep(random.randint(2, 4)) 
    
    return jsonify(books_with_urls)


if __name__ == '__main__':
    # Make sure to set the host to '0.0.0.0' to make it accessible
    # on your local network if you want to test from your phone.
    app.run(debug=True, host='0.0.0.0')