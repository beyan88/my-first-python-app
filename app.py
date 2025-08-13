from flask import Flask, request, render_template_string, send_file
from flask_socketio import SocketIO, emit
import re
from time import sleep
import csv
import requests
from bs4 import BeautifulSoup
import io

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)


# トップページ
@app.route("/")
def index():
    """
    スクレイピングを開始するためのトップページを表示します。
    """
    return """
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>BUYMA スクレイピングアプリ</title>
        <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; background-color: #f0f2f5; margin: 0; padding: 20px; color: #333; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; text-align: center; }
            .container { background-color: #ffffff; padding: 40px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1); max-width: 600px; width: 100%; }
            h1 { color: #2c3e50; margin-bottom: 20px; }
            p { color: #7f8c8d; line-height: 1.6; }
            button { background-color: #3498db; color: #ffffff; border: none; padding: 15px 30px; font-size: 16px; font-weight: bold; border-radius: 8px; cursor: pointer; transition: background-color 0.3s, transform 0.2s; box-shadow: 0 4px 10px rgba(52, 152, 219, 0.3); }
            button:hover { background-color: #2980b9; transform: translateY(-2px); }
            .progress-container { width: 100%; background-color: #e9ecef; border-radius: 8px; overflow: hidden; margin-top: 20px; display: none; }
            .progress-bar { width: 0%; height: 30px; background-color: #2ecc71; text-align: center; line-height: 30px; color: white; transition: width 0.4s ease; }
            #status { margin-top: 10px; font-weight: bold; color: #555; }
            .download-link { margin-top: 20px; display: none; }
            .download-link a { color: #3498db; text-decoration: none; font-weight: bold; font-size: 18px; }
            .download-link a:hover { text-decoration: underline; }
            .error-message { color: #e74c3c; font-weight: bold; margin-top: 20px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>BUYMA スクレイピングアプリ</h1>
            <p>以下のボタンをクリックしてスクレイピングを開始します。</p>
            <button id="startButton">スクレイピング開始</button>
            <div class="progress-container" id="progressContainer">
                <div class="progress-bar" id="progressBar">0%</div>
            </div>
            <div id="status"></div>
            <div class="download-link" id="downloadLink"></div>
            <div id="errorMessage" class="error-message"></div>
        </div>
        <script>
            document.addEventListener('DOMContentLoaded', () => {
                const socket = io();
                const startButton = document.getElementById('startButton');
                const progressContainer = document.getElementById('progressContainer');
                const progressBar = document.getElementById('progressBar');
                const statusDiv = document.getElementById('status');
                const downloadLinkDiv = document.getElementById('downloadLink');
                const errorMessageDiv = document.getElementById('errorMessage');

                startButton.addEventListener('click', () => {
                    startButton.disabled = true;
                    progressContainer.style.display = 'block';
                    progressBar.style.width = '0%';
                    progressBar.textContent = '0%';
                    statusDiv.textContent = 'スクレイピングを開始します...';
                    downloadLinkDiv.style.display = 'none';
                    errorMessageDiv.textContent = '';

                    fetch('/scrape', { method: 'POST' });
                });

                socket.on('progress', (data) => {
                    const percentage = Math.round((data.current / data.total) * 100);
                    progressBar.style.width = percentage + '%';
                    progressBar.textContent = percentage + '%';
                    statusDiv.textContent = data.message;
                });

                socket.on('complete', (data) => {
                    statusDiv.textContent = data.message;
                    if (data.success) {
                        downloadLinkDiv.innerHTML = `<a href="/download-csv" download>結果をダウンロード</a>`;
                        downloadLinkDiv.style.display = 'block';
                    } else {
                        errorMessageDiv.textContent = 'エラーが発生しました: ' + data.error;
                    }
                    startButton.disabled = false;
                });
            });
        </script>
    </body>
    </html>
    """


# スクレイピングのバックグラウンドタスク
def background_scraper():
    try:
        base_url = 'https://www.buyma.com/buyer/5824366'
        headers = {"User-Agent": "Mozilla/5.0"}

        # 最終ページ番号の取得
        socketio.emit('progress', {'current': 0, 'total': 100, 'message': '最終ページ番号を取得中...'})
        last_page = get_last_page(f'{base_url}/item_1.html', headers)
        last_page = 1  # 1ページに限定

        # 商品リストのスクレイピング
        item_list = []
        for i in range(1, last_page + 1):
            socketio.emit('progress', {'current': 10 + i, 'total': 100,
                                       'message': f'商品リスト ({i}/{last_page}ページ) を取得中...'})
            item_list.extend(scrape_item_list(base_url, last_page, headers))

        # 商品詳細のスクレイピング
        final_data = []
        for i, item in enumerate(item_list):
            socketio.emit('progress',
                          {'current': 20 + int(70 * (i / len(item_list))) if len(item_list) > 0 else 90, 'total': 100,
                           'message': f'商品詳細 ({i + 1}/{len(item_list)}個) を取得中...'})
            final_data.extend(scrape_item_details([item], headers))

        socketio.emit('progress', {'current': 100, 'total': 100, 'message': 'スクレイピングが完了しました。'})

        # CSVデータをメモリ上で生成
        csv_buffer = io.StringIO()
        if final_data:
            keys = final_data[0].keys()
            writer = csv.DictWriter(csv_buffer, fieldnames=keys)
            writer.writeheader()
            writer.writerows(final_data)

        csv_buffer.seek(0)

        # セッションにCSVデータを保存
        app.config['CSV_DATA'] = csv_buffer.getvalue().encode('utf-8-sig')

        socketio.emit('complete', {'success': True, 'message': '完了しました。ダウンロードしてください。'})

    except Exception as e:
        socketio.emit('complete',
                      {'success': False, 'error': str(e), 'message': 'スクレイピング中にエラーが発生しました。'})


# スクレイピング開始のエンドポイント
@app.route("/scrape", methods=["POST"])
def start_scrape():
    """
    非同期でスクレイピングを開始します。
    """
    socketio.start_background_task(background_scraper)
    return 'Scraping started'


# CSVダウンロードエンドポイント
@app.route("/download-csv")
def download_csv():
    """
    生成されたCSVファイルをダウンロードします。
    """
    if 'CSV_DATA' in app.config:
        return send_file(
            io.BytesIO(app.config['CSV_DATA']),
            mimetype='text/csv',
            as_attachment=True,
            download_name='ChasePrice.csv'
        )
    return "No CSV file found.", 404


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
    page_url = f'{base_url}/item_{last_page}.html'
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
        sleep(3)
    return all_items


if __name__ == "__main__":
    # このアプリをローカルで実行します。
    # ターミナルに表示されるURL (例: http://127.0.0.1:5000/) にアクセスしてください。
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True, host='0.0.0.0')
