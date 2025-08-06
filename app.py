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

# --- Helper Function for Step 2 ---
def get_goodreads_url(title, author):
    """Searches for a book and returns the first Goodreads URL found."""
    if not title or title == "Unknown":
        return None # Cannot search without a title

    query = f"{title} {author} site:goodreads.com"
    search_url = f"https://www.google.com/search?q={query}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(search_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for link in soup.find_all('a'):
            href = link.get('href')
            if href and 'goodreads.com/book/show' in href:
                if href.startswith('/url?q='):
                    return href.split('/url?q=')[1].split('&sa=')[0]
        return None
    except requests.exceptions.RequestException as e:
        print(f"Request failed for '{title}': {e}")
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


# @app.route('/find_urls', methods=['POST'])

if __name__ == '__main__':
    # Make sure to set the host to '0.0.0.0' to make it accessible
    # on your local network if you want to test from your phone.
    app.run(debug=True, host='0.0.0.0')