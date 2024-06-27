# 検索キーワードをこの配列に入れる
query = ["テレビ", "洗濯機", "掃除機","炊飯器","エアコン","冷蔵庫"]

import os
import time
import json
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import re

# 型番を抽出する正規表現パターン
pattern = re.compile(r'(?<!\S)(?![A-Z]+(?:\s|$))(?!\d+[LV](?:\s|$))(?!\d+(?:\s|$))[0-9A-Z\-\(\)]{4,}(?!\S)')

# 1列目から型番を抽出する関数
def extract_model_number(text):
    if isinstance(text, str):
        match = re.search(pattern, text)
        return match.group(0) if match else None
    return None

# strongタグを含む要素を削除する
def remove_strong_tags(html):
    soup = BeautifulSoup(html, 'html.parser')
    for strong in soup.find_all('strong'):
        strong.decompose()
    return soup

# 型番と価格を追加
def extract_special_elements(soup, data):
    model_number = soup.find_all('h2')
    model_number = extract_model_number(model_number)
    if len(model_number) >= 2:
        key = model_number[0].get_text(strip=True)
        value = model_number[1].get_text(strip=True)
        if key:
            data[key] = value

    price = soup.find_all('p')
    if len(price) >= 1:
        key = price[0].get_text(strip=True)
        sibling = price[0].find_next_sibling(string=True)
        value = sibling.strip() if sibling else ""
        if key:
            data[key] = value
    return data
    

# thとtdのペアを取得してキーとバリューにする
def extract_key_value_pairs(soup):
    data = {}
    rows = soup.find_all('tr')
    for row in rows:
        cols = row.find_all(['th', 'td'])
        if len(cols) >= 4:
            key1 = cols[0].get_text(strip=True)
            value1 = cols[1].get_text(strip=True)
            key2 = cols[2].get_text(strip=True)
            value2 = cols[3].get_text(strip=True)
            if key1:
                data[key1] = value1
            if key2:
                data[key2] = value2
        elif len(cols) >= 2:
            key = cols[0].get_text(strip=True)
            value = cols[1].get_text(strip=True)
            if key:
                data[key] = value
    return data

# JSON形式で保存する
def save_as_json(data, output_file):
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# JSONファイルを読み込み、データフレームに変換する
def json_to_dataframe(json_file):
    return pd.read_json(json_file)

# 商品情報を取得する
def get_product_info(driver, page_url, base_url):
    driver.get(page_url)
    html_content = driver.page_source
    soup = BeautifulSoup(html_content, 'html.parser')
    product_info_list = []
    product_containers = soup.find_all('div', class_='p-result_item')

    for product in product_containers:
        a_tag = product.find('a', class_='p-item_visual is-biggerlinkBigger s-biggerlinkHover_alpha')
        name_tag = product.find('p', class_='p-item_name s-biggerlinkHover_underline')
        price_tag = product.find('span', class_='c-num p-item_price_num')

        href = a_tag['href'] if a_tag else 'N/A'
        product_url = href if href.startswith('http') else base_url + href
        product_name = name_tag.get_text(strip=True) if name_tag else 'N/A'
        product_name = extract_model_number(product_name)
        product_price = price_tag.get_text(strip=True) if price_tag else 'N/A'

        product_info_list.append((product_url, product_name, product_price))
    return product_info_list

# 次のページのURLを取得する
def get_next_page_url(driver, page_url):
    driver.get(page_url)
    html_content = driver.page_source
    soup = BeautifulSoup(html_content, 'html.parser')
    next_page_tag = soup.find('li', class_='p-pager_btn p-pager_btn_next')
    if next_page_tag and next_page_tag.find('a'):
        return next_page_tag.find('a')['href']
    return None

# 検索クエリを使用して検索結果のURLを取得する関数
def get_search_url(driver, base_url, search_query):
    try:
        driver.get(base_url)
        search_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "query"))
        )
        search_box.send_keys(search_query)
        print(f"検索クエリ '{search_query}' を入力しました。")
        search_button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "main_search_button"))
        )
        search_button.click()
        print("検索ボタンをクリックしました。")
        current_url = driver.current_url
        print(f"現在のURL: {current_url}")
        return current_url
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        return None

for i in query:
    # 初期ページのURL
    base_url = "https://kakaku.com"
    # 検索クエリを設定
    search_query = str(i)
    print("クエリを読み込みました。")

    # 出力ディレクトリを設定
    output_dir = f'{search_query}spec_pages'
    os.makedirs(output_dir, exist_ok=True)
    print("ディレクトリを設定しました。")

    # Seleniumのセットアップ
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    print("Seleniumをセットアップしました。")

    # 1ページ目に遷移
    search_url = get_search_url(driver, base_url, search_query)
    if search_url is None:
        print("検索結果ページに遷移できませんでした。プログラムを終了します。")
        driver.quit()
        exit()

    print("1ページ目に遷移しました。")

    page_number = 1
    all_data = []

    while True:
        print(f"検索ページにアクセス中: {search_url}")
        product_info_list = get_product_info(driver, search_url, base_url)

        # ページごとの出力ディレクトリを設定
        page_output_dir = os.path.join(output_dir, f'page_{page_number}')
        os.makedirs(page_output_dir, exist_ok=True)

        page_data = []

        for index, (product_url, product_name, product_price) in enumerate(product_info_list):
            print(f"{index + 1}番目の製品情報（ページ {page_number}）:")
            print(f"URL: {product_url}")
            print(f"型番: {product_name}")
            print(f"価格: {product_price}")

            if not product_url.startswith("https://kakaku.com/item"):
                print("製品URLが無効です。次の製品に進みます。")

                # データを構築
                data = {
                    "型番": product_name,
                    "価格": product_price
                }

                page_data.append(data)
                continue

            # 商品ページにアクセス
            driver.get(product_url)

            # 次のページの特定のボタンを探してクリック
            try:
                spec_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, '//a[contains(@href, "spec/#tab")]'))
                )
                spec_button.click()

                # スペックページのURLを取得
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "tbody"))
                )
                spec_url = driver.current_url
                print(f"スペックページのURL: {spec_url}")

                # スペックページのHTMLを取得
                html_content = driver.page_source
                soup = BeautifulSoup(html_content, 'html.parser')

                # データを初期化
                data = {
                    "型番": product_name,
                    "価格": product_price
                }

                # strongタグを含む要素を削除
                soup = remove_strong_tags(html_content)

                # h2タグとpタグの特定の内容を追加
                data = extract_special_elements(soup, data)

                # thとtdのペアを取得してキーとバリューにする
                data.update(extract_key_value_pairs(soup))

                page_data.append(data)
                # 少し待機
                time.sleep(2)  # 2秒待つ

            except Exception as e:
                print(f"エラーが発生しました: {e}")

                # 型番と価格のみを保存
                data = {
                    "型番": product_name,
                    "価格": product_price
                }

                page_data.append(data)

        # ページデータをJSONとして保存
        page_json_file = os.path.join(page_output_dir, f'page_{page_number}.json')
        save_as_json(page_data, page_json_file)
        print(f"ページ {page_number} のデータを保存しました: {page_json_file}")

        # データフレームに変換して追加
        df = json_to_dataframe(page_json_file)
        all_data.append(df)

        # 次のページへのリンクを探す
        next_page_url = get_next_page_url(driver, search_url)
        if next_page_url:
            search_url = next_page_url
            page_number += 1
        else:
            print("次のページが見つかりませんでした。終了します。")
            break

    # すべてのデータを1つのデータフレームに統合
    final_df = pd.concat(all_data, ignore_index=True)

    # CSVファイルとして保存
    csv_filename = f'./all_products_{search_query}.csv'
    final_df.to_csv(csv_filename, index=False, encoding='utf-8')
    print(f"全ての製品情報をCSVファイルとして保存しました: {csv_filename}")

    # ドライバーを閉じる
    driver.quit()

    # 完了メッセージ
    print("スクレイピングが完了しました。")