function fetchStockData() {
    const stockCode = document.getElementById('stock_code').value;
    const closePriceInput = document.getElementById('close_price');
    const dailyChangeInput = document.getElementById('daily_change');

    // 发送 AJAX 请求获取股票数据
    fetch(`/api/get_stock_data?stock_code=${stockCode}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert(data.error);
                closePriceInput.value = '';
                dailyChangeInput.value = '';
            } else {
                closePriceInput.value = data.close_price;
                dailyChangeInput.value = (data.daily_change * 100).toFixed(2) + '%';
            }
        })
        .catch(error => {
            console.error('Error fetching stock data:', error);
            closePriceInput.value = '';
            dailyChangeInput.value = '';
        });
}