"""
語音輸入工具
功能：
1. 通過快捷鍵（Ctrl+Alt+V）啟動語音輸入視窗
2. 自動檢測語音並轉換為文字
3. 在檢測到靜音1秒後自動輸入文字
4. 提供視覺化的錄音狀態顯示
"""

import tkinter as tk
from tkinter import ttk, messagebox
import speech_recognition as sr  # 語音識別
import keyboard  # 鍵盤控制
import threading  # 多線程處理
import pyaudio  # 音頻處理
import wave  # 音頻檔案處理
import os
import time
import win32clipboard  # Windows剪貼簿操作
import win32con
import numpy as np  # 數值計算
from queue import Queue, Empty  # 線程間通信
import math  # 數學計算

class RecordButton(tk.Canvas):
    """
    自定義錄音按鈕類
    功能：
    1. 顯示錄音狀態的動態波形
    2. 根據音量大小調整波形效果
    3. 提供點擊控制
    """
    def __init__(self, master, command=None, **kwargs):
        super().__init__(master, **kwargs)
        self.command = command
        self.size = 60  # 按鈕大小
        self.configure(width=self.size, height=self.size, bg='white', highlightthickness=0)
        
        # 初始化動畫參數
        self.wave_points = []  # 波形點
        self.animation_phase = 0  # 動畫相位
        self.is_animating = False  # 動畫狀態
        self.volume_level = 0  # 音量級別
        
        # 繪製初始按鈕
        self.draw_button()
        
        # 綁定點擊事件
        self.bind('<Button-1>', self.on_click)
        
    def draw_button(self):
        """繪製按鈕的方法，包含外圈、波形和內圈"""
        self.delete('all')
        
        center = self.size/2
        padding = 5
        outer_radius = self.size/2 - padding
        
        # 先繪製波形（在最底層）
        if self.is_animating:
            # 波形背景
            self.create_oval(
                padding, padding,
                self.size-padding, self.size-padding,
                fill='#ffeeee', width=0
            )
            self.draw_waves()
        
        # 外圈（中間層）- 使用較淡的顏色和較細的線條
        self.create_oval(
            padding, padding,
            self.size-padding, self.size-padding,
            fill='', outline='#ffcccc', width=1
        )
        
        # 內圈（最上層）- 錄音指示點
        inner_radius = outer_radius * 0.5
        self.create_oval(
            center-inner_radius, center-inner_radius,
            center+inner_radius, center+inner_radius,
            fill='#ff4444', width=0
        )
        
    def draw_waves(self):
        """
        繪製動態波形
        使用三重正弦波疊加產生自然的波形效果
        波形大小根據音量級別動態調整
        """
        center = self.size/2
        max_radius = self.size/2 - 5
        min_radius = max_radius * 0.6
        
        points = []
        num_points = 180  # 波形點數
        for i in range(num_points):
            angle = 2 * math.pi * i / num_points
            # 三重正弦波疊加
            wave = math.sin(angle * 12 + self.animation_phase) * 0.5 + \
                   math.sin(angle * 8 + self.animation_phase * 1.2) * 0.3 + \
                   math.sin(angle * 4 + self.animation_phase * 0.8) * 0.2
            
            # 計算波形半徑
            radius = min_radius + (max_radius - min_radius) * self.volume_level * (0.7 + 0.3 * wave)
            x = center + radius * math.cos(angle)
            y = center + radius * math.sin(angle)
            points.append((x, y))
        
        # 繪製波形
        if len(points) > 2:
            self.create_polygon(
                *[coord for point in points for coord in point],
                fill='#ff8888', width=0
            )
    
    def set_volume(self, volume):
        """設置音量級別，用於調整波形大小"""
        self.volume_level = min(1.0, volume / 300)
    
    def animate(self):
        """執行波形動畫"""
        if self.is_animating:
            self.animation_phase += 0.15
            self.draw_button()
            self.after(20, self.animate)
    
    def start_animation(self):
        """開始波形動畫"""
        self.is_animating = True
        self.volume_level = 0.3
        self.animate()
    
    def stop_animation(self):
        """停止波形動畫"""
        self.is_animating = False
        self.volume_level = 0
        self.draw_button()
    
    def on_click(self, event):
        """處理按鈕點擊事件"""
        if self.command:
            self.command()

class VoiceInputTool:
    """
    語音輸入工具主類
    功能：
    1. 管理錄音和識別過程
    2. 處理音頻輸入和文字輸出
    3. 控制用戶界面
    """
    def __init__(self):
        self.is_recording = False
        self.root = None
        self.record_button = None
        self.recognizer = sr.Recognizer()
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.frames = []  # 儲存音頻幀
        self.last_process_time = time.time()
        self.text_queue = Queue()  # 文字處理佇列
        self.input_thread = None
        
    def set_clipboard_text(self, text):
        """將文字複製到剪貼簿"""
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()
        
    def toggle_window(self):
        """切換視窗顯示狀態"""
        if self.root:
            if self.is_recording:
                self.stop_recording()
            self.root.destroy()
            self.root = None
        else:
            self.create_window()
            
    def create_window(self):
        """創建主視窗和UI元素"""
        self.root = tk.Tk()
        self.root.title("語音輸入")
        
        # 設置視窗大小和位置
        window_width = 300
        window_height = 120
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # 設置視窗樣式
        self.root.configure(bg='white')
        
        # 創建UI元素
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 狀態標籤
        self.status_label = ttk.Label(
            main_frame,
            text="準備就緒",
            font=("Microsoft JhengHei", 10)
        )
        self.status_label.pack(pady=5)
        
        # 錄音按鈕
        self.record_button = RecordButton(
            main_frame,
            command=self.stop_recording,
            width=60,
            height=60
        )
        self.record_button.pack(pady=10)
        
        # 視窗設置
        self.root.attributes('-topmost', True)
        self.root.overrideredirect(True)
        
        # 拖動功能
        self.root.bind('<Button-1>', self.start_move)
        self.root.bind('<B1-Motion>', self.on_move)
        
        # 關閉按鈕
        close_button = ttk.Button(
            self.root,
            text="×",
            width=3,
            command=self.stop_recording
        )
        close_button.place(x=window_width-30, y=5)
        
        # 啟動錄音和文字處理
        self.start_recording()
        self.start_text_input_thread()
        
        self.root.mainloop()
        
    def start_move(self, event):
        """開始視窗拖動"""
        self.x = event.x
        self.y = event.y

    def on_move(self, event):
        """處理視窗拖動"""
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")
        
    def start_text_input_thread(self):
        """啟動文字輸入處理線程"""
        self.input_thread = threading.Thread(target=self.process_text_input, daemon=True)
        self.input_thread.start()
        
    def process_text_input(self):
        """
        處理文字輸入
        功能：
        1. 累積識別到的文字
        2. 在靜音時輸入文字
        3. 處理錯誤情況
        """
        last_input_time = time.time()
        accumulated_text = ""
        
        while self.is_recording:
            try:
                try:
                    text = self.text_queue.get_nowait()
                    if text:
                        accumulated_text += text + " "
                        last_input_time = time.time()
                except Empty:
                    pass
                
                current_time = time.time()
                if accumulated_text and current_time - last_input_time >= 1.0:
                    self.set_clipboard_text(accumulated_text.strip())
                    keyboard.write(accumulated_text.strip())
                    keyboard.send('space')
                    accumulated_text = ""
                    
                time.sleep(0.1)
            except Exception as e:
                print(f"處理文字輸入時發生錯誤：{str(e)}")
                
        if accumulated_text:
            try:
                self.set_clipboard_text(accumulated_text.strip())
                keyboard.write(accumulated_text.strip())
                keyboard.send('space')
            except Exception as e:
                print(f"最終文字輸入時發生錯誤：{str(e)}")
        
    def start_recording(self):
        """
        開始錄音
        功能：
        1. 初始化音頻流
        2. 啟動錄音按鈕動畫
        3. 開始音頻處理線程
        """
        try:
            self.is_recording = True
            self.last_process_time = time.time()
            
            # 設置錄音參數
            self.frames = []
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=44100,
                input=True,
                frames_per_buffer=1024,
                stream_callback=self.audio_callback
            )
            self.stream.start_stream()
            
            # 開始按鈕動畫
            if hasattr(self, 'record_button') and self.record_button:
                self.record_button.start_animation()
            
            # 開始音頻處理線程
            threading.Thread(target=self.process_audio, daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("錯誤", f"開始錄音時發生錯誤：{str(e)}")
            self.is_recording = False
            if self.root:
                self.root.destroy()
                self.root = None
        
    def audio_callback(self, in_data, frame_count, time_info, status):
        """音頻回調函數，用於接收音頻數據"""
        self.frames.append(in_data)
        return (in_data, pyaudio.paContinue)
    
    def detect_silence(self, audio_data, threshold=200):
        """
        檢測靜音
        功能：
        1. 計算音頻振幅
        2. 更新按鈕音量顯示
        3. 判斷是否為靜音
        """
        data = np.frombuffer(audio_data, dtype=np.int16)
        volume = np.abs(data).mean()
        
        if hasattr(self, 'record_button') and self.record_button:
            self.record_button.set_volume(volume)
        
        return volume < threshold
    
    def update_status(self, text):
        """更新狀態標籤文字"""
        if self.root and hasattr(self, 'status_label'):
            self.status_label.config(text=text)
    
    def process_audio(self):
        """
        處理音頻數據
        功能：
        1. 檢測語音活動
        2. 控制錄音狀態
        3. 觸發語音識別
        """
        min_silence_duration = 1.0
        min_chunk_duration = 1.0
        max_chunk_duration = 10
        check_interval = 0.05
        samples_per_second = 44100
        
        silence_start = None
        last_process_size = 0
        accumulated_frames = []
        last_active_time = time.time()
        is_processing = False
        last_status_update = time.time()
        is_listening = False
        
        while self.is_recording:
            if is_processing:
                time.sleep(check_interval)
                continue
                
            current_size = len(self.frames)
            current_time = time.time()
            
            if current_size > last_process_size:
                new_frames = self.frames[last_process_size:]
                audio_data = b''.join(new_frames)
                
                is_silent = self.detect_silence(audio_data)
                
                accumulated_frames.extend(new_frames)
                chunk_duration = (len(accumulated_frames) * 1024) / samples_per_second
                
                if not is_silent:
                    last_active_time = current_time
                    if not is_listening:
                        self.update_status("聆聽中")
                        is_listening = True
                    if silence_start is not None:
                        silence_start = None
                else:
                    if silence_start is None:
                        silence_start = current_time
                        is_listening = False
                
                should_process = False
                
                # 檢查是否需要處理音頻
                if silence_start and (current_time - silence_start >= min_silence_duration):
                    if chunk_duration >= min_chunk_duration:
                        should_process = True
                elif chunk_duration >= max_chunk_duration:
                    should_process = True
                
                if should_process:
                    self.update_status("處理中...")
                    is_processing = True
                    self.process_chunk(accumulated_frames)
                    accumulated_frames = []
                    silence_start = None
                    is_processing = False
                    self.update_status("準備就緒")
                    is_listening = False
                
                last_process_size = current_size
            
            time.sleep(check_interval)
    
    def process_chunk(self, frames):
        """
        處理音頻片段
        功能：
        1. 將音頻數據保存為臨時文件
        2. 使用Google語音識別API進行識別
        3. 將識別結果加入處理佇列
        """
        if not frames:
            return
            
        temp_wav = "temp_recording.wav"
        try:
            wf = wave.open(temp_wav, 'wb')
            wf.setnchannels(1)
            wf.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))
            wf.setframerate(44100)
            wf.writeframes(b''.join(frames))
            wf.close()
            
            with sr.AudioFile(temp_wav) as source:
                audio_data = self.recognizer.record(source)
                try:
                    text = self.recognizer.recognize_google(audio_data, language='zh-TW')
                    if text.strip():
                        print(f"識別到的文字：{text}")
                        self.text_queue.put(text.strip())
                except sr.UnknownValueError:
                    pass
                except Exception as e:
                    print(f"處理語音時發生錯誤：{str(e)}")
        finally:
            if os.path.exists(temp_wav):
                os.remove(temp_wav)
        
    def stop_recording(self):
        """
        停止錄音
        功能：
        1. 關閉音頻流
        2. 停止動畫
        3. 關閉視窗
        """
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            
        self.is_recording = False
        
        if hasattr(self, 'record_button') and self.record_button:
            self.record_button.stop_animation()
            
        if self.root:
            self.root.destroy()
            self.root = None

def main():
    """
    主程式入口
    功能：
    1. 創建語音輸入工具實例
    2. 註冊快捷鍵
    3. 等待用戶操作
    """
    tool = VoiceInputTool()
    keyboard.add_hotkey('ctrl+alt+v', tool.toggle_window)
    keyboard.wait()

if __name__ == "__main__":
    main()
