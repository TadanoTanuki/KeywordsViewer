import streamlit as st
import os
import re
import csv
from io import BytesIO
import docx
import markdown2
import pdfplumber


# ページのレイアウトをワイドに設定
st.set_page_config(layout="wide")


def highlight_phrase(sentence, phrase, color):
    highlighted_sentence = re.sub(
        re.escape(phrase),
        f'<span style="color: {color};">{phrase}</span>',
        sentence,
        flags=re.IGNORECASE,
    )
    return highlighted_sentence


def split_regular(text, search_string):
# TODO テキストの整形 ウィキペディアなど
    # テキストを改行で分割して段落を取得
    paragraphs = text.split("\n")
    results = []

    for para_index, para in enumerate(paragraphs):
        # 正規表現を使ってセンテンスを分割
        # 句点、感嘆符、疑問符でセンテンスを分ける
        # TODO より精密に
        sentences = re.split(r'(?<=[。！？.?!])\s*', para.strip())
        for sent_index, sent in enumerate(sentences):
            if search_string.lower() in sent.lower():
                results.append((para_index + 1, sent_index + 1, sent))
    return results


def read_txt(file):
    return file.read().decode("utf-8")


def read_docx(file):
    doc = docx.Document(file)
    return "\n".join([para.text for para in doc.paragraphs])


def read_md(file):
    md_content = file.read().decode("utf-8")
    return str(markdown2.markdown(md_content, extras=["strip"]))


def read_pdf(file):
    text = ""
    try:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text
    except Exception as e:
        st.error(f"PDF読み込み中にエラーが発生しました: {str(e)}")
        return ""
    return str(text)


def read_file(file):
    try:
        file_extension = file.name.split(".")[-1].lower()
        if file_extension == "txt":
            return read_txt(file)
        elif file_extension == "pdf":
            return read_pdf(file)
        elif file_extension == "docx":
            return read_docx(file)
        elif file_extension == "md":
            return read_md(file)
        else:
            st.error("対応していないファイル形式です。")
            return None
    except Exception as e:
        st.error(f"ファイル読み込み中にエラーが発生しました: {str(e)}")
        return None


def display_save_buttons(uploaded_file, columns, file_name_input):
    file_name_input = st.text_input("保存ファイル名:", value=file_name_input)
    if st.button("結果を保存"):
        if file_name_input:
            file_name = file_name_input
        elif uploaded_file:
            file_name = os.path.splitext(uploaded_file.name)[0]
        else:
            file_name = "highlighted_sentences"

        # TODO HTMLタグで色情報を付加したいが、それはMarkdownを開くソフトの方で何とかさせることもできる。
        save_format = st.session_state.save_format
        if save_format == "Markdown":
            md_data = save_as_md_table(columns)
            st.download_button(
                label="Markdownファイルとして保存",
                data=md_data,
                file_name=f"{file_name}.md",
                mime="text/markdown"
            )
        elif save_format == "CSV":
            csv_data = save_as_csv(columns)
            st.download_button(
                label="CSVファイルとして保存",
                data=csv_data,
                file_name=f"{file_name}.csv",
                mime="text/csv"
            )


def save_as_md_table(columns):
    md_output = "| No. | " + " | ".join([col["value"] for col in columns]) + " |\n"
    md_output += "|-----|" + "|".join(["-" * len(col["value"]) for col in columns]) + "|\n"

    max_len = max([len(col["results"]) for col in columns])
    for row_index in range(max_len):
        row = [f"{row_index + 1}"]
        for col in columns:
            if row_index < len(col["results"]):
                para, sent_idx, sent = col["results"][row_index]
                cleaned_sentence = sent.replace('\n', '').strip()
                row.append(f"{cleaned_sentence} (¶{para}-{sent_idx})")
            else:
                row.append("")
        md_output += "| " + " | ".join(row) + " |\n"

    return md_output.encode("utf-8")


def save_as_csv(columns):
    output = BytesIO()
    writer = csv.writer(output, encoding='utf-8')

    headers = ["No."] + [col["value"] for col in columns]
    writer.writerow(headers)

    max_len = max([len(col["results"]) for col in columns])
    for row_index in range(max_len):
        row = [row_index + 1]
        for col in columns:
            if row_index < len(col["results"]):
                para, sent_idx, sent = col["results"][row_index]
                cleaned_sentence = sent.replace('\n', '').strip()
                row.append(f"{cleaned_sentence} (¶{para}-{sent_idx})")
            else:
                row.append("")
        writer.writerow(row)

    return output.getvalue()


def search_and_highlight(text, search_string):
    return split_regular(text, search_string)


def main():
    st.title("KeywordsViewer")
    with st.expander("使い方", expanded=False):
        st.write("""
            ##### 【Import】
            1. ［Brouse Files］をクリックし、ファイルをアップロードします。
                - １つずつしかアップロードできませんが、一度アップロードしたファイルはそのままリストに残ります。
                - 不要なものは［×］で消してください。
                - 画面中央のテキストボックスにテキストをコピー＆ペーストすることもできます。
            2. アップロードしたファイルの中から、選択したいファイルを選びます。

            ---

            ##### 【Process】
            3. 検索する文字列を画面中央の［検索ワード］欄に入力してください。
                - 右脇の［＋］を押して、さらにその下に表示される［🗘］を押すと、列が増えてさらに検索するワードを指定することができるようになります。
                - また、不要な列はテキストボックスの下の［－］ボタンを押した後［🗘Update］を押すことで削除することができます。
            4. 検索ボタンをクリックすると、該当する文がハイライトされて表示されます。

            ---

            ##### 【Export】
            5. 好みの保存形式があれば、サイドパネルのプルダウンメニューから選択してください。
                - デフォルトで選択されているMarkdownが開けるアプリは限られています。Excelなどで開きたければ、CSVを選択してください。
            6. 必要に応じて保存ファイル名を入力してください。
                - デフォルトでは、選択中のファイルのファイル名になっています。
            7. ［結果を保存］を押すと、［Markdownファイルとして保存］もしくは［CSVファイルとして保存］のボタンが表示されます。
                - 面倒で申し訳ないですが、さらにこのボタンを押してください。
            """)

    # セッション状態の初期化
    if "uploaded_files" not in st.session_state:
        st.session_state.uploaded_files = []
    if 'file_name_input' not in st.session_state:
        st.session_state.file_name_input = ""
    if "columns" not in st.session_state:
        st.session_state.columns = [
          {"key": f"input_{1}", "color": "red", "value": "", "results": []},
          {"key": f"input_{2}", "color": "blue", "value": "", "results": []}   
        ]     
    if "key_counter" not in st.session_state:
        st.session_state.key_counter = 3  # 初期化カウンタ
    if "save_format" not in st.session_state:
        st.session_state.save_format = "Markdown"

    # サイドパネルにファイルアップロードと保存ボタンを追加
    with st.sidebar:
        uploaded_files = st.file_uploader("ファイルをアップロードしてください", type=["txt", "md", "pdf", "docx"], accept_multiple_files=True)
        if uploaded_files:
            st.session_state.uploaded_files = uploaded_files
            st.session_state.file_name_input = os.path.splitext(uploaded_files[0].name)[0]

        # アップロードしたファイルのリストから選択
        selected_file = st.selectbox("選択中のファイル:", [file.name for file in st.session_state.uploaded_files])

        # 選択したファイル名を保存ファイル名に反映させる
        if selected_file:
            st.session_state.file_name_input = os.path.splitext(selected_file)[0]

        st.session_state.save_format = st.selectbox("保存形式を選択:", ["Markdown", "CSV"])

        # 選択されたファイルをフィルタリング
        current_file = next((file for file in st.session_state.uploaded_files if file.name == selected_file), None)
        if current_file is not None:
            display_save_buttons(current_file, st.session_state.columns, st.session_state.file_name_input)

    # テキスト入力ボックスまたはファイルから読み取ったテキスト
    if st.session_state.uploaded_files and current_file is not None:
        text = read_file(current_file)
    else:
        text = st.text_area("テキストを入力してください:", height=200)

    if text:
        # カラムごとの検索入力と削除ボタンを表示
        cols_input = st.columns([1] * len(st.session_state.columns) + [0.1])

        for i, col in enumerate(st.session_state.columns):
            with cols_input[i]:
                search_string = st.text_input(f"検索ワード{i + 1}", key=col["key"], value=col["value"])
                st.session_state.columns[i]["value"] = search_string

                if st.button("－", key=f"remove_{i}", help=f"削除 カラム{i + 1}"):
                    st.session_state.columns.pop(i)        # 空のボタンを追加して再描画を促す
                    if st.button("🗘Update", key="delete"):
                      pass  # このボタンが押されたときに何もしない

        with cols_input[-1]:
            st.write("")
            st.write("")
            if st.button("＋", key="add", help="カラムを追加"):
                if len(st.session_state.columns) < 20:
                    new_key = f"input_{st.session_state.key_counter}"
                    new_color = [
                        "blue", "green", "purple", "orange", "brown", "pink",
                        "gray", "cyan", "magenta", "lime", "olive", "navy",
                        "maroon", "teal", "yellow", "violet", "indigo",
                        "gold", "coral",
                    ][len(st.session_state.columns) % 20]
                    st.session_state.columns.append(
                        {"key": new_key, "color": new_color, "value": "", "results": []}
                    )
                    st.session_state.key_counter += 1
            # 空のボタンを追加して再描画を促す
            if st.button("🗘", key="update"):
                pass  # このボタンが押されたときに何もしない

        # 検索ボタンを表示
        if st.button("検索"):
            for i, col in enumerate(st.session_state.columns):
                search_string = col["value"]
                if search_string:
                    results = search_and_highlight(text, search_string)
                    st.session_state.columns[i]["results"] = results

        # 出力表示のカラムを生成
        cols_output = st.columns([1] * len(st.session_state.columns) + [0.1])

        for i, col in enumerate(st.session_state.columns):
            with cols_output[i]:
                for para_index, sent_index, sent in col["results"]:
                    highlighted_sent = highlight_phrase(sent, col["value"], col["color"])
                    st.markdown(f"{highlighted_sent} (¶{para_index}-{sent_index})", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
