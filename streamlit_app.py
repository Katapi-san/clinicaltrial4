import streamlit as st
import requests
import pandas as pd
import openai
import re
import base64
from bs4 import BeautifulSoup

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

# jRCTをスクレイピングなしで検索する関数
def search_jrct_without_selenium(disease_name, free_keyword):
    base_url = "https://jrct.mhlw.go.jp/search"
    session = requests.Session()

    params = {
        "keyword": disease_name,
        "target": free_keyword,
        "recruitmentStatus": "2"  # 募集中
    }

    response = session.get(base_url, params=params)

    if response.status_code != 200:
        return pd.DataFrame(), f"HTTPエラー: {response.status_code}"

    soup = BeautifulSoup(response.content, "html.parser")
    rows = soup.select("table.table-search tbody tr")

    if not rows:
        return pd.DataFrame(), "検索結果が見つかりませんでした。"

    results = []
    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 6:
            continue
        link = cols[5].find("a")["href"] if cols[5].find("a") else ""
        results.append({
            "臨床研究実施計画番号": cols[0].text.strip(),
            "研究の名称": cols[1].text.strip(),
            "対象疾患名": cols[2].text.strip(),
            "研究の進捗状況": cols[3].text.strip(),
            "公表日": cols[4].text.strip(),
            "詳細": f"https://jrct.mhlw.go.jp{link}" if link.startswith("/") else link
        })

    return pd.DataFrame(results), None

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
                "リンク": f'https://clinicaltrials.gov/study/{protocol.get("identificationModule", {}).get("nctId", "")}'}
            )
        df_clinical = pd.DataFrame(results)
        st.dataframe(df_clinical)

        csv = df_clinical.to_csv(index=False).encode('utf-8')
        st.download_button("ClinicalTrials.govの結果をCSVダウンロード", data=csv, file_name="clinical_trials.csv", mime="text/csv")

    st.subheader("jRCTの検索結果")
    df_jrct, jrct_error = search_jrct_without_selenium(jp_condition, jp_terms)
    if jrct_error:
        st.warning(jrct_error)
    elif not df_jrct.empty:
        st.dataframe(df_jrct)
        csv_jrct = df_jrct.to_csv(index=False).encode('utf-8')
        st.download_button("jRCTの結果をCSVダウンロード", data=csv_jrct, file_name="jrct_trials.csv", mime="text/csv")
    else:
        st.warning("該当する日本の試験は見つかりませんでした。")
