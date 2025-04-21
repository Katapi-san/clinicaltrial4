import streamlit as st
import urllib.parse
import openai

# =============================
# ChatGPT APIを使用して翻訳する関数
# =============================
def translate_text(text: str, model: str = "gpt-4o-mini") -> str:
    """
    ChatGPT APIを使用して日本語テキストを英語に翻訳する関数。
    """
    # StreamlitのSecretsからOpenAI APIキーを読み込み
    openai.api_key = st.secrets["openai_api_key"]

    prompt = f"次の文を英語に翻訳してください:\n{text}"
    response = openai.ChatCompletion.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant that translates Japanese to English."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content.strip()

# =============================
# サイト検索用URLを生成する関数
# =============================
def generate_search_urls(disease_jp: str, freeword_jp: str):
    """
    日本語の疾患名 (disease_jp) とフリーワード (freeword_jp) を
    ChatGPT APIで英訳してからjRCTとClinicalTrials.govで検索するURLを作成する。
    """
    # 日本語を英訳
    disease_en = translate_text(disease_jp)  # "Condition"に使用
    freeword_en = translate_text(freeword_jp)  # "Other Terms"に使用

    # jRCT URL 生成
    jRCT_base_url = "https://jrct.niph.go.jp/search"
    jRCT_params = {
        "page": 1,
        "disease": disease_jp,
        "keyword": freeword_jp,
    }
    jRCT_url = f"{jRCT_base_url}?{urllib.parse.urlencode(jRCT_params)}"

    # ClinicalTrials.gov URL 生成
    clinical_base_url = "https://clinicaltrials.gov/ct2/results"
    clinical_params = {
        "cond": disease_en,
        "term": freeword_en,
    }
    clinical_url = f"{clinical_base_url}?{urllib.parse.urlencode(clinical_params)}"

    return jRCT_url, clinical_url

# =============================
# Streamlitアプリ本体
# =============================
def main():
    st.title("jRCT & ClinicalTrials.gov 検索アプリ")

    st.markdown(
        """
        **使い方**  
        1. サイドバーの「App settings > Secrets」に保管したOpenAI APIキーを利用しています。  
        2. 日本語の疾患名とフリーワードを入力してください。  
        3. 「検索リンクを生成」ボタンを押すと、jRCTとClinicalTrials.govの検索リンクが表示されます。  
        """
    )

    with st.form("search_form"):
        disease_jp = st.text_input("疾患名 （日本語）", "")
        freeword_jp = st.text_input("フリーワード （日本語）", "")
        submitted = st.form_submit_button("検索リンクを生成")

    if submitted:
        if not disease_jp and not freeword_jp:
            st.error("疾患名またはフリーワードを入力してください。")
        else:
            with st.spinner("翻訳中..."):
                jRCT_url, clinical_url = generate_search_urls(disease_jp, freeword_jp)
            st.success("検索リンクを作成しました。以下のリンクをクリックしてください。")
            st.markdown(f"[jRCTで検索]({jRCT_url})")
            st.markdown(f"[ClinicalTrials.govで検索]({clinical_url})")

if __name__ == "__main__":
    main()
