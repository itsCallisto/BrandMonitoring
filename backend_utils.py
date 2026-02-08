import sqlite3
import time
from datetime import datetime

import pandas as pd
import requests
import streamlit as st
import google.genai as genai
# import google.generativeai as genai

import os

DB_NAME = "brand_monitor.db"


client = genai.Client(api_key="AIzaSyA1bfPZCH2LyE9WtTr6kmJ2YZYs_jTR8os")


# ================= DATABASE =================


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


# ================= RAPIDAPI FETCH =================


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
            # 🔑 THIS IS WHERE THE URL GOES
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

            time.sleep(1)  # polite delay

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
    texts = texts[:4000]  # safety limit

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


# ================= ANALYSIS =================


def get_sentiment(text):
    prompt = f"""
Analyze the sentiment of this text. Reply with EXACTLY one word: Positive, Negative, or Neutral.

Text: {text}

Sentiment:"""

    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt).text.strip()

        # 🔑 normalize output
        response = response.lower()

        if "positive" in response:
            return "Positive"
        elif "negative" in response:
            return "Negative"
        elif "neutral" in response:
            return "Neutral"
        else:
            # If unclear, default to Neutral
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
