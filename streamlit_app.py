import streamlit as st
import requests
import pandas as pd
import openai
import re
import base64

# OpenAI clientの初期化
client = openai.OpenAI(api_key=st.secrets["openai_api_key"])

# 翻訳関数
@st.cache_data
def translate_to_english(text):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "あなたは優秀な医療翻訳者です。"},
            {"role": "user", "content": f"以下の医学用語を英語に翻訳してください：{text}"}
        ]
    )
    return response.choices[0].message.content.strip()

# 英訳部分だけ抽出する関数
def extract_english(text):
    match = re.search(r'英語(?:で|では)?[「\"](.+?)[」\"]', text)
    return match.group(1) if match else text

# ClinicalTrials.gov API呼び出し
def fetch_clinical_trials(condition, terms, location):
    url = "https://clinicaltrials.gov/api/v2/studies"
    params = {
        "query.cond": condition,
        "query.term": terms,
        "filter.overallStatus": "RECRUITING",
        "query.locn": location
    }
    r = requests.get(url, params=params)
    if r.status_code != 200:
        st.error(f"ClinicalTrials.gov APIエラー（ステータスコード: {r.status_code}）")
        st.stop()
    return r.json()

# jRCT検索関数
def search_jrct(disease_name, free_keyword):
    url = "https://jrct.mhlw.go.jp/search"
    params = {
        "reg-plobrem-1": disease_name,
        "demo-1": free_keyword,
        "reg-recruitment-2": "2",  # 募集ステータスが「募集中」のもの
    }

    # HTMLを取得
    response = requests.get(url, params=params)
    if response.status_code != 200:
        st.error(f"jRCTサイトへのアクセスエラー（ステータスコード: {response.status_code}）")
        st.stop()

    # BeautifulSoupで解析
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(response.text, 'html.parser')

    # 検索結果を抽出
    rows = soup.select("table.table-search tbody tr")
    results = []
    for row in rows:
        cols = row.find_all("td")
        if len(cols) > 5:
            results.append({
                "臨床研究実施計画番号": cols[0].get_text(strip=True),
                "研究の名称": cols[1].get_text(strip=True),
                "対象疾患名": cols[2].get_text(strip=True),
                "研究の進捗状況": cols[3].get_text(strip=True),
                "公表日": cols[4].get_text(strip=True),
                "詳細": cols[5].find("a")["href"]
            })

    return pd.DataFrame(results)

# Streamlit UI
st.title("日米臨床試験同時検索アプリ")

jp_condition = st.text_input("疾患名（日本語）", "肺がん")
jp_terms = st.text_input("その他のキーワード（日本語）", "ROS1")
location_jp = st.text_input("地域（日本語）", "日本")

if st.button("検索"):
    with st.spinner("翻訳中..."):
        condition_en = extract_english(translate_to_english(jp_condition))
        terms_en = extract_english(translate_to_english(jp_terms))
        location_en = extract_english(translate_to_english(location_jp))

    st.subheader("ClinicalTrials.govの検索結果")
    data = fetch_clinical_trials(condition_en, terms_en, location_en)
    studies = data.get("studies", [])
    if not studies:
        st.warning("該当する米国の試験は見つかりませんでした。")
    else:
        results = []
        for study in studies:
            protocol = study.get("protocolSection", {})
            results.append({
                "試験ID": protocol.get("identificationModule", {}).get("nctId", ""),
                "試験名": protocol.get("identificationModule", {}).get("officialTitle", ""),
                "ステータス": protocol.get("statusModule", {}).get("overallStatus", ""),
                "開始日": protocol.get("statusModule", {}).get("startDateStruct", {}).get("startDate", ""),
                "場所": protocol.get("locationsModule", {}).get("locations", [{}])[0].get("locationFacility", ""),
                "リンク": f'https://clinicaltrials.gov/study/{protocol.get("identificationModule", {}).get("nctId", "")}'
            })
        df_clinical = pd.DataFrame(results)
        st.dataframe(df_clinical)

        csv = df_clinical.to_csv(index=False).encode('utf-8')
        st.download_button("ClinicalTrials.govの結果をCSVダウンロード", data=csv, file_name="clinical_trials.csv", mime="text/csv")

    st.subheader("jRCTの検索結果")
    df_jrct = search_jrct(jp_condition, jp_terms)
    if not df_jrct.empty:
        st.dataframe(df_jrct)
        csv_jrct = df_jrct.to_csv(index=False).encode('utf-8')
        st.download_button("jRCTの結果をCSVダウンロード", data=csv_jrct, file_name="jrct_trials.csv", mime="text/csv")
    else:
        st.warning("該当する日本の試験は見つかりませんでした。")
