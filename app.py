import streamlit as st
import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, date, time
import io
import os
from dotenv import load_dotenv

import os
from dotenv import load_dotenv

from streamlit.errors import StreamlitAPIException, StreamlitSecretNotFoundError

# --- Load API Key with Environment-Specific Logic ---
# This approach allows the app to work seamlessly both locally and on Streamlit Cloud.

# First, try to load from Streamlit's secrets management (for cloud deployment)
try:
    API_KEY = st.secrets["YOUTUBE_API_KEY"]
except (StreamlitAPIException, StreamlitSecretNotFoundError, KeyError):
    # If st.secrets doesn't exist or the key is not found (local development),
    # fall back to loading from a local .env file.
    load_dotenv()
    API_KEY = os.getenv("YOUTUBE_API_KEY")


# --- Functions ---

def search_youtube_api(api_key, keyword, start_date, end_date, max_results=1000):
    """
    使用 Google YouTube Data API 進行搜尋，並支援分頁以取得超過 50 筆結果。
    """
    video_data = []
    next_page_token = None
    
    try:
        start_time = datetime.combine(start_date, time.min).isoformat() + 'Z'
        end_time = datetime.combine(end_date, time.max).isoformat() + 'Z'

        youtube = build('youtube', 'v3', developerKey=api_key)
        
        while len(video_data) < max_results:
            # 每次請求最多 50 筆
            results_per_page = min(50, max_results - len(video_data))

            request = youtube.search().list(
                q=keyword,
                part='snippet',
                type='video',
                maxResults=results_per_page,
                order='date',
                publishedAfter=start_time,
                publishedBefore=end_time,
                pageToken=next_page_token
            )
            
            response = request.execute()

            for item in response.get('items', []) :
                video_data.append({
                    "發布日期": datetime.strptime(item['snippet']['publishedAt'], "%Y-%m-%dT%H:%M:%SZ").date(),
                    "標題": item['snippet']['title'],
                    "作者": item['snippet']['channelTitle'],
                    "網址": f"https://www.youtube.com/watch?v={item['id']['videoId']}"
                })

            next_page_token = response.get('nextPageToken')
            
            # 如果沒有下一頁，或已達到所需數量，則結束迴圈
            if not next_page_token or len(video_data) >= max_results:
                break
            
    except HttpError as e:
        # 檢查是否為 API 金鑰無效的特定錯誤
        if e.resp.status == 400:
             st.error("API 金鑰無效或格式錯誤。請檢查您的 .env 檔案中的 YOUTUBE_API_KEY。")
        else:
            st.error(f"呼叫 YouTube API 時發生錯誤: {e}")
            st.error("請確認您的 API 金鑰是否正確、有效，且尚未超過每日使用配額。")
        return None

    return video_data[:max_results]

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='YouTube_Results')
    processed_data = output.getvalue()
    return processed_data

# --- Streamlit App UI ---

st.set_page_config(page_title="YouTube 影片資訊擷取工具", layout="wide")

st.title("🎬 YouTube 影片資訊擷取工具")

# --- API Key Check ---
if not API_KEY or API_KEY == "YOUR_API_KEY_HERE":
    st.error("錯誤：找不到 API 金鑰！")
    st.info("請依照以下步驟設定：")
    st.markdown("1. 將專案根目錄下的 `.env.example` 檔案複製並改名為 `.env`。")
    st.markdown("2. 在 `.env` 檔案中，將 `YOUR_API_KEY_HERE` 替換成您自己的 YouTube Data API 金鑰。")
    st.markdown("3. 重新啟動應用程式。")
    st.stop() # 如果沒有 API Key，則停止執行

# --- Sidebar for Inputs ---
with st.sidebar:
    st.success("✅ API 金鑰已成功載入！")
    st.header("🔍 搜尋設定")
    keyword = st.text_input("請輸入搜尋關鍵字", "臺師大女足")
    
    today = date.today()
    one_month_ago = today.replace(month=today.month - 1 if today.month > 1 else 12, year=today.year if today.month > 1 else today.year - 1)
    
    start_date = st.date_input("起始日期", one_month_ago)
    end_date = st.date_input("結束日期", today)
    
    search_limit = st.slider("最大搜尋結果數量", 1, 1000, 50)

    search_button = st.button("開始搜尋", type="primary")

# --- Main Area for Results ---

if 'search_results' not in st.session_state:
    st.session_state.search_results = pd.DataFrame()

if search_button:
    if not keyword:
        st.warning("請務必輸入關鍵字！")
    elif start_date > end_date:
        st.error("錯誤：起始日期不能晚於結束日期！")
    else:
        with st.spinner(f"正在透過官方 API 搜尋關於「{keyword}」的影片..."):
            videos = search_youtube_api(API_KEY, keyword, start_date, end_date, max_results=search_limit)
            
            if videos is None:
                st.session_state.search_results = pd.DataFrame()
            elif not videos:
                st.info("在指定日期範圍內找不到任何影片。")
                st.session_state.search_results = pd.DataFrame()
            else:
                df = pd.DataFrame(videos)
                df['發布日期'] = df['發布日期'].astype(str)
                st.session_state.search_results = df.reset_index(drop=True)

# --- Display Results and Download Buttons ---
if not st.session_state.search_results.empty:
    df_to_show = st.session_state.search_results
    st.success(f"成功找到 {len(df_to_show)} 部符合條件的影片！")
    
    st.dataframe(df_to_show, use_container_width=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.download_button(
            label="📥 下載為 CSV 檔",
            data=df_to_show.to_csv(index=False).encode('utf-8-sig'),
            file_name=f"{keyword}_youtube_results.csv",
            mime="text/csv",
        )
        
    with col2:
        st.download_button(
            label="📥 下載為 Excel 檔",
            data=to_excel(df_to_show),
            file_name=f"{keyword}_youtube_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
else:
    st.info("請在左側輸入搜尋條件，然後點擊搜尋。")
