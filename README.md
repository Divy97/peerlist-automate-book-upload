# Bookshelf photo to Peerlist Book collection

A simple web app that scans a picture of your bookshelf, uses AI to identify the books, and adds them to your Books collection on Peerlist.io.

## Features

* **Scan Books**: Upload an image of your bookshelf.
* **AI Identification**: Uses Google Gemini to extract book titles and authors.
* **Automated Adding**: Automatically finds the books on Goodreads and adds them to a specified Peerlist collection.

## Setup Instructions

Follow these steps to get the project running on your local machine.

### Step 1: Clone the Project

First, clone this repository to your computer.

```bash
git clone https://github.com/Divy97/peerlist-automate-book-upload.git
cd peerlist-automate-book-upload
```

### Step 2: Set up a Virtual Environment

It's a good practice to use a virtual environment to keep project dependencies separate.

For macOS/Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

For Windows:
```bash
python -m venv venv
.\venv\Scripts\activate
```

### Step 3: Install Dependencies

Install all the required Python packages using the requirements.txt file.

```bash
pip install -r requirements.txt
```

### Step 4: Configure Your Credentials

You need to provide your own API keys and credentials for the script to work.

1. Make a copy of the example environment file.

```bash
cp env.example .env
```

2. Open the .env file in a text editor and fill in your values.

**How to get your credentials:**

- **GOOGLE_API_KEY:**
  - Go to Google AI Studio.
  - Click "Create API key" and copy the key.

- **PEERLIST_USERNAME:**
  - This is just your username from your Peerlist profile URL (e.g., https://peerlist.io/sydney-sweeney).

- **PEERLIST_COLLECTION_ID:**
  - Go to the specific collection on Peerlist where you want to add the books.
  - The ID is in the URL: https://peerlist.io/your-username/collections/THE_ID_IS_HERE.

- **PEERLIST_AUTHORIZATION and PEERLIST_COOKIES:**
  - Log in to your Peerlist.io account in your browser.
  - Open the Developer Tools (F12 or Right Click -> Inspect).
  - Go to the Network tab.
  - Refresh the page to see the network requests.
  - Click on any request to the Peerlist API (look for names like feed, user, etc.).
  - In the Request Headers section, find and copy the following:
    - **authorization:** Copy the entire value, including the word Bearer.
    - **cookie:** Copy the entire long string of text.

> **Warning:** Your Authorization Token and Cookies are sensitive. Treat them like your partner and do not share them with anyone.

## How to Run the App

Make sure your virtual environment is activated.

Run the app.py script from your terminal.

```bash
python app.py
```

Open your web browser and go to: http://127.0.0.1:5000

You should now see the web interface where you can upload an image and start scanning!

