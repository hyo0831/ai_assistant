# main_2.py
# -*- coding: utf-8 -*-
"""
GUI (비동기 분석 + 진행바) + 캔들 차트 표시 버전

요구 반영
- 패턴감지: YOLO(이미지 기반)로 필터링
- 차트: 선차트 -> 캔들스틱
- 파일명: *_2.py

주의
- ultralytics/huggingface_hub 설치 필요 (venv 안에서)
- 최초 실행 시 HuggingFace에서 model.pt 다운로드 시도(네트워크 필요)
"""

from __future__ import annotations

import threading
import queue
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import ttk, messagebox

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Rectangle

from pykrx import stock

from paturn_2 import PATTERN_REGISTRY, safe_download_yf, _get_series


# =========================
# 종목 필터
# =========================
def is_preferred_share(name: str) -> bool:
    if not name:
        return True
    name = name.strip()
    if "(우)" in name:
        return True
    if name.endswith("우") or name.endswith("우B") or name.endswith("우C") or name.endswith("우D"):
        return True
    if "우선주" in name:
        return True
    return False


def get_kospi_by_trading_value(target_date: str, top_n: int) -> List[Dict]:
    df = stock.get_market_ohlcv(target_date, market="KOSPI")
    if df is None or df.empty:
        return []
    if "거래대금" not in df.columns:
        return []

    df_sorted = df.sort_values(by="거래대금", ascending=False)
    out: List[Dict] = []
    for code, row in df_sorted.iterrows():
        name = stock.get_market_ticker_name(code)
        if is_preferred_share(name):
            continue
        out.append({
            "code": code,
            "name": name,
            "trading_value": float(row["거래대금"]),
        })
        if len(out) >= top_n:
            break
    return out


# =========================
# 캔들 차트 그리기
# =========================
def plot_candles(ax, df, title: str = "", max_bars: int = 180):
    data = df.copy()
    if len(data) > max_bars:
        data = data.iloc[-max_bars:]

    o = _get_series(data, "Open")
    h = _get_series(data, "High")
    l = _get_series(data, "Low")
    c = _get_series(data, "Close")
    x = range(len(data))
    width = 0.6

    ax.set_title(title, fontsize=11)
    ax.grid(True, alpha=0.2)

    for i in range(len(data)):
        ax.vlines(i, l.iloc[i], h.iloc[i], linewidth=1)

        open_p = float(o.iloc[i])
        close_p = float(c.iloc[i])
        lower = min(open_p, close_p)
        height = abs(close_p - open_p)
        if height == 0:
            height = (float(h.iloc[i]) - float(l.iloc[i])) * 0.01

        rect = Rectangle((i - width/2, lower), width, height)
        ax.add_patch(rect)

    ax.set_xlim(-1, len(data))
    ax.set_xticks([0, len(data)//2, len(data)-1])
    ax.set_xticklabels([data.index[0].strftime("%Y-%m-%d"),
                        data.index[len(data)//2].strftime("%Y-%m-%d"),
                        data.index[-1].strftime("%Y-%m-%d")], rotation=0)
    ax.set_ylabel("Price")


# =========================
# 분석 스레드
# =========================
def analysis_worker(params: Dict, q: "queue.Queue"):
    try:
        target_date: str = params["target_date"]
        months: int = int(params["months"])
        candidate_n: int = int(params["candidate_n"])
        top_n: int = int(params["top_n"])
        pattern_numbers: List[int] = params["pattern_numbers"]
        yolo_conf: float = float(params["yolo_conf"])

        candidates = get_kospi_by_trading_value(target_date, candidate_n)
        if not candidates:
            q.put(("error", "후보 종목을 가져오지 못했음(데이터 비어있음/거래대금 컬럼 없음)."))
            return

        end_dt = datetime.strptime(target_date, "%Y%m%d") + timedelta(days=1)
        start_dt = end_dt - timedelta(days=int(months * 30))

        funcs: List[Tuple[int, object]] = []
        for pno in pattern_numbers:
            f = PATTERN_REGISTRY.get(int(pno))
            if f is not None:
                funcs.append((int(pno), f))
        if not funcs:
            q.put(("error", "선택된 패턴이 없음. 패턴 체크박스를 선택해줘."))
            return

        results: List[Dict] = []
        total = len(candidates)

        for idx, c in enumerate(candidates, start=1):
            ticker_yf = c["code"] + ".KS"
            df = safe_download_yf(ticker_yf, start_dt, end_dt)
            if df is None or df.empty:
                q.put(("progress", idx, total, len(results)))
                continue

            for pno, f in funcs:
                try:
                    res = f(c["name"], ticker_yf, df, yolo_conf=yolo_conf)
                    if res:
                        results.append(res)
                except Exception:
                    pass

            q.put(("progress", idx, total, len(results)))

        if not results:
            q.put(("error", "탐지된 종목이 없음. YOLO conf를 낮추거나(예: 0.15), 기간/후보수를 조정해줘."))
            return

        results.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        q.put(("result", results[:max(1, top_n)]))

    except Exception as e:
        q.put(("error", str(e)))


# =========================
# GUI
# =========================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("KOSPI 패턴 스캐너 (YOLO + 캔들)")
        self.geometry("1250x800")

        self.q: "queue.Queue" = queue.Queue()
        self.worker_thread: Optional[threading.Thread] = None
        self.results: List[Dict] = []

        self._build_ui()
        self._poll_queue()

    def _build_ui(self):
        top = ttk.Frame(self, padding=10)
        top.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(top, text="기준일(YYYYMMDD)").grid(row=0, column=0, sticky="w")
        self.var_date = tk.StringVar(value="20260203")
        ttk.Entry(top, textvariable=self.var_date, width=12).grid(row=0, column=1, padx=6, sticky="w")

        ttk.Label(top, text="기간(개월)").grid(row=0, column=2, sticky="w")
        self.var_months = tk.StringVar(value="8")
        ttk.Entry(top, textvariable=self.var_months, width=6).grid(row=0, column=3, padx=6, sticky="w")

        ttk.Label(top, text="후보 종목 수(거래대금 상위)").grid(row=0, column=4, sticky="w")
        self.var_candidate_n = tk.StringVar(value="100")
        ttk.Entry(top, textvariable=self.var_candidate_n, width=6).grid(row=0, column=5, padx=6, sticky="w")

        ttk.Label(top, text="결과 Top N").grid(row=0, column=6, sticky="w")
        self.var_top_n = tk.StringVar(value="3")
        ttk.Entry(top, textvariable=self.var_top_n, width=6).grid(row=0, column=7, padx=6, sticky="w")

        ttk.Label(top, text="YOLO conf").grid(row=0, column=8, sticky="w")
        self.var_yolo_conf = tk.StringVar(value="0.25")
        ttk.Entry(top, textvariable=self.var_yolo_conf, width=6).grid(row=0, column=9, padx=6, sticky="w")

        pat_box = ttk.Frame(top)
        pat_box.grid(row=1, column=0, columnspan=10, sticky="w", pady=(8, 0))
        ttk.Label(pat_box, text="패턴 선택:").pack(side=tk.LEFT)

        self.var_p1 = tk.BooleanVar(value=True)
        self.var_p2 = tk.BooleanVar(value=True)
        ttk.Checkbutton(pat_box, text="[1] Cup&Handle", variable=self.var_p1).pack(side=tk.LEFT, padx=6)
        ttk.Checkbutton(pat_box, text="[2] Double Bottom", variable=self.var_p2).pack(side=tk.LEFT, padx=6)

        self.btn_run = ttk.Button(top, text="분석 시작", command=self.start_analysis)
        self.btn_run.grid(row=0, column=10, padx=10, sticky="e")

        prog = ttk.Frame(self, padding=(10, 0, 10, 10))
        prog.pack(side=tk.TOP, fill=tk.X)

        self.progress = ttk.Progressbar(prog, mode="determinate")
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.var_status = tk.StringVar(value="대기 중. 설정 후 '분석 시작' 클릭.")
        ttk.Label(prog, textvariable=self.var_status).pack(side=tk.RIGHT, padx=10)

        body = ttk.Frame(self, padding=10)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        left = ttk.Frame(body)
        left.pack(side=tk.LEFT, fill=tk.Y)

        ttk.Label(left, text="신뢰도 목록(클릭)", font=("Apple SD Gothic Neo", 12, "bold")).pack(anchor="w")
        self.listbox = tk.Listbox(left, width=62, height=30)
        self.listbox.pack(fill=tk.Y, pady=8)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        right = ttk.Frame(body)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.fig = plt.Figure(figsize=(8.8, 6.6))
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        bottom = ttk.Frame(self, padding=10)
        bottom.pack(side=tk.BOTTOM, fill=tk.X)
        self.var_info = tk.StringVar(value="종목 선택 시 Pivot/TP/SL 표시")
        ttk.Label(bottom, textvariable=self.var_info).pack(anchor="w")

    def _collect_params(self) -> Dict:
        target_date = self.var_date.get().strip()
        if len(target_date) != 8 or not target_date.isdigit():
            raise ValueError("기준일은 YYYYMMDD 8자리 숫자로 입력. 예: 20260203")

        months = int(self.var_months.get().strip())
        if months <= 0 or months > 60:
            raise ValueError("기간(개월)은 1~60")

        candidate_n = int(self.var_candidate_n.get().strip())
        if candidate_n <= 0 or candidate_n > 500:
            raise ValueError("후보 종목 수는 1~500")

        top_n = int(self.var_top_n.get().strip())
        if top_n <= 0 or top_n > 50:
            raise ValueError("결과 Top N은 1~50")

        yolo_conf = float(self.var_yolo_conf.get().strip())
        if yolo_conf <= 0 or yolo_conf >= 1:
            raise ValueError("YOLO conf는 0~1 사이. 예: 0.25 또는 0.15")

        pattern_numbers: List[int] = []
        if self.var_p1.get():
            pattern pattern_numbers.append(1)
        if self.var_p2.get():
            pattern_numbers.append(2)

        return {
            "target_date": target_date,
            "months": months,
            "candidate_n": candidate_n,
            "top_n": top_n,
            "pattern_numbers": pattern_numbers,
            "yolo_conf": yolo_conf,
        }

    def start_analysis(self):
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showinfo("안내", "이미 분석 중. 끝나면 다시 실행.")
            return

        try:
            params = self._collect_params()
        except Exception as e:
            messagebox.showerror("설정 오류", str(e))
            return

        self.listbox.delete(0, tk.END)
        self.results = []
        self.ax.clear()
        self.canvas.draw()
        self.var_info.set("분석 중...")
        self.var_status.set("분석 시작! (YOLO 모델 로딩/다운로드 포함)")
        self.progress["value"] = 0
        self.progress["maximum"] = 100
        self.btn_run.config(state=tk.DISABLED)

        self.worker_thread = threading.Thread(target=analysis_worker, args=(params, self.q), daemon=True)
        self.worker_thread.start()

    def _poll_queue(self):
        try:
            while True:
                msg = self.q.get_nowait()
                self._handle_msg(msg)
        except queue.Empty:
            pass
        self.after(120, self._poll_queue)

    def _handle_msg(self, msg):
        kind = msg[0]
        if kind == "progress":
            _, done, total, found = msg
            pct = 0 if total == 0 else int(done / total * 100)
            self.progress["value"] = pct
            self.var_status.set(f"진행 {done}/{total} | 발견 {found}건 | {pct}%")

        elif kind == "result":
            _, results_top = msg
            self.results = results_top
            self.listbox.delete(0, tk.END)

            for i, r in enumerate(self.results, start=1):
                self.listbox.insert(
                    tk.END,
                    f"{i}. [{r['pattern_no']}] {r['pattern_name']} | {r['name']} | Conf {r['confidence']}% (YOLO {r.get('yolo_conf',0):.2f})"
                )

            self.var_status.set("완료! 목록 클릭 시 캔들 차트 표시.")
            self.progress["value"] = 100
            self.btn_run.config(state=tk.NORMAL)

            if self.results:
                self.listbox.selection_set(0)
                self.draw_chart(self.results[0])

        elif kind == "error":
            _, text = msg
            self.btn_run.config(state=tk.NORMAL)
            self.var_status.set("오류 발생")
            messagebox.showerror("분석 오류", text)

    def on_select(self, event):
        idxs = self.listbox.curselection()
        if not idxs:
            return
        idx = int(idxs[0])
        if 0 <= idx < len(self.results):
            self.draw_chart(self.results[idx])

    def draw_chart(self, res: Dict):
        try:
            df = res.get("data")
            if df is None or df.empty:
                raise ValueError("차트 데이터가 비어있음")

            self.ax.clear()
            title = (
                f"[{res['pattern_no']}] {res['pattern_name']} - {res['name']} ({res['ticker']})\n"
                f"Conf {res['confidence']}% | Cur {res['current_price']:.2f}"
            )
            plot_candles(self.ax, df, title=title, max_bars=180)

            labels = res.get("labels", {})
            for txt, (x, y) in labels.items():
                # x가 Timestamp이므로, 캔들 x축 index로 변환
                try:
                    # 전체 df를 max_bars로 잘랐을 때를 감안해서 동일한 슬라이싱을 다시 만들기
                    data = df.copy()
                    if len(data) > 180:
                        data = data.iloc[-180:]
                    if x not in data.index:
                        continue
                    xi = int(data.index.get_loc(x))
                    self.ax.scatter([xi], [float(y)], s=55)
                    self.ax.text(xi, float(y), f" {txt}", fontsize=9, va="bottom")
                except Exception:
                    pass

            pivot = res.get("pivot_price")
            tp = res.get("take_profit_price")
            sl = res.get("stop_loss_price")

            if pivot is not None:
                self.ax.axhline(float(pivot), linestyle="--", label=f"Pivot {float(pivot):.2f}")
            if tp is not None:
                self.ax.axhline(float(tp), linestyle="--", label=f"TP {float(tp):.2f}")
            if sl is not None:
                self.ax.axhline(float(sl), linestyle="--", label=f"SL {float(sl):.2f}")

            self.ax.legend(fontsize=9)
            self.canvas.draw()

            self.var_info.set(
                f"Pivot={float(pivot):.2f} | TP={float(tp):.2f} | SL={float(sl):.2f} | "
                f"YOLO label={res.get('yolo_label','?')} ({res.get('yolo_conf',0):.2f})"
            )
        except Exception as e:
            messagebox.showerror("차트 오류", str(e))


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
