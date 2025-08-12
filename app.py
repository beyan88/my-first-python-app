from flask import Flask, request, render_template_string, send_file
import re
from time import sleep
import csv
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
import os
import io

app = Flask(__name__)


# トップページ
@app.route("/")
def index():
    """
    スクレイピングを開始するためのトップページを表示します。
    """
    return """
    <h1>BUYMA スクレイピングアプリ</h1>
    <p>以下のボタンをクリックしてスクレイピングを開始します。</p>
    <form action="/scrape" method="post">
        <button type="submit">スクレイピング開始</button>
    </form>
    """


# スクレイピングを実行するページ
@app.route("/scrape", methods=["POST"])
def scrape():
    """
    スクレイピングを実行し、結果をCSVとしてダウンロードできるようにします。
    """
    try:
        # スクリプトのメイン処理をここに統合
        base_url = 'https://www.buyma.com/buyer/5824366'
        headers = {"User-Agent": "Mozilla/5.0"}

        # 最終ページ番号の取得
        last_page = get_last_page(f'{base_url}/item_1.html', headers)
        last_page = 1  # 今回は1ページに限定

        # 商品リストのスクレイピング
        item_list = scrape_item_list(base_url, last_page, headers)

        # 商品詳細のスクレイピング
        final_data = scrape_item_details(item_list, headers)

        # CSVデータをメモリ上で生成
        csv_buffer = io.StringIO()
        if final_data:
            keys = final_data[0].keys()
            writer = csv.DictWriter(csv_buffer, fieldnames=keys)
            writer.writeheader()
            writer.writerows(final_data)

        csv_buffer.seek(0)

        # ファイルとしてダウンロードさせる
        return send_file(
            io.BytesIO(csv_buffer.getvalue().encode('utf-8-sig')),
            mimetype='text/csv',
            as_attachment=True,
            download_name='ChasePrice.csv'
        )

    except Exception as e:
        return f"スクレイピング中にエラーが発生しました: {e}", 500


def get_last_page(url, headers):
    """
    指定されたURLから最終ページ番号を取得する。
    """
    res = requests.get(url, headers=headers, timeout=20)
    res.encoding = res.apparent_encoding
    soup = BeautifulSoup(res.text, 'html.parser')
    try:
        lastpage = int(soup.select('a[class="box"]')[-1]['href'].split('_')[1].split('.')[0])
        return lastpage
    except (IndexError, ValueError):
        return 1


def scrape_item_list(base_url, last_page, headers):
    """
    各ページから商品URLと価格をスクレイピングする。
    """
    item_data = []
    for i in tqdm(range(1, last_page + 1)):
        page_url = f'{base_url}/item_{i}.html'
        res = requests.get(page_url, headers=headers, timeout=20)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, 'html.parser')
        sleep(3)

        for h, j in zip(soup.select('img[class="itemimg"]'),
                        soup.select('p[class="buyeritem_price"]')):
            item_url = 'https://www.buyma.com/item/' + h.get('id').split('_')[1]
            price = re.sub(r'[^0-9.]', '', j.text)
            item_data.append({'itemUrl': item_url, 'price': price})
    return item_data


def scrape_item_details(item_data, headers):
    """
    商品の詳細ページからskuと商品名を取得し、データを統合する。
    """
    all_items = []
    for item in tqdm(item_data):
        res = requests.get(item['itemUrl'], headers=headers, timeout=20)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, 'html.parser')

        try:
            sku = soup.select_one('dd[class="clearfix"]').text.strip()
            item_name = soup.select_one('span[class="itemdetail-item-name"]').text.strip()

            all_items.append({
                'sku': sku,
                'itemName': item_name,
                'itemUrl': item['itemUrl'],
                'price': item['price']
            })
        except AttributeError:
            continue

        sleep(3)
    return all_items


if __name__ == "__main__":
    app.run(debug=True)
