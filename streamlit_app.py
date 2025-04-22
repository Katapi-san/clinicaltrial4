import streamlit as st
import pandas as pd
import base64
import time
import requests
import re

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import openai

# =====================
# OpenAI API key
# =====================
client = openai.OpenAI(api_key=st.secrets["openai_api_key"])

# =====================
# 日本語→英語翻訳関数
# =====================
def translate_to_english(japanese_text):
    """ChatGPTを使って日本語を英語に翻訳する"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "あなたは優秀な医療翻訳者です。"},
            {"role": "user", "content": f"以下の医学用語を英語に翻訳してください：{japanese_text}"}
        ]
    )
    return response.choices[0].message.content.strip()

# =====================
# 英語の単語を抽出する関数
# =====================
def extract_english_phrase(text):
    """
    英数字とスペースのみで3文字以上連続する箇所を抽出。
    もっとも短いものを優先的に返す。
    """
    matches = re.findall(r'[A-Za-z0-9+\- ]{3,}', text)
    if matches:
        matches = sorted(matches, key=lambda x: (len(x), x))
        return matches[0].strip()
    return text

# =====================
# ClinicalTrials.gov 検索API
# =====================
def fetch_trials(condition, other_terms, location):
    """
    ClinicalTrials.govのAPI v2から情報を取得（Recruitingのみ）。
    condition, other_terms, location は英語で与える。
    """
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

# =====================
# jRCTの検索関数
# =====================
def search_jrct(disease_name, free_keyword, location):
    """
    ChromedriverでjRCTをスクレイピングし、検索結果一覧を取得。
    """
    CHROMEDRIVER_PATH = "/usr/bin/chromedriver"
    CHROME_BINARY_PATH = "/usr/bin/chromium"

    options = Options()
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                         " AppleWebKit/537.36 (KHTML, like Gecko)"
                         " Chrome/122.0.0.0 Safari/537.36")
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

        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "reg-plobrem-1"))
        ).send_keys(disease_name)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "demo-1"))
        ).send_keys(free_keyword)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "reg-address"))
        ).send_keys(location)

        # 募集前~募集終了までチェックをON
        checkbox = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "reg-recruitment-2"))
        )
        if not checkbox.is_selected():
            checkbox.click()

        # 検索ボタンクリック
        search_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, '//button[contains(text(), "検索")]'))
        )
        driver.execute_script("arguments[0].scrollIntoView(true);", search_button)
        time.sleep(1)
        search_button.click()

        # 結果テーブルの行を取得
        rows = WebDriverWait(driver, 20).until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, "table.table-search tbody tr")
            )
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

# =====================================================
# Streamlit アプリ本体
# =====================================================
col1, col2 = st.columns([1, 3])
with col1:
    st.image("Tech0_team_sleep_well_1.jpg", width=180)
with col2:
    st.markdown(
        "<h1 style='font-size: 48px; color: blue;'>jRCT & ClinicalTrials.gov 検索アプリ</h1>",
        unsafe_allow_html=True
    )

# ユーザ入力
disease_name = st.text_input("疾患名", "肺がん")
free_keyword = st.text_input("フリーワード", "EGFR")
jp_location = st.text_input("実施場所：東京、大阪 など", "東京")

# -----------------------------
# 検索ボタンクリック時の処理
# -----------------------------
if st.button("検索"):
    # ===============
    # jRCT 検索
    # ===============
    jrct_results = search_jrct(disease_name, free_keyword, jp_location)
    st.subheader("🔍 jRCT 検索結果一覧")
    if jrct_results:
        st.write(f"**検索件数: {len(jrct_results)} 件**")
        df_jrct = pd.DataFrame(jrct_results)

        # "詳細"列をリンクに変換
        def make_clickable_jrct(val):
            return f'<a href="{val}" target="_blank">詳細</a>'
        df_jrct['詳細'] = df_jrct['詳細'].apply(make_clickable_jrct)

        st.write(df_jrct.to_html(escape=False, index=False), unsafe_allow_html=True)

        # CSVダウンロード
        def generate_download_link(dataframe, filename):
            csv = dataframe.to_csv(index=False)
            b64 = base64.b64encode(csv.encode()).decode()
            return f'<a href="data:file/csv;base64,{b64}" download="{filename}">📥 CSVをダウンロード</a>'

        st.markdown(generate_download_link(df_jrct, "jrct_results.csv"), unsafe_allow_html=True)
    else:
        st.warning("jRCTの検索結果が見つかりませんでした。")

    # ===============
    # ClinicalTrials.gov 検索
    # ===============
    # 1) 日本語→英語翻訳
    disease_name_en_raw = translate_to_english(disease_name)
    free_keyword_en_raw = translate_to_english(free_keyword)
    jp_location_en_raw = translate_to_english(jp_location)

    # 2) シンプル英語キーへの変換
    condition_en = extract_english_phrase(disease_name_en_raw)
    other_terms_en = extract_english_phrase(free_keyword_en_raw)
    location_en = extract_english_phrase(jp_location_en_raw)

    st.subheader("翻訳結果")
    st.write(f"Condition: {disease_name} → `{condition_en}`")
    st.write(f"Other Terms: {free_keyword} → `{other_terms_en}`")
    st.write(f"Location: {jp_location} → `{location_en}`")

    # 3) ClinicalTrials.gov API呼び出し
    data = fetch_trials(condition_en, other_terms_en, location_en)
    studies = data.get("studies", [])

    st.subheader("🔍 ClinicalTrials.gov 検索結果一覧（Eligibility Criteria は表示しません）")
    if not studies:
        st.warning("ClinicalTrials.gov で該当する試験は見つかりませんでした。")
    else:
        st.write(f"**検索件数: {len(studies)} 件**")

        # 結果整理
        results_ctgov = []
        for study in studies:
            protocol = study.get("protocolSection", {})
            identification = protocol.get("identificationModule", {})
            description = protocol.get("descriptionModule", {})
            status_module = protocol.get("statusModule", {})
            location_module = protocol.get("locationsModule", {})

            # nctId をリンク先に活用
            nct_id = identification.get("nctId", "")
            link_url = f"https://clinicaltrials.gov/study/{nct_id}"  # ClinicalTrials.gov 詳細ページ

            # Locations
            loc_list = location_module.get("locations", [])
            loc_str = ", ".join([loc.get("locationFacility", "") for loc in loc_list])

            # Eligibility Criteria は表示しない
            results_ctgov.append({
                "試験ID": nct_id,
                "試験名": identification.get("officialTitle", ""),
                "Brief Summary": description.get("briefSummary", ""),
                "Locations": loc_str,
                "ステータス": status_module.get("overallStatus", ""),
                "Last Update Posted": status_module.get("lastUpdatePostDateStruct", {}).get("lastUpdatePostDate", ""),
                "リンク": link_url
            })

        df_clinical = pd.DataFrame(results_ctgov)

        # -----------------------------
        # 「試験名」「Brief Summary」のカラム幅を広げたい
        # + 表の右端にリンク
        # -----------------------------
        #
        # 1) "リンク" カラムをHTMLリンクに変換
        def make_clickable_ctgov(url):
            return f'<a href="{url}" target="_blank">リンク</a>'
        df_clinical["リンク"] = df_clinical["リンク"].apply(make_clickable_ctgov)

        # 2) カラム幅をCSSで調整する
        custom_css = """
        <style>
        table {
            table-layout: auto !important;
            width: 100% !important;
            border-collapse: collapse;
        }
        th {
            padding: 8px;
            text-align: left;
        }
        td {
            padding: 8px;
            vertical-align: top;
            text-align: left;
        }
        /* 試験名 (2列目) と Brief Summary (3列目) の幅を広げる */
        th:nth-child(2), td:nth-child(2) {
            min-width: 200px;
        }
        th:nth-child(3), td:nth-child(3) {
            min-width: 300px;
        }
        </style>
        """
        # df を HTMLテーブルに変換（HTML埋め込みのため escape=False）
        html_table = df_clinical.to_html(escape=False, index=False)
        st.write(custom_css + html_table, unsafe_allow_html=True)

        # CSV ダウンロード
        csv_ct = df_clinical.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="ClinicalTrials.govの結果をCSVでダウンロード",
            data=csv_ct,
            file_name="clinical_trials.csv",
            mime="text/csv"
        )
