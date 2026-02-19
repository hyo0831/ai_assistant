import tkinter as tk
from tkinter import messagebox
import subprocess
import sys
import os

# === 경로 설정 ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ANALYSIS_SCRIPT = os.path.join(BASE_DIR, "hyochang", "main.py")
PYTHON_EXEC = sys.executable  # 현재 venv python 사용

def run_analysis():
    ticker = ticker_entry.get().strip().upper()
    filename = file_entry.get().strip()

    if not ticker:
        messagebox.showerror("입력 오류", "티커(symbol)를 입력하세요.")
        return

    if not filename:
        messagebox.showerror("입력 오류", "파일 저장 이름을 입력하세요.")
        return

    try:
        # main.py를 subprocess로 실행
        subprocess.run(
            [
                PYTHON_EXEC,
                ANALYSIS_SCRIPT,
                "--ticker", ticker,
                "--output", filename
            ],
            check=True
        )

        messagebox.showinfo(
            "완료",
            f"{ticker} 분석 완료\n파일명: {filename}"
        )

    except subprocess.CalledProcessError as e:
        messagebox.showerror("실행 실패", str(e))


# === GUI 구성 ===
root = tk.Tk()
root.title("William O'Neil AI Investment Assistant")
root.geometry("420x220")
root.resizable(False, False)

tk.Label(root, text="Ticker (예: AAPL)", font=("Arial", 11)).pack(pady=(15, 5))
ticker_entry = tk.Entry(root, font=("Arial", 12))
ticker_entry.pack()

tk.Label(root, text="저장 파일 이름 (확장자 제외)", font=("Arial", 11)).pack(pady=(15, 5))
file_entry = tk.Entry(root, font=("Arial", 12))
file_entry.pack()

tk.Button(
    root,
    text="분석 실행",
    font=("Arial", 12, "bold"),
    command=run_analysis,
    bg="#2c7be5",
    fg="white",
    width=18
).pack(pady=20)

root.mainloop()
