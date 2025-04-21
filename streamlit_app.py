import streamlit as st
import urllib.parse
import openai

# =============================
#  ChatGPT APIを使用して翻訳する関数
# =============================
def translate_text(text: str, openai_api_key: str, model: str = "gpt-4o-mini") -> str:
    """
    ChatGPT APIを使用して日本語テキストを英語に翻訳する関数。
    デフォルトモデルを'gpt-4o-mini'とする。
    必要に応じてご利用のモデルに置き換えてください。
    """
    openai.api_key = openai_api_key

    # ChatGPT API に送信するメッセージ内容を作成
    prompt = f"次の文を英語に翻訳してください: {text}"

    response = openai.ChatCompletion.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant that translates Japanese to English."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,  # 必要に応じてトーンを調整
    )

    # 応答から翻訳結果を取り出し
    translated_text = response["choices"][0]["message"]["content"].strip()
    return translated_text

# =============================
#  サイト検索用URLを生成する関数
# =============================
def generate_search_urls(disease_jp: str, freeword_jp: str, openai_api_key: str):
    """
    日本語の疾患名 (disease_jp) とフリーワード (freeword_jp) を
    ChatGPT APIで英訳してからjRCTとClinicalTrials.govで検索するURLを作成する。
    """
    # 1. 疾患名とフリーワードを英訳
    disease_en = translate_text(disease_jp, openai_api_key)  # "Condition"に使用
    freeword_en = translate_text(freeword_jp, openai_api_key)  # "Other Terms"に使用

    # 2. jRCTの検索用URLを作成
    jRCT_base_url = "https://jrct.niph.go.jp/search"
    jRCT_params = {
        "page": 1,
        "disease": disease_jp,    # 疾患名に日本語
        "keyword": freeword_jp,   # フリーワードに日本語
    }
    jRCT_url = f"{jRCT_base_url}?{urllib.parse.urlencode(jRCT_params)}"

    # 3. ClinicalTrials.govの検索用URLを作成
    clinical_base_url = "https://clinicaltrials.gov/ct2/results"
    clinical_params = {
        "cond": disease_en,
        "term": freeword_en,
    }
    clinical_url = f"{clinical_base_url}?{urllib.parse.urlencode(clinical_params)}"

    return jRCT_url, clinical_url

# =============================
#  Streamlitのメインアプリ
# =============================
def main():
    st.title("jRCT & ClinicalTrials.gov 検索アプリ")

    st.markdown("日本語で疾患名とフリーワードを入力すると、自動で英訳して検索結果ページへのリンクを生成します。")

    openai_api_key = st.text_input("OpenAI API Key:", type="password")
    if not openai_api_key:
        st.warning("OpenAI APIキーを入力してください。")
        st.stop()

    disease_jp = st.text_input("疾患名 （日本語）", "")
    freeword_jp = st.text_input("フリーワード （日本語）", "")

    # ボタンがクリックされたら検索URLを生成
    if st.button("検索リンクを生成"):
        if not disease_jp and not freeword_jp:
            st.error("疾患名またはフリーワードを入力してください。")
        else:
            with st.spinner("翻訳中..."):
                jRCT_url, clinical_url = generate_search_urls(disease_jp, freeword_jp, openai_api_key)

            st.success("検索リンクを作成しました。以下のリンクをクリックしてください。")
            st.markdown(f"[jRCTで検索]({jRCT_url})")
            st.markdown(f"[ClinicalTrials.govで検索]({clinical_url})")

if __name__ == "__main__":
    main()
