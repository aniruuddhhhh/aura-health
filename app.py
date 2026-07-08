import streamlit as st
import os
import time
import warnings
warnings.filterwarnings("ignore")
import os
os.environ["STREAMLIT_WATCHER_TYPE"] = "none"

st.set_page_config(
    page_title="AURA",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

@st.cache_resource
def initialize_aura():
    if not os.path.exists("aura_health.db"):
        try:
            from db_manager import build_numerical_vault
            build_numerical_vault()
        except Exception as e:
            st.error(f"Setup error: {e}")
            return False
    return True

initialize_aura()

from session_manager import (
    save_message, load_chat_history, clear_chat_history,
)

from journal_manager import (
    add_journal_entry,
    get_recent_journals,
    get_journal_stats,
    search_user_added_journals,
)

try:
    from aura_tools import run_query
except Exception as e:
    st.error(f"Import error: {e}")
    st.stop()

st.markdown("""
<style>
  /* Use system fonts - looks more native */
  html, body, [class*="css"] { 
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
  }
  
  /* Cleaner background - less "designed" */
  .stApp {
    background: #0e1117;
    color: #fafafa;
  }
  
  /* Standard sidebar */
  [data-testid="stSidebar"] {
    background: #1a1d23;
    border-right: 1px solid #2a2f38;
  }
  
  /* Simple buttons - not gradient */
  .stButton > button {
    background: #2563eb;
    color: white;
    border: 1px solid #1d4ed8;
    border-radius: 6px;
    font-weight: 500;
  }
  
  .stButton > button:hover {
    background: #1d4ed8;
  }
  
  /* Hide Streamlit branding */
  #MainMenu, footer, header { visibility: hidden; }
  
  /* Simple journal entry styling */
  .journal-entry {
    background: #1a1d23;
    padding: 12px 16px;
    border-radius: 6px;
    border-left: 3px solid #2563eb;
    margin: 8px 0;
  }
  
  .journal-entry-meta {
    color: #64748b;
    font-size: 0.8rem;
    margin-bottom: 4px;
  }
</style>
""", unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = load_chat_history()

if "page" not in st.session_state:
    st.session_state.page = "Home"

if "demo_query" not in st.session_state:
    st.session_state.demo_query = None

with st.sidebar:
    
    st.markdown("## AURA")
    st.caption("Health Analytics")
    
    st.divider()
    
    page = st.radio(
        "Navigation",
        ["Home", "Chat", "Journal", "Examples", "About"],
        label_visibility="collapsed",
    )
    st.session_state.page = page
    
    st.divider()
    
    st.markdown("**Links**")
    st.markdown("[GitHub](https://github.com/yourusername/aura-health)")
    st.markdown("[LinkedIn](https://linkedin.com/in/yourprofile)")
    
    st.divider()
    
    if st.button("Clear chat history", use_container_width=True):
        clear_chat_history()
        st.session_state.messages = []
        st.rerun()

if st.session_state.page == "Home":
    st.title("AURA")
    st.markdown("##### Health analytics with hybrid SQL generation and semantic journal search")
    
    st.markdown("---")
    st.markdown("""
    AURA combines structured biometric data with semantic journal search to provide 
    contextualized health insights. The system uses template-based and LLM-generated 
    SQL queries against fitness data, alongside cross-encoder reranking for journal 
    retrieval.
    """)
    
    st.markdown("### Capabilities")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **Structured Queries**
        - Single date lookups
        - Aggregate statistics
        - Multi-date comparisons
        - Trend analysis
        - Hourly patterns
        - Weekly aggregates
        - Anomaly detection
        """)
    
    with col2:
        st.markdown("""
        **Semantic Search**
        - Cross-encoder reranking
        - Query expansion
        - Relevance filtering
        - Real-time vectorization
        - Multi-source synthesis
        - Persistent storage
        """)
    
    st.markdown("---")
    st.markdown("### Try it")
    st.markdown("Navigate to **Chat** or **Examples** to explore the system.")


elif st.session_state.page == "Chat":
    st.title("Chat")
    
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    
    if st.session_state.demo_query:
        prompt = st.session_state.demo_query
        st.session_state.demo_query = None
    else:
        prompt = st.chat_input("Ask about your health data...")
    
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        save_message("user", prompt)
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                start = time.time()
                try:
                    history = [m for m in st.session_state.messages[:-1]][-20:]
                    response = run_query(prompt, chat_history=history)
                except Exception as e:
                    response = f"Error: {e}"
                elapsed = time.time() - start
            
            st.markdown(response)
            st.caption(f"Response time: {elapsed:.2f}s")
        
        st.session_state.messages.append({"role": "assistant", "content": response})
        save_message("assistant", response)

elif st.session_state.page == "Journal":
    st.title("Journal")
    
    stats = get_journal_stats()
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Total entries:** {stats['total_structured_entries']}")
    with col2:
        st.markdown(f"**Indexed:** {stats['total_vector_entries']}")
    
    st.markdown("---")
    st.markdown("### New entry")
    
    phase = st.selectbox(
        "Context",
        ["Morning", "Afternoon", "Evening", "Night",
         "Stressed", "Relaxed", "Post-workout", "Other"],
        key="entry_phase",
    )
    
    entry_text = st.text_area(
        "Entry",
        height=120,
        placeholder="What's on your mind?",
        label_visibility="collapsed",
        key="entry_text",
    )
    
    if st.button("Save", type="primary"):
        if entry_text.strip():
            with st.spinner("Saving..."):
                result = add_journal_entry(entry_text.strip(), phase)
            
            if result["success"]:
                if result["vector_saved"]:
                    st.success("Entry saved")
                else:
                    st.warning("Entry saved but indexing failed")
            else:
                st.error("Save failed")
            
            time.sleep(0.5)
            st.rerun()
        else:
            st.warning("Entry cannot be empty")
    
    st.markdown("---")
    
    with st.expander("Search entries"):
        search_query = st.text_input(
            "Search",
            label_visibility="collapsed",
            placeholder="Search your entries...",
        )
        
        if search_query:
            results = search_user_added_journals(search_query, k=5)
            
            if results:
                st.markdown(f"_Found {len(results)} entries_")
                for r in results:
                    st.markdown(f"""
                    <div class='journal-entry'>
                      <div class='journal-entry-meta'>{r['timestamp'][:16]} · {r['phase']}</div>
                      <div>{r['content']}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No matching entries")
    
    st.markdown("---")
    st.markdown("### Recent entries")
    
    journals = get_recent_journals(limit=20)
    
    if not journals:
        st.markdown("_No entries yet._")
    else:
        for j in journals:
            phase_str = j['phase'] if j['phase'] else 'No context'
            st.markdown(f"""
            <div class='journal-entry'>
              <div class='journal-entry-meta'>{j['timestamp'][:16]} · {phase_str}</div>
              <div>{j['entry']}</div>
            </div>
            """, unsafe_allow_html=True)

elif st.session_state.page == "Examples":
    st.title("Examples")
    st.caption("Sample queries demonstrating different capabilities")
    
    st.markdown("---")
    st.markdown("### Basic queries")
    
    basic_queries = [
        "What was my heart rate on May 9?",
        "How was my sleep on April 17?",
        "Show my most active days",
        "What was my average heart rate on May 2?",
    ]
    
    cols = st.columns(2)
    for idx, query in enumerate(basic_queries):
        with cols[idx % 2]:
            if st.button(query, key=f"basic_{idx}", use_container_width=True):
                st.session_state.demo_query = query
                st.session_state.page = "Chat"
                st.rerun()
    
    st.markdown("---")
    st.markdown("### Advanced queries")
    
    advanced_queries = [
        "Compare my heart rate on May 2 vs May 9",
        "Show me my sleep trend",
        "Days when I slept poorly and had high heart rate",
        "Heart rate by hour of day",
        "Average steps per week",
        "Show me outlier days for heart rate",
    ]
    
    cols = st.columns(2)
    for idx, query in enumerate(advanced_queries):
        with cols[idx % 2]:
            if st.button(query, key=f"adv_{idx}", use_container_width=True):
                st.session_state.demo_query = query
                st.session_state.page = "Chat"
                st.rerun()
    
    st.markdown("---")
    st.markdown("### Context-aware queries")
    
    context_queries = [
        "Why was my heart rate high on May 9?",
        "Why was I stressed last month?",
        "When did I feel anxious?",
    ]
    
    cols = st.columns(2)
    for idx, query in enumerate(context_queries):
        with cols[idx % 2]:
            if st.button(query, key=f"ctx_{idx}", use_container_width=True):
                st.session_state.demo_query = query
                st.session_state.page = "Chat"
                st.rerun()

elif st.session_state.page == "About":
    st.title("About")
    
    st.markdown("""
    AURA is a health analytics platform that I built to explore hybrid retrieval 
    architectures combining structured queries with semantic search.
    
    The system uses template-based SQL for common queries and LLM-generated SQL 
    for complex analytical questions like comparisons, trends, and anomaly 
    detection. Journal entries are indexed in a vector database with cross-encoder 
    reranking applied to retrieved candidates.
    """)
    
    st.markdown("---")
    
    st.markdown("### Stack")
    st.markdown("""
    - Python, Streamlit
    - SQLite for biometric data
    - Pinecone for vector storage
    - Supabase for persistent session data
    - Google Gemini for SQL generation and insights
    - SentenceTransformers for embeddings
    - HuggingFace cross-encoder for reranking
    """)
    
    st.markdown("### Code")
    st.markdown("[GitHub repository](https://github.com/aniruuddhhhh/aura-health)")
    
    st.markdown("### Contact")
    st.markdown("""
    - anirudhak1269@example.com
    - [LinkedIn](https://www.linkedin.com/in/anirudh-s-22ab19271)
    """)
