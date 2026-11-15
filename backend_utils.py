import sqlite3
import time
from datetime import datetime
import json
import pandas as pd
import requests
import streamlit as st
import google.genai as genai
import os
from urllib.parse import quote_plus
from groq import Groq
import sys
from dotenv import load_dotenv
from api_client import BrandMonitorClient
import praw
from prawcore.exceptions import PrawcoreException
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
    
GROQ_API_KEY = None

try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except Exception:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")

REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv(
    "REDDIT_USER_AGENT", "BrandMonitoring/1.0 (brand-monitoring-app)"
)
APIFY_TOKEN = os.getenv("APIFY_TOKEN")
APIFY_ACTOR_ID = os.getenv("APIFY_ACTOR_ID", "automation-lab~reddit-scraper")
APIFY_MAX_ITEMS = int(os.getenv("APIFY_MAX_ITEMS", "25"))



if not GROQ_API_KEY and not API_KEY:
    st.error("❌ No AI API key found. Add GROQ_API_KEY or GEMINI_API_KEY")
    st.stop()

_api_client = None


def configure_api_client(client: BrandMonitorClient):
    global _api_client
    _api_client = client

@st.cache_resource
def get_gemini_client():
    return genai.Client(api_key=API_KEY)


@st.cache_resource
def get_groq_client():
    return Groq(api_key=GROQ_API_KEY)


@st.cache_resource
def get_reddit_client():
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        return None
    return praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
        check_for_async=False,
    )


def fetch_apify_posts(session, brand_name, subreddit):
    if not APIFY_TOKEN:
        return None

    search_url = (
        f"https://www.reddit.com/r/{subreddit}/search/?"
        f"q={quote_plus(brand_name)}&restrict_sr=1&sort=new"
    )
    endpoint = (
        f"https://api.apify.com/v2/acts/{APIFY_ACTOR_ID}"
        "/run-sync-get-dataset-items"
    )
    response = session.post(
        endpoint,
        params={"token": APIFY_TOKEN},
        json={
            "startUrls": [{"url": search_url}],
            "maxItems": APIFY_MAX_ITEMS,
        },
        timeout=120,
    )
    response.raise_for_status()
    items = response.json()
    if not isinstance(items, list):
        raise ValueError("Apify returned an unexpected dataset format")
    return items


def normalize_apify_post(post):
    title = post.get("title", "")
    body = post.get("selftext") or post.get("body") or post.get("text") or ""
    permalink = post.get("permalink", "")
    url = post.get("url") or post.get("postUrl") or ""
    if not permalink and "/comments/" in url:
        permalink = url.split("reddit.com", 1)[-1]
    created = (
        post.get("created_utc")
        or post.get("createdUtc")
        or post.get("createdAt")
        or time.time()
    )
    if isinstance(created, str):
        try:
            created = datetime.fromisoformat(created.replace("Z", "+00:00")).timestamp()
        except ValueError:
            created = time.time()
    return {
        "title": title,
        "selftext": body,
        "permalink": permalink,
        "created_utc": created,
    }









def init_db():
    if _api_client is not None:
        return
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
    if _api_client is not None:
        mention = _api_client.create_mention(
            {
                "brand": brand_name,
                "source": source,
                "text": text,
                "url": url,
                "timestamp": timestamp.isoformat(),
            }
        )
        return bool(mention)

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
    if _api_client is not None:
        records = _api_client.list_mentions(brand_name)
        columns = [
            "id",
            "brand",
            "source",
            "text",
            "url",
            "timestamp",
            "sentiment",
            "topic",
            "urgency",
        ]
        df = pd.DataFrame(records)
        for column in columns:
            if column not in df:
                df[column] = None
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        return df[columns]

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

    session = requests.Session()

    session.headers.update({
        "User-Agent": REDDIT_USER_AGENT
    })
    reddit_client = get_reddit_client()

    for sub_name in subreddits_list:

        sub_name = sub_name.strip()

        if not sub_name:
            continue

        data = None

        if APIFY_TOKEN:
            try:
                posts = fetch_apify_posts(session, brand_name, sub_name)
                data = {
                    "data": {
                        "children": [
                            {"data": normalize_apify_post(post)}
                            for post in posts
                        ]
                    }
                }
                print("Using Apify Reddit scraper")
            except (requests.RequestException, ValueError) as error:
                print(f"Apify failed for r/{sub_name}: {error}")

        if data is None and reddit_client is not None:
            try:
                posts = reddit_client.subreddit(sub_name).search(
                    brand_name, sort="new", limit=25
                )
                data = {
                    "data": {
                        "children": [
                            {
                                "data": {
                                    "title": post.title,
                                    "selftext": post.selftext,
                                    "permalink": post.permalink,
                                    "created_utc": post.created_utc,
                                }
                            }
                            for post in posts
                        ]
                    }
                }
                print("Using Reddit API")
            except PrawcoreException as error:
                print(f"Reddit API failed for r/{sub_name}: {error}")

        if not data:
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

            except requests.RequestException as error:
                print("PullPush failed:", error)

        
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

                elif response.status_code != 403:
                    print("Reddit JSON failed:", response.status_code)

            except Exception as e:

                print("Reddit JSON error:", e)

        
        if not data:

            try:

                url = f"https://redlib.perennialte.ch/r/{sub_name}/new.json"

                response = session.get(url, timeout=15)

                if response.status_code == 200:

                    print("Using Redlib fallback")

                    data = response.json()

            except Exception as e:

                print("Redlib failed:", e)

       
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

            created = post.get("created_utc", time.time())

            try:
                timestamp = datetime.fromtimestamp(float(created))
            except:
                timestamp = datetime.now()


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
    texts = texts[:2000]  

    prompt = f"""
    You are a business analyst.
    Summarize the following POSITIVE customer feedback in 3 bullet points.
    Focus on strengths, value, and what users appreciate most.

    Feedback:
    {texts}
    """

    try:
        return generate_ai_response(prompt)

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
        return generate_ai_response(prompt)

    except Exception as e:
        return f"Error generating negative summary: {e}"





def generate_report_summary(df):

    relevant_df = df[
    (df["sentiment"] == "Negative") |
    ((df["sentiment"] == "Neutral") & (df["urgency"] == "High"))
]
    


    if relevant_df.empty:
        return "No suggestions found."
    
    relevant_df = relevant_df.copy()
    relevant_df["topic"] = (
    relevant_df["topic"]
    .dropna()
    .str.lower()
    .str.strip()
)

    

    topic_counts = (
        relevant_df["topic"]
        .dropna()
        .str.strip()
        .value_counts()
    )

    total = topic_counts.sum()

    if total == 0:
        return "No significant issues detected."


    top_issues = topic_counts.head(5)

    issues_text = "\n".join(
        [
            f"• {topic} ({round(count/total*100,1)}%)"
            for topic, count in top_issues.items()
        ]
    )

    

    texts = "\n---\n".join(relevant_df["text"].tolist())
    texts = texts[:4000]

    prompt = f"""
You are an enterprise brand intelligence analyst.

Explain the user problems clearly and professionally.

Focus on:

• Root causes  
• User frustration patterns  
• Product weaknesses  

Feedback:
{texts}
"""

    ai_analysis = generate_ai_response(prompt)

   

    final_output = f"""
Most reported issues:
{issues_text}

Analysis:
{ai_analysis}
"""

    return final_output.strip()





def batch_analyze_texts(texts):
#     """
#     Analyze multiple texts in a single API call using Gemini's structured output.
#     Returns a list of dicts: [{"sentiment": str, "topic": str, "urgency": str}, ...]
    
# """
    if not texts:
        return []
    
    
    texts_with_indices = "\n\n".join(
    [f"[{i}] {text[:250]}" for i, text in enumerate(texts)]
)

    

    prompt = f"""
You are a strict JSON sentiment classifier.

Classify EACH text independently.
Do NOT average tone across texts.
Return EXACTLY {len(texts)} JSON objects.
If unsure, still return one object per text.
Do NOT skip any text.

Allowed sentiments:
- Positive
- Negative
- Neutral

Rules:
- Complaints or problems = Negative
- Questions about issues = Negative
- Praise or recommendation = Positive
- Pure factual discussion = Neutral

Return ONLY valid JSON.
No explanation.
No markdown.
No extra text.

Format:
[
  {{
    "sentiment": "Positive|Negative|Neutral",
    "topic": "1-3 words",
    "urgency": "High|Low"
  }}
]

Texts:
{texts_with_indices}
"""



    
    
    try:
        response = generate_ai_response(prompt, task_type="classification")

        if not response or response.startswith("AI analysis"):
            raise ValueError("AI unavailable")

        response = response.strip()

        # Remove markdown fences
        response = response.replace("```json", "").replace("```", "").strip()

        # Extract JSON array safely
        start = response.find("[")
        end = response.rfind("]")

        if start == -1 or end == -1:
            raise ValueError("No valid JSON array found")

        json_text = response[start:end + 1]

        results = json.loads(json_text)

        return results

    except Exception as e:
        st.error(f"Batch analysis error: {e}")

        return [
            {"sentiment": "Neutral", "topic": "Unknown", "urgency": "Low"}
            for _ in texts
        ]

def analyze_in_batches(texts, batch_size=10):
    all_results = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]

        results = batch_analyze_texts(batch)

        # 🔁 Retry once if mismatch
        if len(results) != len(batch):
            print("Retrying batch due to mismatch...")
            results = batch_analyze_texts(batch)

        # 🛡 Final safety fallback
        if len(results) != len(batch):
            print("Batch still mismatched. Filling defaults.")
            results = [
                {"sentiment": "Neutral", "topic": "Unknown", "urgency": "Low"}
                for _ in batch
            ]

        all_results.extend(results)

    return all_results





def get_sentiment(text):
    prompt = f"""
Analyze the sentiment of this text. Reply with EXACTLY one word: Positive, Negative, or Neutral.

Text: {text}

Sentiment:"""

    try:
        response = generate_ai_response(prompt).lower()

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
        return generate_ai_response(prompt)

    except:
        return "General"


def get_urgency(text):
    prompt = f"Rate the urgency level of this feedback. Reply with only 'High' or 'Low':\n{text}"
    try:
        response = generate_ai_response(prompt)

        

        if "high" in response.lower():
            return "High"
        else:
            return "Low"
    except:
        return "Low"


def update_mention_analysis(mention_id, sentiment, topic, urgency):
    if _api_client is not None:
        _api_client.update_mention(mention_id, sentiment, topic, urgency)
        return

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
        
        
        
        
        
def generate_ai_response(prompt, task_type="general"):

    model_name = "llama-3.1-8b-instant"

    
    if task_type == "premium":
        model_name = "llama-3.3-70b-versatile"

    
    if GROQ_API_KEY:
        try:
            groq = get_groq_client()

            response = groq.chat.completions.create(
                model=model_name,   
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )

            return response.choices[0].message.content.strip()

        except Exception as groq_error:
            st.error(f"Groq failed: {groq_error}")

    
    if API_KEY:
        try:
            gemini = get_gemini_client()

            response = gemini.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )

            return response.text.strip()

        except Exception as gemini_error:
            st.error(f"Gemini failed: {gemini_error}")

    return "AI analysis temporarily unavailable."




def suggest_competitor(brand_name):

    prompt = f"""
You are a market intelligence system.

For the brand: {brand_name}

Return ONLY the strongest current direct competitor brand name.

Rules:
- Must be real company
- Must be current competitor
- Return only the name
- No explanation
"""

    try:
        response = generate_ai_response(prompt)
        competitor = response.strip().split("\n")[0]
        return competitor
    except:
        return None




def calculate_competitive_score(df):

    if df.empty:
        return 0

    total = len(df)

    sentiment_counts = df["sentiment"].value_counts(normalize=True)

    positive = sentiment_counts.get("Positive", 0)
    negative = sentiment_counts.get("Negative", 0)
    neutral = sentiment_counts.get("Neutral", 0)

    high_urgency = len(df[df["urgency"] == "High"]) / total

    
    sentiment_score = (
    positive * 50
    + neutral * 20
    - negative * 40
)

    
    urgency_penalty = high_urgency * 10

    final_score = sentiment_score - urgency_penalty

    
    final_score = max(min(final_score, 100), 0)

    return round(final_score, 2)




def generate_competition_summary(df_a, df_b, brand_a, brand_b):

    score_a = calculate_competitive_score(df_a)
    score_b = calculate_competitive_score(df_b)

    total_a = len(df_a)
    total_b = len(df_b)

    pos_a = len(df_a[df_a["sentiment"] == "Positive"])
    neg_a = len(df_a[df_a["sentiment"] == "Negative"])

    pos_b = len(df_b[df_b["sentiment"] == "Positive"])
    neg_b = len(df_b[df_b["sentiment"] == "Negative"])
    neutral_a = len(df_a[df_a["sentiment"] == "Neutral"])
    neutral_b = len(df_b[df_b["sentiment"] == "Neutral"])

    high_a = len(df_a[df_a["urgency"] == "High"])
    high_b = len(df_b[df_b["urgency"] == "High"])

    neg_ratio_a = neg_a / total_a if total_a else 0
    neg_ratio_b = neg_b / total_b if total_b else 0

    pos_ratio_a = pos_a / total_a if total_a else 0
    pos_ratio_b = pos_b / total_b if total_b else 0
    
    positive_diff = round(pos_ratio_a - pos_ratio_b, 3)
    negative_diff = round(neg_ratio_a - neg_ratio_b, 3)
    urgency_diff = high_a - high_b
    score_diff = round(score_a - score_b, 2)

    
    if score_a > score_b:
        better_score_brand = brand_a
    elif score_b > score_a:
        better_score_brand = brand_b
    else:
        better_score_brand = "Tie"


    prompt = f"""
You are a product strategy analyst.

Translate performance metrics into competitive insight.

Important:
- Do NOT mention ratios or numbers.
- Do NOT sound like a data report.
- Do NOT invent external causes.
- Focus only on what user sentiment suggests.

Brand: {brand_a}
Competitor: {brand_b}

Data summary:
{brand_a} → Score: {score_a}, Positive ratio: {round(pos_ratio_a,2)}, 
Negative ratio: {round(neg_ratio_a,2)}, High urgency issues: {high_a}

{brand_b} → Score: {score_b}, Positive ratio: {round(pos_ratio_b,2)}, 
Negative ratio: {round(neg_ratio_b,2)}, High urgency issues: {high_b}

Write a clear competitive insight covering:

1. What {brand_b} is doing better in users' eyes
2. What {brand_a} is doing better in users' eyes
3. How {brand_a} can strategically strengthen its position

Make it natural.
Make it product-focused.
Make it useful for decision-making.
No bullet metrics.
No percentages.
No fluff.
"""






    return generate_ai_response(prompt)

