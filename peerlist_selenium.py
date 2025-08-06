#!/usr/bin/env python3
"""
Selenium-based Peerlist integration to handle Cloudflare challenges.
This uses a real browser to bypass Cloudflare protection.
"""

import time
import json
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get configuration from environment variables
PEERLIST_AUTHORIZATION = os.getenv("PEERLIST_AUTHORIZATION")
PEERLIST_USERNAME = os.getenv("PEERLIST_USERNAME")
PEERLIST_IPV4 = os.getenv("PEERLIST_IPV4")
PEERLIST_IPV6 = os.getenv("PEERLIST_IPV6")

class PeerlistSelenium:
    def __init__(self):
        self.driver = None
        self.setup_driver()
    
    def setup_driver(self):
        """Setup Chrome driver with appropriate options."""
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36")
        
        # Add cookies and headers
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Execute script to remove webdriver property
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    def login_to_peerlist(self, cookies_string):
        """Login to Peerlist using cookies."""
        try:
            # First visit the main site
            self.driver.get("https://peerlist.io")
            time.sleep(3)
            
            # Parse and set cookies
            cookies = self.parse_cookies(cookies_string)
            for name, value in cookies.items():
                try:
                    self.driver.add_cookie({
                        'name': name,
                        'value': value,
                        'domain': '.peerlist.io'
                    })
                except Exception as e:
                    print(f"Could not set cookie {name}: {e}")
            
            # Refresh to apply cookies
            self.driver.refresh()
            time.sleep(30)
            
            print("✅ Successfully logged into Peerlist")
            return True
            
        except Exception as e:
            print(f"❌ Failed to login to Peerlist: {e}")
            return False
    
    def parse_cookies(self, cookie_string):
        """Parse cookie string into dictionary."""
        cookies = {}
        if not cookie_string:
            return cookies
        
        cookie_pairs = cookie_string.split('; ')
        for pair in cookie_pairs:
            if '=' in pair:
                first_equals = pair.find('=')
                name = pair[:first_equals]
                value = pair[first_equals + 1:]
                if name:
                    cookies[name] = value
        
        return cookies
    
    def get_book_metadata(self, goodreads_url):
        """Get book metadata using Selenium to bypass Cloudflare."""
        try:
            # Check if authorization is available
            if not PEERLIST_AUTHORIZATION:
                print("    > PEERLIST_AUTHORIZATION not set in environment variables")
                return None
            
            # Construct the API URL
            api_url = f"https://peerlist.io/api/v1/service/getMetaDetails?url={quote_plus(goodreads_url)}"
            
            print(f"    > Accessing: {api_url}")
            
            # Set up the request with proper headers
            # First navigate to Peerlist to establish session
            if PEERLIST_USERNAME:
                self.driver.get(f"https://peerlist.io/{PEERLIST_USERNAME}/collections")
            else:
                self.driver.get("https://peerlist.io")
            time.sleep(3)
            
            # Now make the API request with proper headers
            # We'll use JavaScript to make the request with the correct headers
            script = f"""
            return fetch('{api_url}', {{
                method: 'GET',
                headers: {{
                    'accept': 'application/json, text/plain, */*',
                    'accept-language': 'en-US,en;q=0.6',
                    'authorization': '{PEERLIST_AUTHORIZATION}',
                    'priority': 'u=1, i',
                    'referer': f'https://peerlist.io/{PEERLIST_USERNAME}/collections' if PEERLIST_USERNAME else 'https://peerlist.io',
                    'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Brave";v="138"',
                    'sec-ch-ua-mobile': '?0',
                    'sec-ch-ua-platform': '"Linux"',
                    'sec-fetch-dest': 'empty',
                    'sec-fetch-mode': 'cors',
                    'sec-fetch-site': 'same-origin',
                    'sec-gpc': '1',
                    'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
                    'x-pl-ip': '{PEERLIST_IPV4}' if PEERLIST_IPV4 else '',
                    'x-real-ip': '{PEERLIST_IPV6}' if PEERLIST_IPV6 else ''
                }},
                credentials: 'include'
            }})
            .then(response => response.text())
            .then(data => data)
            .catch(error => error.toString());
            """
            
            # Execute the JavaScript request
            result = self.driver.execute_script(script)
            
            if result and isinstance(result, str):
                try:
                    data = json.loads(result)
                    if data.get('success'):
                        metadata = data.get('data', {})
                        print(f"    > Successfully got metadata: {metadata}")
                        return metadata
                    else:
                        print(f"    > API returned success=false: {data}")
                        return None
                except json.JSONDecodeError as e:
                    print(f"    > Failed to parse JSON response: {e}")
                    print(f"    > Raw response: {result[:200]}...")
                    return None
            else:
                print(f"    > No response from fetch request")
                return None
            
        except Exception as e:
            print(f"    > Error getting metadata: {e}")
            return None
    
    def add_book_to_collection(self, book_data, collection_id):
        """Add a book to the Peerlist collection using the API."""
        try:
            # Check if authorization is available
            if not PEERLIST_AUTHORIZATION:
                print("    > PEERLIST_AUTHORIZATION not set in environment variables")
                return False, None
            
            # Prepare the request data
            request_data = {
                "data": {
                    "collectionId": collection_id,
                    "item": {
                        "author": book_data.get('author', 'Unknown'),
                        "type": "BOOKS",
                        "image": book_data.get('image', ''),
                        "title": book_data.get('title', 'Unknown'),
                        "description": book_data.get('description', ''),
                        "url": book_data.get('url', '')
                    },
                    "postOnScroll": False
                }
            }
            
            # Convert to JSON string
            json_data = json.dumps(request_data)
            
            print(f"    > Adding book to collection: {book_data.get('title', 'Unknown')}")
            
            # Use JavaScript to make the POST request with proper headers
            script = f"""
            return fetch('https://peerlist.io/api/v1/users/collections/addItem', {{
                method: 'POST',
                headers: {{
                    'accept': 'application/json, text/plain, */*',
                    'accept-language': 'en-US,en;q=0.6',
                    'authorization': '{PEERLIST_AUTHORIZATION}',
                    'content-type': 'application/json',
                    'origin': 'https://peerlist.io',
                    'priority': 'u=1, i',
                    'referer': f'https://peerlist.io/{PEERLIST_USERNAME}/collections' if PEERLIST_USERNAME else 'https://peerlist.io',
                    'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Brave";v="138"',
                    'sec-ch-ua-mobile': '?0',
                    'sec-ch-ua-platform': '"Linux"',
                    'sec-fetch-dest': 'empty',
                    'sec-fetch-mode': 'cors',
                    'sec-fetch-site': 'same-origin',
                    'sec-gpc': '1',
                    'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
                    'x-pl-ip': '{PEERLIST_IPV4}' if PEERLIST_IPV4 else '',
                    'x-real-ip': '{PEERLIST_IPV6}' if PEERLIST_IPV6 else ''
                }},
                body: '{json_data}',
                credentials: 'include'
            }})
            .then(response => response.text())
            .then(data => data)
            .catch(error => error.toString());
            """
            
            # Execute the JavaScript request
            result = self.driver.execute_script(script)
            
            if result and isinstance(result, str):
                try:
                    data = json.loads(result)
                    if data.get('success'):
                        item_id = data.get('itemId')
                        print(f"    > Successfully added book to collection (ID: {item_id})")
                        return True, item_id
                    else:
                        print(f"    > Failed to add book: {data}")
                        return False, None
                except json.JSONDecodeError as e:
                    print(f"    > Failed to parse response: {e}")
                    print(f"    > Raw response: {result[:200]}...")
                    return False, None
            else:
                print(f"    > No response from addItem request")
                return False, None
            
        except Exception as e:
            print(f"    > Error adding book to collection: {e}")
            return False, None
    
    def close(self):
        """Close the browser."""
        if self.driver:
            self.driver.quit()

