import streamlit as st
import google.generativeai as genai








st.set_page_config(
    page_title="AI Reddit Brand Monitor",
    page_icon="🤖",
    layout="wide"
)





model = genai.GenerativeModel("gemini-2.5-flash")

@st.cache_data(ttl=3600)
def translate_ui(text, language):

    prompt = f"""
Translate the following text to {language}.

Return ONLY the translated text.
Do NOT add explanation.

Text:
{text}
"""

    return bu.generate_ai_response(prompt)







languages = {
    "English": "English",
    "Hindi": "Hindi",
    "Malayalam": "Malayalam",
    "Tamil": "Tamil",
    "Telugu": "Telugu"
}


selected_language = st.sidebar.selectbox(
    "🌐 Select Language",
    list(languages.keys())
)






import backend_utils as bu
import plotly.express as px
import os

# if not os.getenv("GEMINI_API_KEY"):
#     st.error("Please set the GEMINI_API_KEY environment variable with your Google Gemini API key.")
#     st.stop()




bu.init_db()


if "app_ready" not in st.session_state:
    st.session_state.app_ready = True

if "brand_name" not in st.session_state:
    st.session_state.brand_name = "OpenAI"


with st.sidebar:
    st.title(
    translate_ui(
        "AI Brand Monitor",
        languages[selected_language]
    )
)


    st.info("Powered by Multi-Model AI Intelligence")


    st.header("Configuration")

    st.session_state.brand_name = st.text_input(
        "Brand / Keyword to Monitor",
        st.session_state.brand_name
    )

    subreddits_str = st.text_area(
        "Subreddits (comma-separated)",
        "OpenAI, ChatGPT, artificial, singularity"
    )

    subreddits_list = [
        s.strip() for s in subreddits_str.split(",") if s.strip()
    ]

  
    if st.button("Fetch New Mentions"):
        with st.spinner(f"Fetching data for '{st.session_state.brand_name}'..."):
            count = bu.fetch_reddit_mentions(
                st.session_state.brand_name,
                subreddits_list
            )
            st.success(f"Added {count} new mentions.")
            st.rerun()
            
    if st.button("Run AI Competitive Analysis"):

        competitor_name = bu.suggest_competitor(st.session_state.brand_name)

        if competitor_name:
            st.session_state.competitor = competitor_name
            st.info(f"AI detected competitor: {competitor_name}")

            bu.fetch_reddit_mentions(
                competitor_name,
                subreddits_list
            )
            competitor_df = bu.get_all_mentions_as_df(competitor_name)
            pending_comp = competitor_df[competitor_df["sentiment"].isnull()]

            if not pending_comp.empty:
                    texts = pending_comp["text"].tolist()
                    analyses = bu.analyze_in_batches(texts, batch_size=5)

                    for i, row in enumerate(pending_comp.itertuples()):
                        analysis = analyses[i]

                        bu.update_mention_analysis(
                            row.id,
                            analysis.get("sentiment", "Neutral"),
                            analysis.get("topic", "Unknown"),
                            analysis.get("urgency", "Low")
                        )

            st.success(f"Fetched data for {competitor_name}")
            st.rerun()
        else:
            st.warning("Could not detect competitor.")


   
    all_data_df = bu.get_all_mentions_as_df(st.session_state.brand_name)
    pending_df = all_data_df[all_data_df["sentiment"].isnull()]

    st.info(f"**{len(pending_df)}** mentions pending analysis")

    if not pending_df.empty:
        if st.button(f"Analyze {len(pending_df)} Pending Mentions"):
            progress = st.progress(0, text="Analyzing mentions...")
            total = len(pending_df)

            texts = pending_df["text"].tolist()
            
            # analyses = bu.batch_analyze_texts(texts)
            analyses = bu.analyze_in_batches(texts, batch_size=10)

            
            for i, row in enumerate(pending_df.itertuples()):
                if i < len(analyses):
                    analysis = analyses[i]
                    sentiment = analysis.get("sentiment", "Neutral")
                    topic = analysis.get("topic", "Unknown")
                    urgency = analysis.get("urgency", "Low")
                else:
                    sentiment = "Neutral"
                    topic = "Unknown"
                    urgency = "Low"
                
                bu.update_mention_analysis(
                    row.id, sentiment, topic, urgency
                )

                progress.progress(
                    (i + 1) / total,
                    text=f"Updating {i + 1}/{total}"
                )

            progress.empty()
            st.success("Analysis complete!")
            st.rerun()


st.title(f"Reputation Dashboard: {st.session_state.brand_name}")

analyzed_df = all_data_df.dropna(subset=["sentiment"]).copy()

tab1, tab2 = st.tabs(["Main Dashboard", "Raw Data"])


with tab1:
    st.header("Overall Brand Sentiment")

    sentiment_counts = analyzed_df["sentiment"].value_counts()

    if not sentiment_counts.empty:
        fig_pie = px.pie(
            sentiment_counts,
            values=sentiment_counts.values,
            names=sentiment_counts.index,
            title="Sentiment Breakdown",
            color=sentiment_counts.index,
            color_discrete_map={
                "Negative": "red",
                "Positive": "green",
                "Neutral": "blue"
            }
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.write("No sentiment data available yet.")

    topics_exploded = analyzed_df["topic"].str.split(",").explode().str.strip()
    topic_counts = topics_exploded.value_counts()

    if not topic_counts.empty:
        fig_bar = px.bar(
            topic_counts,
            x=topic_counts.index,
            y=topic_counts.values,
            title="Top Topics",
            labels={"x": "Topic", "y": "Count"}
        )
        st.plotly_chart(fig_bar, use_container_width=True)
        
    if "competitor" in st.session_state:

        competitor_name = st.session_state.competitor

        competitor_df = bu.get_all_mentions_as_df(competitor_name)
        competitor_analyzed = competitor_df.dropna(subset=["sentiment"])
      
        if not competitor_analyzed.empty:

            brand_score = bu.calculate_competitive_score(analyzed_df)
            competitor_score = bu.calculate_competitive_score(competitor_analyzed)

            st.divider()
            st.header("Competitive Performance")

            import plotly.graph_objects as go

            fig = go.Figure()

            fig.add_trace(go.Bar(
                x=[st.session_state.brand_name],
                y=[brand_score],
                name="Brand"
            ))

            fig.add_trace(go.Bar(
                x=[competitor_name],
                y=[competitor_score],
                name="Competitor"
            ))

            
            # max_score = max(brand_score, competitor_score, 20)
            max_score = max(brand_score, competitor_score) + 5



            fig.update_layout(
            yaxis=dict(range=[0, max_score + 5]),
            title="Competitive Score Comparison",
            yaxis_title="Competitive Score",
            xaxis_title="Brand"
            )

            st.plotly_chart(fig, use_container_width=True)

            # AI Summary
            st.header("Competition Analysis")

            summary = bu.generate_competition_summary(
                analyzed_df,
                competitor_analyzed,
                st.session_state.brand_name,
                competitor_name
            )

            st.markdown(summary)


    st.divider()
    st.header("Automated Summaries")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Positive Summary"):
            with st.spinner("Generating positive summary..."):
                # st.markdown(bu.generate_positive_report_summary(analyzed_df))
                summary = bu.generate_positive_report_summary(analyzed_df)

                translated_summary = translate_ui(
                summary,
                languages[selected_language]
                )

                st.markdown(translated_summary)


    with col2:
        if st.button("Negative Summary"):
            with st.spinner("Generating negative summary..."):
                # st.markdown(bu.generate_negative_report_summary(analyzed_df))
                summary = bu.generate_negative_report_summary(analyzed_df)

                translated_summary = translate_ui(
                    summary,
                    languages[selected_language]
                )

                st.markdown(translated_summary)


    with col3:
        if st.button("Suggestion Summary"):
            with st.spinner("Generating suggestion summary..."):
                # st.markdown(bu.generate_report_summary(analyzed_df))
                summary = bu.generate_report_summary(analyzed_df)

                translated_summary = translate_ui(
                    summary,
                    languages[selected_language]
                )

                st.markdown(translated_summary)


with tab2:
    st.header("All Raw Mentions")
    st.dataframe(
        all_data_df,
        use_container_width=True,
        hide_index=True
    )
    
    
    
    
    

    
    






