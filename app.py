from flask import Flask, request, render_template_string, jsonify, send_file
import re
from time import sleep
import csv
import requests
from bs4 import BeautifulSoup
import threading
import io
import json

app = Flask(__name__)

# スクレイピングの進捗状況を保持するグローバル変数
# スレッド間で共有するため、threading.Lock で保護する
scraping_status = {
    'status': 'idle',  # 'idle', 'in_progress', 'finished'
    'total_items': 0,
    'scraped_items': 0,
    'total_pages': 0,
    'scraped_pages': 0,
    'csv_data': None,
}
status_lock = threading.Lock()

# フロントエンドのHTMLテンプレート
# プログレスバーと進捗メッセージを表示
TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BUYMA スクレイピングアプリ</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { font-family: 'Inter', sans-serif; }
    </style>
</head>
<body class="bg-gray-100 flex items-center justify-center min-h-screen">
    <div class="bg-white p-8 rounded-2xl shadow-xl max-w-lg w-full">
        <h1 class="text-3xl font-bold text-center mb-6 text-gray-800">BUYMA スクレイピングアプリ</h1>
        <div id="controls" class="flex justify-center">
            <button id="start-btn" class="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-6 rounded-lg shadow-lg transition-transform transform hover:scale-105">
                スクレイピング開始
            </button>
        </div>

        <div id="progress-container" class="mt-8 hidden">
            <div class="flex justify-between items-center mb-2">
                <span class="text-sm font-semibold text-gray-700">ページ進捗:</span>
                <span id="page-progress-text" class="text-sm font-semibold text-gray-700">0 / 0</span>
            </div>
            <div class="w-full bg-gray-200 rounded-full h-4">
                <div id="page-progress-bar" class="bg-blue-500 h-4 rounded-full transition-all duration-500" style="width: 0%"></div>
            </div>

            <div class="flex justify-between items-center mt-4 mb-2">
                <span class="text-sm font-semibold text-gray-700">商品進捗:</span>
                <span id="item-progress-text" class="text-sm font-semibold text-gray-700">0 / 0</span>
            </div>
            <div class="w-full bg-gray-200 rounded-full h-4">
                <div id="item-progress-bar" class="bg-green-500 h-4 rounded-full transition-all duration-500" style="width: 0%"></div>
            </div>

            <div id="status-message" class="mt-4 text-center text-gray-600 italic">準備完了</div>
        </div>

        <div id="download-container" class="flex justify-center mt-8 hidden">
            <a id="download-link" href="/download" class="bg-green-600 hover:bg-green-700 text-white font-bold py-3 px-6 rounded-lg shadow-lg transition-transform transform hover:scale-105">
                CSVダウンロード
            </a>
        </div>
    </div>

    <script>
        const startBtn = document.getElementById('start-btn');
        const progressContainer = document.getElementById('progress-container');
        const pageProgressBar = document.getElementById('page-progress-bar');
        const pageProgressText = document.getElementById('page-progress-text');
        const itemProgressBar = document.getElementById('item-progress-bar');
        const itemProgressText = document.getElementById('item-progress-text');
        const statusMessage = document.getElementById('status-message');
        const downloadContainer = document.getElementById('download-container');
        let progressInterval;

        startBtn.addEventListener('click', async () => {
            // ボタンを無効化
            startBtn.disabled = true;
            startBtn.classList.add('bg-gray-400');
            startBtn.classList.remove('bg-blue-600', 'hover:bg-blue-700');
            statusMessage.textContent = 'スクレイピングを開始します...';

            // 進捗コンテナを表示
            progressContainer.classList.remove('hidden');
            downloadContainer.classList.add('hidden');
            pageProgressBar.style.width = '0%';
            pageProgressText.textContent = '0 / 0';
            itemProgressBar.style.width = '0%';
            itemProgressText.textContent = '0 / 0';

            // スクレイピング開始リクエストを送信
            try {
                const response = await fetch('/scrape', { method: 'POST' });
                const result = await response.json();
                statusMessage.textContent = result.message;

                // 進捗更新のために定期的にサーバーをポーリング
                progressInterval = setInterval(updateProgress, 1000);
            } catch (error) {
                statusMessage.textContent = 'エラーが発生しました: ' + error.message;
            }
        });

        async function updateProgress() {
            try {
                const response = await fetch('/progress');
                const status = await response.json();

                // ページ進捗の更新
                if (status.total_pages > 0) {
                    const pageProgress = (status.scraped_pages / status.total_pages) * 100;
                    pageProgressBar.style.width = `${pageProgress}%`;
                    pageProgressText.textContent = `${status.scraped_pages} / ${status.total_pages}`;
                }

                // 商品進捗の更新
                if (status.total_items > 0) {
                    const itemProgress = (status.scraped_items / status.total_items) * 100;
                    itemProgressBar.style.width = `${itemProgress}%`;
                    itemProgressText.textContent = `${status.scraped_items} / ${status.total_items}`;
                }

                if (status.status === 'in_progress') {
                    if (status.scraped_pages < status.total_pages) {
                         statusMessage.textContent = `商品リストをスクレイピング中 (${status.scraped_pages}/${status.total_pages}ページ)...`;
                    } else {
                         statusMessage.textContent = `商品詳細をスクレイピング中 (${status.scraped_items}/${status.total_items})...`;
                    }
                } else if (status.status === 'finished') {
                    clearInterval(progressInterval);
                    statusMessage.textContent = 'スクレイピングが完了しました！';
                    downloadContainer.classList.remove('hidden');
                    // ボタンを再有効化
                    startBtn.disabled = false;
                    startBtn.classList.remove('bg-gray-400');
                    startBtn.classList.add('bg-blue-600', 'hover:bg-blue-700');
                }
            } catch (error) {
                clearInterval(progressInterval);
                statusMessage.textContent = '進捗の取得中にエラーが発生しました。';
            }
        }
    </script>
</body>
</html>
"""


# トップページを表示
@app.route("/")
def index():
    """
    スクレイピングを開始するためのトップページを表示します。
    """
    return render_template_string(TEMPLATE)


# スクレイピングを開始するエンドポイント
@app.route("/scrape", methods=["POST"])
def scrape():
    """
    スクレイピングをバックグラウンドスレッドで開始し、クライアントに進捗開始を通知します。
    """
    with status_lock:
        if scraping_status['status'] == 'in_progress':
            return jsonify({'message': 'スクレイピングは既に進行中です。'}), 409

        # ステータスをリセット
        scraping_status['status'] = 'in_progress'
        scraping_status['total_items'] = 0
        scraping_status['scraped_items'] = 0
        scraping_status['total_pages'] = 0
        scraping_status['scraped_pages'] = 0
        scraping_status['csv_data'] = None

    # 別スレッドでスクレイピング関数を実行
    threading.Thread(target=start_scraping).start()
    return jsonify({'message': 'スクレイピングを開始しました。進捗を確認してください。'})


# 進捗状況を取得するエンドポイント
@app.route("/progress")
def get_progress():
    """
    現在のスクレイピングの進捗状況を返します。
    """
    with status_lock:
        return jsonify(scraping_status)


# CSVファイルをダウンロードするエンドポイント
@app.route("/download")
def download_csv():
    """
    完了したスクレイピング結果のCSVファイルを返します。
    """
    with status_lock:
        if scraping_status['status'] != 'finished' or not scraping_status['csv_data']:
            return "スクレイピングが完了していません。", 404

        csv_buffer = io.BytesIO(scraping_status['csv_data'].encode('utf-8-sig'))

        return send_file(
            csv_buffer,
            mimetype='text/csv',
            as_attachment=True,
            download_name='ChasePrice.csv'
        )


def start_scraping():
    """
    実際のスクレイピング処理。
    進捗をグローバル変数に定期的に更新します。
    """
    try:
        base_url = 'https://www.buyma.com/buyer/5824366'
        headers = {"User-Agent": "Mozilla/5.0"}

        # 最終ページ番号の取得
        last_page = get_last_page(base_url, headers)
        with status_lock:
            scraping_status['total_pages'] = last_page

        # 商品リストのスクレイピング
        item_list = scrape_item_list(base_url, last_page, headers)

        # スクリーピングする商品総数を設定
        with status_lock:
            scraping_status['total_items'] = len(item_list)

        # 商品詳細のスクレイピング
        final_data = scrape_item_details(item_list, headers)

        # CSVデータをメモリ上で生成
        csv_buffer = io.StringIO()
        if final_data:
            keys = final_data[0].keys()
            writer = csv.DictWriter(csv_buffer, fieldnames=keys)
            writer.writeheader()
            writer.writerows(final_data)

        # CSVデータをグローバル変数に保存し、ステータスを更新
        with status_lock:
            scraping_status['csv_data'] = csv_buffer.getvalue()
            scraping_status['status'] = 'finished'

    except Exception as e:
        print(f"スクレイピング中にエラーが発生しました: {e}")
        with status_lock:
            scraping_status['status'] = 'error'


def get_last_page(url, headers):
    """
    指定されたURLから最終ページ番号を取得する。
    """
    try:
        res = requests.get(url, headers=headers, timeout=20)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, 'html.parser')

        # 最終ページ番号のセレクターを修正
        last_page_element = soup.select('a[class="box"]')[-1]
        if last_page_element and 'item' in last_page_element['href']:
            return int(last_page_element['href'].split('_')[1].split('.')[0])
        return 1
    except (IndexError, ValueError):
        return 1


def scrape_item_list(base_url, last_page, headers):
    """
    各ページから商品URLと価格をスクレイピングする。
    """
    item_data = []
    for i in range(1, last_page + 1):
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

        # ページ巡回の進捗を更新
        with status_lock:
            scraping_status['scraped_pages'] += 1

    return item_data


def scrape_item_details(item_data, headers):
    """
    商品の詳細ページからskuと商品名を取得し、データを統合する。
    進捗をグローバル変数に更新します。
    """
    all_items = []
    for item in item_data:
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

        # 進捗を1つ進める
        with status_lock:
            scraping_status['scraped_items'] += 1

        sleep(3)
    return all_items


if __name__ == "__main__":
    app.run(debug=True, port=8080)
