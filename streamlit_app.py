import streamlit as st
import pandas as pd
import base64
import time
import requests
import openai
import re

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# OpenAI APIキーを Streamlit Cloud の secrets から取得
client = openai.OpenAI(api_key=st.secrets["openai_api_key"])

# 翻訳関数（ChatGPTを使って日本語→英語）
def translate_to_english(japanese_text):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "あなたは優秀な医療翻訳者です。"},
            {"role": "user", "content": f"以下の医学用語を英語に翻訳してください：{japanese_text}"}
        ]
    )
    return response.choices[0].message.content.strip()

# 英訳からシンプルな英語キーワードを抽出
def extract_english_phrase(text):
    matches = re.findall(r'[A-Za-z0-9+\- ]{3,}', text)
    if matches:
        matches = sorted(matches, key=lambda x: (len(x), x))
        return matches[0].strip()
    return text

# ClinicalTrials.gov API 呼び出し
def fetch_trials(condition, other_terms, location):
    url = "https://clinicaltrials.gov/api/v2/studies"
    params = {
        "query.cond": condition,
        "query.term": other_terms,
        "query.locn": location,
        "filter.overallStatus": "RECRUITING"
    }
    r = requests.get(url, params=params)
    if r.status_code != 200:
        st.error(f"APIエラーが発生しました（ステータスコード: {r.status_code}）")
        st.write("実際のリクエストURL:", r.url)
        st.stop()
    return r.json()

# jRCT 検索関数
def search_jrct(disease_name, free_keyword, location):
    CHROMEDRIVER_PATH = "/usr/bin/chromedriver"
    CHROME_BINARY_PATH = "/usr/bin/chromium"

    options = Options()
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    options.binary_location = CHROME_BINARY_PATH
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    results = []
    try:
        driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=options)
        driver.implicitly_wait(40)

        driver.get("https://jrct.mhlw.go.jp/search")

        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "reg-plobrem-1"))).send_keys(disease_name)
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "demo-1"))).send_keys(free_keyword)
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "reg-address"))).send_keys(location)

        checkbox = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "reg-recruitment-2")))
        if not checkbox.is_selected():
            checkbox.click()

        search_button_element = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, '//button[contains(text(), "検索")]'))
        )
        driver.execute_script("arguments[0].scrollIntoView(true);", search_button_element)
        time.sleep(1)
        search_button_element.click()

        rows = WebDriverWait(driver, 20).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table.table-search tbody tr"))
        )

        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            results.append({
                "臨床研究実施計画番号": cols[0].text.strip(),
                "研究の名称": cols[1].text.strip(),
                "対象疾患名": cols[2].text.strip(),
                "研究の進捗状況": cols[3].text.strip(),
                "公表日": cols[4].text.strip(),
                "詳細": cols[5].find_element(By.TAG_NAME, "a").get_attribute("href")
            })

    except Exception as e:
        st.error(f"Error initializing WebDriver: {str(e)}")

    finally:
        if 'driver' in locals():
            driver.quit()

    return results

# Streamlit アプリ本体
# st.title("jRCT & ClinicalTrials.gov 治験一括検索アプリ")

col1, col2 = st.columns([1, 3])

with col1:
    st.image("Tech0_team_sleep_well_1.jpg", width=180)

with col2:
    st.markdown("<h1 style='font-size: 48px; color: blue;'>jRCT & ClinicalTrials.gov 検索アプリ</h1>", unsafe_allow_html=True)

disease_name = st.text_input("疾患名", "肺がん")
free_keyword = st.text_input("フリーワード", "EGFR")
jp_location = st.text_input("実施場所：東京、大阪 など", "東京")

if st.button("検索"):
    # jRCT 検索
    jrct_results = search_jrct(disease_name, free_keyword, jp_location)
    jrct_count = len(jrct_results)  # Count the number of jRCT results
    st.write(f"jRCT 検索結果: {jrct_count} 件ヒットしました。")
    
    if jrct_results:
        df_jrct = pd.DataFrame(jrct_results)
        st.subheader("🔍 jRCT 検索結果一覧")

        # リンクを含むHTMLを生成
        def make_clickable(val):
            return f'<a href="{val}" target="_blank">詳細</a>'

        # "詳細"列をリンクに変換
        df_jrct['詳細'] = df_jrct['詳細'].apply(make_clickable)

        # HTMLとしてデータフレームを表示
        st.write(df_jrct.to_html(escape=False, index=False), unsafe_allow_html=True)

        # CSVダウンロードリンク生成
        def generate_download_link(dataframe, filename):
            csv = dataframe.to_csv(index=False)
            b64 = base64.b64encode(csv.encode()).decode()
            href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">📥 CSVをダウンロード</a>'
            return href

        st.markdown(generate_download_link(df_jrct, "jrct_results.csv"), unsafe_allow_html=True)
    else:
        st.warning("jRCTの検索結果が見つかりませんでした。")

    # ClinicalTrials.gov 検索
    condition_en_raw = translate_to_english(disease_name)
    other_terms_en_raw = translate_to_english(free_keyword)
    location_en_raw = translate_to_english(jp_location)

    condition_en = extract_english_phrase(condition_en_raw)
    other_terms_en = extract_english_phrase(other_terms_en_raw)
    location_en = extract_english_phrase(location_en_raw)

    st.subheader("翻訳結果")
    st.write(f"Condition: {condition_en_raw} → `{condition_en}`")
    st.write(f"Other Terms: {other_terms_en_raw} → `{other_terms_en}`")
    st.write(f"Location: {location_en_raw} → `{location_en}`")

    data = fetch_trials(condition_en, other_terms_en, location_en)

    studies = data.get("studies", [])
    clinical_count = len(studies)  # Count the number of ClinicalTrials.gov results
    st.write(f"ClinicalTrials.gov 検索結果: {clinical_count} 件ヒットしました。")
    
    if not studies:
        st.warning("ClinicalTrials.govで該当する試験は見つかりませんでした。")
    else:
        results = []
        for study in studies:
            results.append({
                "試験ID": study.get("protocolSection", {}).get("identificationModule", {}).get("nctId", ""),
                "試験名": study.get("protocolSection", {}).get("identificationModule", {}).get("officialTitle", ""),
                "ステータス": study.get("protocolSection", {}).get("statusModule", {}).get("overallStatus", ""),
                "開始日": study.get("protocolSection", {}).get("statusModule", {}).get("startDateStruct", {}).get("startDate", ""),
                "場所": study.get("protocolSection", {}).get("locationsModule", {}).get("locations", [{}])[0].get("locationFacility", ""),
                "リンク": f'https://clinicaltrials.gov/study/{study.get("protocolSection", {}).get("identificationModule", {}).get("nctId", "")}'
            })

        df_clinical = pd.DataFrame(results)

        # Convert URLs to clickable links
        def make_clickable(val):
            return f'<a href="{val}" target="_blank">リンク</a>'

        df_clinical['リンク'] = df_clinical['リンク'].apply(make_clickable)
    
        st.subheader("🔍 ClinicalTrials.gov 検索結果一覧")
        st.write(df_clinical.to_html(escape=False, index=False), unsafe_allow_html=True)

        csv = df_clinical.to_csv(index=False).encode('utf-8')
        st.download_button("CSVをダウンロード", data=csv, file_name="clinical_trials.csv", mime="text/csv")
