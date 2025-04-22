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
