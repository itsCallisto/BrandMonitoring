import sqlite3
import time
from datetime import datetime
import json
import pandas as pd
import requests
import streamlit as st
import google.genai as genai
import os
import sys
from dotenv import load_dotenv
if os.path.exists(".env"):

    load_dotenv()  







if sys.platform.startswith("win"):
    
    DB_NAME = "brand_monitor.db"
else:
    
    DB_NAME = "/tmp/brand_monitor.db"
    
    
















API_KEY = None

try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    API_KEY = os.getenv("GEMINI_API_KEY")


if not API_KEY:
    st.error("❌ GEMINI_API_KEY not found in Streamlit secrets")
    st.stop()
@st.cache_resource
def get_gemini_client():
    return genai.Client(api_key=API_KEY)









def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mentions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                brand TEXT NOT NULL,
                source TEXT NOT NULL,
                text TEXT NOT NULL,
                url TEXT UNIQUE,
                timestamp DATETIME,
                sentiment TEXT,
                topic TEXT,
                urgency TEXT
            )
        """)


if "db_initialized" not in st.session_state:
    init_db()
    st.session_state.db_initialized = True




def add_mention(brand_name, source, text, url, timestamp):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM mentions WHERE url=?", (url,))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO mentions (brand, source, text, url, timestamp) VALUES (?, ?, ?, ?, ?)",
                (brand_name, source, text, url, timestamp),
            )
            conn.commit()
            return True
    return False


def get_all_mentions_as_df(brand_name):
    with sqlite3.connect(DB_NAME) as conn:
        df = pd.read_sql_query(
            "SELECT * FROM mentions WHERE brand=? ORDER BY timestamp DESC",
            conn,
            params=(brand_name,),
        )
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df





# def fetch_reddit_mentions(brand_name, subreddits_list):
#     added_count = 0
#     processed_urls = set()

#     existing_df = get_all_mentions_as_df(brand_name)
#     existing_urls = set(existing_df["url"].tolist())

#     headers = {"User-Agent": "Mozilla/5.0 (BrandMonitorProject)"}
#     # headers = {
#     #     "User-Agent": "BrandMonitoringBot/1.0 by Ashutosh Singh"
#     # }

#     for sub_name in subreddits_list:
#         sub_name = sub_name.strip()
#         if not sub_name:
#             continue

#         try:
           
#             url = f"https://www.reddit.com/r/{sub_name}/search.json"
#             # url = f"https://www.reddit.com/r/{sub_name}/new"

#             params = {"q": brand_name, "restrict_sr": 1, "sort": "new", "limit": 10}
#             # params = {"limit": 25}

#             response = requests.get(url, headers=headers, params=params, timeout=20)
#             response.raise_for_status()

#             data = response.json()
#             posts = data.get("data", {}).get("children", [])
#             # DEBUG START
           



#             response.raise_for_status()

#             data = response.json()

#             st.write("DEBUG: JSON keys:", list(data.keys()))

#             posts = data.get("data", {}).get("children", [])

            
#             st.info(f"Found {len(posts)} posts in r/{sub_name}")

#             for item in posts:
#                 post = item.get("data", {})
#                 if not isinstance(post, dict):
#                     continue

#                 permalink = post.get("permalink")
#                 if not permalink:
#                     continue

#                 post_url = f"https://www.reddit.com{permalink}"

#                 if post_url in existing_urls or post_url in processed_urls:
#                     continue

#                 text = f"{post.get('title', '')} {post.get('selftext', '')}"
#                 timestamp = datetime.fromtimestamp(
#                     post.get("created_utc", datetime.now().timestamp())
#                 )

#                 if add_mention(
#                     brand_name, "Reddit (Public JSON)", text, post_url, timestamp
#                 ):
#                     added_count += 1
#                     processed_urls.add(post_url)

#             time.sleep(1)  

#         except Exception as e:
#             # st.error(f"Could not fetch from r/{sub_name}: {e}")
#             st.error(f"Reddit fetch failed for r/{sub_name}")
#             st.error(str(e))
#             import traceback
#             st.error(traceback.format_exc())

#     return added_count


# def fetch_reddit_mentions(brand_name, subreddits_list):

#     added_count = 0
#     processed_urls = set()

#     existing_df = get_all_mentions_as_df(brand_name)
#     existing_urls = set(existing_df["url"].tolist())

#     # Use Session (VERY IMPORTANT for Streamlit Cloud)
#     session = requests.Session()

#     session.headers.update({
#         "User-Agent": "BrandMonitoringBot/1.0 by Ashutosh Singh",
#         "Accept": "application/json"
#     })

#     for sub_name in subreddits_list:

#         sub_name = sub_name.strip()

#         if not sub_name:
#             continue

#         try:

#             url = f"https://api.reddit.com/r/{sub_name}/new"

            

#             response = session.get(url, timeout=20)

            

#             if response.status_code != 200:
#                 st.error(f"Reddit blocked request: {response.status_code}")
#                 continue

#             data = response.json()

#             posts = data.get("data", {}).get("children", [])

#             # st.info(f"Fetched {len(posts)} posts from r/{sub_name}")

#             for item in posts:

#                 post = item.get("data", {})

#                 title = post.get("title", "")
#                 body = post.get("selftext", "")
#                 # st.write("Post title:", title)


#                 text = f"{title} {body}"

#                 # Filter by brand name
#                 if brand_name.lower() not in text.lower():
#                     continue

#                 permalink = post.get("permalink")

#                 if not permalink:
#                     continue

#                 post_url = f"https://www.reddit.com{permalink}"

#                 # Skip duplicates
#                 if post_url in existing_urls or post_url in processed_urls:
#                     continue

#                 timestamp = datetime.fromtimestamp(
#                     post.get("created_utc", time.time())
#                 )

#                 if add_mention(
#                     brand_name,
#                     "Reddit",
#                     text,
#                     post_url,
#                     timestamp
#                 ):
#                     added_count += 1
#                     processed_urls.add(post_url)

#             # Prevent Reddit rate limit
#             time.sleep(2)

#         except Exception as e:

#             st.error(f"Reddit fetch failed for r/{sub_name}")
#             st.error(str(e))

#     return added_count




# def fetch_reddit_mentions(brand_name, subreddits_list):

#     added_count = 0
#     processed_urls = set()

#     existing_df = get_all_mentions_as_df(brand_name)
#     existing_urls = set(existing_df["url"].tolist())

#     session = requests.Session()

#     # VERY IMPORTANT: full browser-like headers
#     session.headers.update({
#         "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
#         "Accept": "application/json",
#         "Accept-Language": "en-US,en;q=0.9",
#         "Connection": "keep-alive"
#     })

#     for sub_name in subreddits_list:

#         sub_name = sub_name.strip()

#         if not sub_name:
#             continue

#         try:
#             # use .json endpoint (LESS blocking)
#             url = f"https://old.reddit.com/r/{sub_name}/new.json"

#             params = {
#                 "limit": 25,
#                 "raw_json": 1
#             }

#             response = session.get(
#                 url,
#                 params=params,
#                 timeout=20
#             )

#             # DEBUG info
#             print(f"Status for r/{sub_name}: {response.status_code}")

#             if response.status_code == 429:
#                 st.warning("Rate limited by Reddit. Waiting 5 seconds...")
#                 time.sleep(5)
#                 continue

#             if response.status_code != 200:
#                 st.warning(f"Reddit blocked r/{sub_name}: {response.status_code}")
#                 continue

#             data = response.json()

#             posts = data.get("data", {}).get("children", [])

#             for item in posts:

#                 post = item.get("data", {})

#                 title = post.get("title", "")
#                 body = post.get("selftext", "")

#                 text = f"{title} {body}"

#                 if brand_name.lower() not in text.lower():
#                     continue

#                 permalink = post.get("permalink")

#                 if not permalink:
#                     continue

#                 post_url = f"https://www.reddit.com{permalink}"

#                 if post_url in existing_urls or post_url in processed_urls:
#                     continue

#                 timestamp = datetime.fromtimestamp(
#                     post.get("created_utc", time.time())
#                 )

#                 if add_mention(
#                     brand_name,
#                     "Reddit",
#                     text,
#                     post_url,
#                     timestamp
#                 ):
#                     added_count += 1
#                     processed_urls.add(post_url)

#             # VERY IMPORTANT: delay
#             time.sleep(3)

#         except Exception as e:

#             st.error(f"Reddit fetch failed for r/{sub_name}")
#             st.error(str(e))

#     return added_count



# def fetch_reddit_mentions(brand_name, subreddits_list):

#     added_count = 0
#     processed_urls = set()

#     existing_df = get_all_mentions_as_df(brand_name)
#     existing_urls = set(existing_df["url"].tolist())

#     session = requests.Session()

#     session.headers.update({
#         "User-Agent": "BrandMonitor/1.0"
#     })

#     for sub_name in subreddits_list:

#         sub_name = sub_name.strip()

#         if not sub_name:
#             continue

#         try:

#             # Arctic Shift API (Pushshift replacement)
#             url = "https://api.pullpush.io/reddit/search/submission/"

#             params = {
#                 "subreddit": sub_name,
#                 "q": brand_name,
#                 "size": 25,
#                 "sort": "desc",
#                 "sort_type": "created_utc"
#             }

#             response = session.get(url, params=params, timeout=20)

#             if response.status_code != 200:

#                 st.warning(f"Failed to fetch r/{sub_name}")
#                 continue

#             data = response.json()

#             posts = data.get("data", [])

#             if not posts:
#                 continue

#             for post in posts:

#                 title = post.get("title", "")
#                 body = post.get("selftext", "")

#                 text = f"{title} {body}"

#                 permalink = post.get("permalink")

#                 if not permalink:
#                     continue

#                 post_url = f"https://reddit.com{permalink}"

#                 if post_url in existing_urls or post_url in processed_urls:
#                     continue

#                 timestamp = datetime.fromtimestamp(
#                     post.get("created_utc", time.time())
#                 )

#                 if add_mention(
#                     brand_name,
#                     "Reddit (PullPush)",
#                     text,
#                     post_url,
#                     timestamp
#                 ):

#                     added_count += 1
#                     processed_urls.add(post_url)

#             time.sleep(1)

#         except Exception as e:

#             st.error(f"Fetch failed for r/{sub_name}")
#             st.error(str(e))

#     return added_count



def fetch_reddit_mentions(brand_name, subreddits_list):

    added_count = 0
    processed_urls = set()

    existing_df = get_all_mentions_as_df(brand_name)
    existing_urls = set(existing_df["url"].tolist())

    session = requests.Session()

    session.headers.update({
        "User-Agent": "BrandMonitor/1.0"
    })

    for sub_name in subreddits_list:

        sub_name = sub_name.strip()

        if not sub_name:
            continue

        data = None

        # SOURCE 1: PullPush API
        try:

            url = "https://api.pullpush.io/reddit/search/submission/"

            params = {
                "subreddit": sub_name,
                "q": brand_name,
                "size": 25,
                "sort": "desc",
                "sort_type": "created_utc"
            }

            response = session.get(url, params=params, timeout=15)

            if response.status_code == 200:

                print("Using PullPush")

                posts = response.json().get("data", [])

                data = {
                    "data": {
                        "children": [{"data": post} for post in posts]
                    }
                }

            elif response.status_code == 429:

                print("PullPush rate limited, switching to fallback")

        except Exception as e:

            print("PullPush failed:", e)

        # SOURCE 2: Reddit public JSON fallback
        if not data:

            try:

                url = f"https://www.reddit.com/r/{sub_name}/new.json"

                response = session.get(
                    url,
                    params={"limit": 25},
                    timeout=15
                )

                if response.status_code == 200:

                    print("Using Reddit JSON fallback")

                    data = response.json()

                else:

                    print("Reddit JSON failed:", response.status_code)

            except Exception as e:

                print("Reddit JSON error:", e)

        # SOURCE 3: Redlib fallback
        if not data:

            try:

                url = f"https://redlib.perennialte.ch/r/{sub_name}/new.json"

                response = session.get(url, timeout=15)

                if response.status_code == 200:

                    print("Using Redlib fallback")

                    data = response.json()

            except Exception as e:

                print("Redlib failed:", e)

        # If all sources fail
        if not data:

            st.warning(f"All sources failed for r/{sub_name}")

            continue

        posts = data.get("data", {}).get("children", [])

        for item in posts:

            post = item.get("data", {})

            title = post.get("title", "")
            body = post.get("selftext", "")

            text = f"{title} {body}"

            if brand_name.lower() not in text.lower():
                continue

            permalink = post.get("permalink")

            if not permalink:
                continue

            post_url = f"https://reddit.com{permalink}"

            if post_url in existing_urls or post_url in processed_urls:
                continue

            timestamp = datetime.fromtimestamp(
                post.get("created_utc", time.time())
            )

            if add_mention(
                brand_name,
                "Reddit",
                text,
                post_url,
                timestamp
            ):

                added_count += 1

                processed_urls.add(post_url)

        time.sleep(2)

    return added_count








def generate_positive_report_summary(df):
    """Generates a concise summary of POSITIVE feedback."""
    positive_df = df[df["sentiment"] == "Positive"]

    if positive_df.empty:
        return "No positive feedback found."

    texts = "\n---\n".join(positive_df["text"].tolist())
    texts = texts[:4000]  

    prompt = f"""
    You are a business analyst.
    Summarize the following POSITIVE customer feedback in 3 bullet points.
    Focus on strengths, value, and what users appreciate most.

    Feedback:
    {texts}
    """

    try:
        client = get_gemini_client()
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return response.text.strip()
    except Exception as e:
        return f"Error generating positive summary: {e}"


def generate_negative_report_summary(df):
    negative_df = df[df["sentiment"] == "Negative"]

    if negative_df.empty:
        return "No negative feedback found."

    texts = "\n---\n".join(negative_df["text"].tolist())
    texts = texts[:4000]

    prompt = f"""
    You are a business analyst.
    Summarize the following NEGATIVE customer feedback in 3 bullet points.
    Focus on complaints, pain points, and risks.

    Feedback:
    {texts}
    """

    try:
        client = get_gemini_client()
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return response.text.strip()
    except Exception as e:
        return f"Error generating negative summary: {e}"


def generate_report_summary(df):
    relevant_df = df[df["sentiment"].isin(["Negative", "Neutral"])]

    if relevant_df.empty:
        return "No suggestions found."

    texts = "\n---\n".join(relevant_df["text"].tolist())
    texts = texts[:4000]

    prompt = f"""
    You are a product strategist.
    Based on the following user feedback, identify:
    - Key suggestions
    - Feature requests
    - Improvement opportunities

    Feedback:
    {texts}
    """

    try:
        client = get_gemini_client()
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return response.text.strip()
    except Exception as e:
        return f"Error generating suggestion summary: {e}"




def batch_analyze_texts(texts):
    """
    Analyze multiple texts in a single API call using Gemini's structured output.
    Returns a list of dicts: [{"sentiment": str, "topic": str, "urgency": str}, ...]
    """
    if not texts:
        return []
    
    texts_with_indices = "\n\n".join([f"[{i}] {text}" for i, text in enumerate(texts)])
    
    prompt = f"""
Analyze each of the following texts for sentiment, topic, and urgency.

For each text [i], provide:
- sentiment: one of "Positive", "Negative", or "Neutral"
- topic: main topic in 1-3 words
- urgency: "High" or "Low" based on how urgent the feedback seems

Output a JSON array of objects, one for each text in order.

Texts:
{texts_with_indices}
"""
    
    try:
        client = get_gemini_client()
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'response_schema': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'sentiment': {'type': 'string', 'enum': ['Positive', 'Negative', 'Neutral']},
                            'topic': {'type': 'string'},
                            'urgency': {'type': 'string', 'enum': ['High', 'Low']}
                        },
                        'required': ['sentiment', 'topic', 'urgency']
                    }
                }
            }
        )
        results = json.loads(response.text.strip())
        return results
    except Exception as e:
        st.error(f"Batch analysis error: {e}")
        return [{"sentiment": "Neutral", "topic": "Unknown", "urgency": "Low"} for _ in texts]


def get_sentiment(text):
    prompt = f"""
Analyze the sentiment of this text. Reply with EXACTLY one word: Positive, Negative, or Neutral.

Text: {text}

Sentiment:"""

    try:
        client = get_gemini_client()
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt).text.strip()

        
        response = response.lower()

        if "positive" in response:
            return "Positive"
        elif "negative" in response:
            return "Negative"
        elif "neutral" in response:
            return "Neutral"
        else:
            
            return "Neutral"

    except Exception as e:
        st.error(f"Sentiment analysis error: {e}")
        return "Neutral"


def get_topic(text):
    prompt = f"Identify the main topic or category of this text in 1-3 words:\n{text}"
    try:
        client = get_gemini_client()
        return client.models.generate_content(model='gemini-2.5-flash', contents=prompt).text.strip()
    except:
        return "General"


def get_urgency(text):
    prompt = f"Rate the urgency level of this feedback. Reply with only 'High' or 'Low':\n{text}"
    try:
        client = get_gemini_client()
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt).text.strip()
        if "high" in response.lower():
            return "High"
        else:
            return "Low"
    except:
        return "Low"


def update_mention_analysis(mention_id, sentiment, topic, urgency):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE mentions
            SET sentiment=?, topic=?, urgency=?
            WHERE id=?
        """,
            (sentiment, topic, urgency, mention_id),
        )
        conn.commit()






