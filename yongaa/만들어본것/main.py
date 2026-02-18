# main.py
# -*- coding: utf-8 -*-
"""
요구 반영:
1) GUI를 먼저 띄우고, 분석은 백그라운드(스레드)에서 실행
2) 진행상황 게이지바(Progressbar) + 현재 처리 종목/발견 건수 표시
3) GUI에서 사용자 정의:
   - 검색할 개월수(월 단위)
   - 후보 종목 수(거래대금 상위 N개, KOSPI, (우) 제외)
   - 결과 목록 개수(신뢰도 상위 1~N)
   - 사용할 패턴 번호(체크박스)
   - 기준일(YYYYMMDD)
4) 리스트 클릭 시 차트 + Pivot/TP/SL 라인 + 라벨 표시
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

from pykrx import stock

from paturn import PATTERN_REGISTRY, safe_download_yf, _get_series


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
# 분석 스레드 작업
# =========================
def analysis_worker(params: Dict, q: "queue.Queue"):
    """
    params:
      target_date, months, candidate_n, top_n, pattern_numbers
    queue message types:
      ("progress", done, total, found)
      ("result", results_top)
      ("error", message)
    """
    try:
        target_date: str = params["target_date"]
        months: int = int(params["months"])
        candidate_n: int = int(params["candidate_n"])
        top_n: int = int(params["top_n"])
        pattern_numbers: List[int] = params["pattern_numbers"]

        # 후보 종목
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
                    res = f(c["name"], ticker_yf, df)
                    if res:
                        results.append(res)
                except Exception:
                    # 패턴 분석 실패는 무시하고 계속
                    pass

            q.put(("progress", idx, total, len(results)))

        if not results:
            q.put(("error", "선택한 패턴 기준으로 탐지된 종목이 없음. 기간/후보수/패턴을 조정해줘."))
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
        self.title("KOSPI 패턴 스캐너 (비동기 + 게이지바)")
        self.geometry("1250x780")

        self.q: "queue.Queue" = queue.Queue()
        self.worker_thread: Optional[threading.Thread] = None

        self.results: List[Dict] = []

        self._build_ui()
        self._poll_queue()

    def _build_ui(self):
        # 상단: 설정 영역
        top = ttk.Frame(self, padding=10)
        top.pack(side=tk.TOP, fill=tk.X)

        # 기준일
        ttk.Label(top, text="기준일(YYYYMMDD)").grid(row=0, column=0, sticky="w")
        self.var_date = tk.StringVar(value="20260203")
        ttk.Entry(top, textvariable=self.var_date, width=12).grid(row=0, column=1, padx=6, sticky="w")

        # 기간(월)
        ttk.Label(top, text="기간(개월)").grid(row=0, column=2, sticky="w")
        self.var_months = tk.StringVar(value="8")
        ttk.Entry(top, textvariable=self.var_months, width=6).grid(row=0, column=3, padx=6, sticky="w")

        # 후보 종목 수
        ttk.Label(top, text="후보 종목 수(거래대금 상위)").grid(row=0, column=4, sticky="w")
        self.var_candidate_n = tk.StringVar(value="100")
        ttk.Entry(top, textvariable=self.var_candidate_n, width=6).grid(row=0, column=5, padx=6, sticky="w")

        # 결과 Top N
        ttk.Label(top, text="결과 목록 Top N").grid(row=0, column=6, sticky="w")
        self.var_top_n = tk.StringVar(value="3")
        ttk.Entry(top, textvariable=self.var_top_n, width=6).grid(row=0, column=7, padx=6, sticky="w")

        # 패턴 체크박스
        pat_box = ttk.Frame(top)
        pat_box.grid(row=1, column=0, columnspan=8, sticky="w", pady=(8, 0))

        ttk.Label(pat_box, text="패턴 선택:").pack(side=tk.LEFT)
        self.var_p1 = tk.BooleanVar(value=True)
        self.var_p2 = tk.BooleanVar(value=True)
        ttk.Checkbutton(pat_box, text="[1] Cup&Handle", variable=self.var_p1).pack(side=tk.LEFT, padx=6)
        ttk.Checkbutton(pat_box, text="[2] Double Bottom", variable=self.var_p2).pack(side=tk.LEFT, padx=6)

        # 실행 버튼
        self.btn_run = ttk.Button(top, text="분석 시작", command=self.start_analysis)
        self.btn_run.grid(row=0, column=8, padx=10, sticky="e")

        # 진행바 + 상태
        prog = ttk.Frame(self, padding=(10, 0, 10, 10))
        prog.pack(side=tk.TOP, fill=tk.X)

        self.progress = ttk.Progressbar(prog, mode="determinate")
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.var_status = tk.StringVar(value="대기 중. 설정 후 '분석 시작'을 누르기.")
        ttk.Label(prog, textvariable=self.var_status).pack(side=tk.RIGHT, padx=10)

        # 본문: 좌(리스트) / 우(차트)
        body = ttk.Frame(self, padding=10)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        left = ttk.Frame(body)
        left.pack(side=tk.LEFT, fill=tk.Y)

        ttk.Label(left, text="신뢰도 목록 (클릭)", font=("Apple SD Gothic Neo", 12, "bold")).pack(anchor="w")
        self.listbox = tk.Listbox(left, width=60, height=28)
        self.listbox.pack(fill=tk.Y, pady=8)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        right = ttk.Frame(body)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.fig = plt.Figure(figsize=(8.8, 6.6))
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # 하단 정보
        bottom = ttk.Frame(self, padding=10)
        bottom.pack(side=tk.BOTTOM, fill=tk.X)
        self.var_info = tk.StringVar(value="종목 선택 시 Pivot/TP/SL 표시")
        ttk.Label(bottom, textvariable=self.var_info).pack(anchor="w")

    def _collect_params(self) -> Dict:
        target_date = self.var_date.get().strip()
        if len(target_date) != 8 or not target_date.isdigit():
            raise ValueError("기준일은 YYYYMMDD 8자리 숫자로 입력해줘. 예: 20260203")

        months = int(self.var_months.get().strip())
        if months <= 0 or months > 60:
            raise ValueError("기간(개월)은 1~60 사이로 입력해줘.")

        candidate_n = int(self.var_candidate_n.get().strip())
        if candidate_n <= 0 or candidate_n > 500:
            raise ValueError("후보 종목 수는 1~500 사이로 입력해줘.")

        top_n = int(self.var_top_n.get().strip())
        if top_n <= 0 or top_n > 50:
            raise ValueError("결과 Top N은 1~50 사이로 입력해줘.")

        pattern_numbers: List[int] = []
        if self.var_p1.get():
            pattern_numbers.append(1)
        if self.var_p2.get():
            pattern_numbers.append(2)

        return {
            "target_date": target_date,
            "months": months,
            "candidate_n": candidate_n,
            "top_n": top_n,
            "pattern_numbers": pattern_numbers,
        }

    def start_analysis(self):
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showinfo("안내", "이미 분석이 진행 중이야. 끝나면 다시 실행해줘.")
            return

        try:
            params = self._collect_params()
        except Exception as e:
            messagebox.showerror("설정 오류", str(e))
            return

        # UI 초기화
        self.listbox.delete(0, tk.END)
        self.results = []
        self.ax.clear()
        self.canvas.draw()
        self.var_info.set("분석 중...")
        self.var_status.set("분석 시작! 다운로드/분석 진행 중...")
        self.progress["value"] = 0
        self.progress["maximum"] = 100

        self.btn_run.config(state=tk.DISABLED)

        # 백그라운드 스레드 실행
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
                    f"{i}. [{r['pattern_no']}] {r['pattern_name']} | {r['name']} ({r['ticker']}) | Conf {r['confidence']}%"
                )

            self.var_status.set("완료! 목록에서 종목을 클릭하면 차트가 표시됨.")
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

            close = _get_series(df, "Close")

            self.ax.clear()
            self.ax.plot(close.index, close.values, label="Close")
            self.ax.grid(True)

            title = (
                f"[{res['pattern_no']}] {res['pattern_name']} - {res['name']} ({res['ticker']})\n"
                f"Conf {res['confidence']}% | Cur {res['current_price']:.2f}"
            )
            self.ax.set_title(title, fontsize=11)

            labels = res.get("labels", {})
            for txt, (x, y) in labels.items():
                self.ax.scatter([x], [float(y)], s=55)
                self.ax.text(x, float(y), f" {txt}", fontsize=9, va="bottom")

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
                f"패턴: [{res['pattern_no']}] {res['pattern_name']} | "
                f"Pivot={float(pivot):.2f} | TP={float(tp):.2f} | SL={float(sl):.2f}"
            )
        except Exception as e:
            messagebox.showerror("차트 오류", str(e))


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
