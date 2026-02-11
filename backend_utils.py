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


import os

from dotenv import load_dotenv

load_dotenv()  







if sys.platform.startswith("win"):
    
    DB_NAME = "brand_monitor.db"
else:
    
    DB_NAME = "/tmp/brand_monitor.db"











import streamlit as st


API_KEY = None

try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    API_KEY = os.getenv("GEMINI_API_KEY")


if not API_KEY:
    st.error("❌ GEMINI_API_KEY not found in Streamlit secrets")
    st.stop()
client = genai.Client(api_key=API_KEY)









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
init_db()


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





def fetch_reddit_mentions(brand_name, subreddits_list):
    added_count = 0
    processed_urls = set()

    existing_df = get_all_mentions_as_df(brand_name)
    existing_urls = set(existing_df["url"].tolist())

    headers = {"User-Agent": "Mozilla/5.0 (BrandMonitorProject)"}

    for sub_name in subreddits_list:
        sub_name = sub_name.strip()
        if not sub_name:
            continue

        try:
           
            url = f"https://www.reddit.com/r/{sub_name}/search.json"

            params = {"q": brand_name, "restrict_sr": 1, "sort": "new", "limit": 10}

            response = requests.get(url, headers=headers, params=params, timeout=20)
            response.raise_for_status()

            data = response.json()
            posts = data.get("data", {}).get("children", [])
            
            st.info(f"Found {len(posts)} posts in r/{sub_name}")

            for item in posts:
                post = item.get("data", {})
                if not isinstance(post, dict):
                    continue

                permalink = post.get("permalink")
                if not permalink:
                    continue

                post_url = f"https://www.reddit.com{permalink}"

                if post_url in existing_urls or post_url in processed_urls:
                    continue

                text = f"{post.get('title', '')} {post.get('selftext', '')}"
                timestamp = datetime.fromtimestamp(
                    post.get("created_utc", datetime.now().timestamp())
                )

                if add_mention(
                    brand_name, "Reddit (Public JSON)", text, post_url, timestamp
                ):
                    added_count += 1
                    processed_urls.add(post_url)

            time.sleep(1)  

        except Exception as e:
            st.error(f"Could not fetch from r/{sub_name}: {e}")
            import traceback
            st.error(traceback.format_exc())

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
        return client.models.generate_content(model='gemini-2.5-flash', contents=prompt).text.strip()
    except:
        return "General"


def get_urgency(text):
    prompt = f"Rate the urgency level of this feedback. Reply with only 'High' or 'Low':\n{text}"
    try:
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
