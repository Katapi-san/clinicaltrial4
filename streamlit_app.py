# ClinicalTrials.gov 検索結果のリンクを追加する関数
def make_clickable_ctgov(nct_id):
    url = f"https://clinicaltrials.gov/ct2/show/{nct_id}"
    return f'<a href="{url}" target="_blank">詳細</a>'

# ClinicalTrials.gov 検索結果の処理
if not studies:
    st.warning("ClinicalTrials.gov で該当する試験は見つかりませんでした。")
else:
    # 件数表示
    st.write(f"**検索件数: {len(studies)} 件**")

    results_ctgov = []
    for study in studies:
        protocol = study.get("protocolSection", {})
        identification = protocol.get("identificationModule", {})
        description = protocol.get("descriptionModule", {})
        status_module = protocol.get("statusModule", {})
        location_module = protocol.get("locationsModule", {})

        loc_list = location_module.get("locations", [])
        loc_str = ", ".join([loc.get("locationFacility", "") for loc in loc_list])

        # Eligibility Criteria は表示しない（取得しない）
        results_ctgov.append({
            "試験ID": identification.get("nctId", ""),
            "試験名": identification.get("officialTitle", ""),
            "Brief Summary": description.get("briefSummary", ""),
            "Locations": loc_str,
            "ステータス": status_module.get("overallStatus", ""),
            "Last Update Posted": status_module.get("lastUpdatePostDateStruct", {}).get("lastUpdatePostDate", ""),
            "詳細": make_clickable_ctgov(identification.get("nctId", ""))
        })

    df_clinical = pd.DataFrame(results_ctgov)

    # "詳細"列をリンクに変換
    df_clinical['詳細'] = df_clinical['詳細'].apply(lambda x: x)

    # 表示
    st.write(df_clinical.to_html(escape=False, index=False), unsafe_allow_html=True)

    # CSV ダウンロードボタン
    csv_ct = df_clinical.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="ClinicalTrials.govの結果をCSVでダウンロード",
        data=csv_ct,
        file_name="clinical_trials.csv",
        mime="text/csv"
    )
