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

# 英訳結果から英語だけ抽出
def extract_english_phrase(text):
    match = re.search(r'英語で「(.+?)」', text)
    return match.group(1) if match else text

# ClinicalTrials.gov API 呼び出し関数
def fetch_trials(condition):
    url = "https://clinicaltrials.gov/api/v2/studies"
    params = {
        "query.cond": condition,
        "filter.overallStatus": "RECRUITING",
        "query.locn": "Japan"
    }
    r = requests.get(url, params=params)
    if r.status_code != 200:
        st.error(f"APIエラーが発生しました（ステータスコード: {r.status_code}）")
        st.stop()
    return r.json()

# jRCT 検索関数
def search_jrct(disease_name, free_keyword):
    CHROMEDRIVER_PATH = "/usr/bin/chromedriver"
    CHROME_BINARY_PATH = "/usr/bin/chromium"

    options = Options()
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    options.binary_location = CHROME_BINARY_PATH
    options.add_argument("--headless=new")
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
st.title("jRCT & ClinicalTrials.gov 検索アプリ")

jp_term = st.text_input("疾患名・キーワード（日本語）", "肺がん EGFR")

if st.button("検索"):
    # jRCT 検索
    jrct_results = search_jrct(jp_term, jp_term)
    if jrct_results:
        df_jrct = pd.DataFrame(jrct_results)
        st.subheader("🔍 jRCT 検索結果一覧")
        st.dataframe(df_jrct, use_container_width=True)

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
    raw_translation = translate_to_english(jp_term)
    translated_term = extract_english_phrase(raw_translation)

    st.write(f"翻訳結果: {raw_translation}")
    st.write(f"検索に使う英語キーワード: {translated_term}")

    data = fetch_trials(translated_term)

    # 検索結果の整形
    studies = data.get("studies", [])
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
        st.subheader("🔍 ClinicalTrials.gov 検索結果一覧")
        st.dataframe(df_clinical)

        # CSVダウンロードボタン
        csv = df_clinical.to_csv(index=False).encode('utf-8')
        st.download_button("CSVをダウンロード", data=csv, file_name="clinical_trials.csv", mime="text/csv")
