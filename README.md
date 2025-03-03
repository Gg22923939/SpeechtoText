# 語音輸入工具 (Voice Input Tool)

這是一個基於 Python 的語音輸入工具，可以將語音實時轉換為文字。

## 功能特點

- 使用快捷鍵（Win+Alt+H）快速啟動語音輸入視窗
- 自動檢測語音並轉換為文字
- 在檢測到靜音1秒後自動輸入文字
- 提供視覺化的錄音狀態顯示
- 支援中文語音識別

## 系統需求

- Python 3.8 或更高版本
- Windows 作業系統
- 麥克風設備

## 安裝步驟

1. 克隆此專案：
```bash
git clone https://github.com/你的用戶名/voice-input-tool.git
cd voice-input-tool
```

2. 創建虛擬環境：
```bash
python -m venv venv
.\venv\Scripts\activate
```

3. 安裝依賴套件：
```bash
pip install -r requirements.txt
```

## 使用方法

1. 啟動虛擬環境：
```bash
.\venv\Scripts\activate
```

2. 運行程式：
```bash
python voice_input_tool.py
```

3. 使用快捷鍵 `Win+Alt+H` 開啟語音輸入視窗

4. 開始說話，程式會自動將語音轉換為文字

5. 停止說話1秒後，文字會自動輸入到當前游標位置

## 注意事項

- 請確保麥克風設備正常運作
- 需要網路連接以使用 Google 語音識別服務
- 建議在安靜的環境中使用

## 授權

本專案採用 MIT 授權條款 - 詳見 [LICENSE](LICENSE) 文件