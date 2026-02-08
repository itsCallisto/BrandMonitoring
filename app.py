import streamlit as st
import backend_utils as bu
import plotly.express as px
import os

if not os.getenv("GEMINI_API_KEY"):
    st.error("Please set the GEMINI_API_KEY environment variable with your Google Gemini API key.")
    st.stop()


st.set_page_config(
    page_title="AI Reddit Brand Monitor",
    page_icon="🤖",
    layout="wide"
)


bu.init_db()


if "app_ready" not in st.session_state:
    st.session_state.app_ready = True

if "brand_name" not in st.session_state:
    st.session_state.brand_name = "OpenAI"


with st.sidebar:
    st.title("🤖 AI Brand Monitor")

    st.info("Using Google Gemini (cloud-based Generative AI)")


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

   
    all_data_df = bu.get_all_mentions_as_df(st.session_state.brand_name)
    pending_df = all_data_df[all_data_df["sentiment"].isnull()]

    st.info(f"**{len(pending_df)}** mentions pending analysis")

    if not pending_df.empty:
        if st.button(f"Analyze {len(pending_df)} Pending Mentions"):
            progress = st.progress(0, text="Analyzing mentions...")
            total = len(pending_df)

            for i, row in enumerate(pending_df.itertuples()):
                sentiment = bu.get_sentiment(row.text)
                topic = bu.get_topic(row.text)
                urgency = bu.get_urgency(row.text)

                # if sentiment and topic and urgency:
                #     bu.update_mention_analysis(
                #         row.id, sentiment, topic, urgency
                #     )
                bu.update_mention_analysis(
                    row.id,
                     sentiment or "Neutral",
                    topic or "Unknown",
                        urgency or "Low"
                        )


                progress.progress(
                    (i + 1) / total,
                    text=f"Analyzing {i + 1}/{total}"
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

    st.divider()
    st.header("Automated Summaries")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Positive Summary"):
            with st.spinner("Generating positive summary..."):
                st.markdown(bu.generate_positive_report_summary(analyzed_df))

    with col2:
        if st.button("Negative Summary"):
            with st.spinner("Generating negative summary..."):
                st.markdown(bu.generate_negative_report_summary(analyzed_df))

    with col3:
        if st.button("Suggestion Summary"):
            with st.spinner("Generating suggestion summary..."):
                st.markdown(bu.generate_report_summary(analyzed_df))

with tab2:
    st.header("All Raw Mentions")
    st.dataframe(
        all_data_df,
        use_container_width=True,
        hide_index=True
    )




