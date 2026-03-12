"""스크리너 스케줄 잡 함수 모음.

Cloud Scheduler → Cloud Run HTTP 엔드포인트 방식으로 호출됨.
각 함수는 app.py의 /internal/scheduler/* 엔드포인트에서 import하여 사용.

스케줄 (KST 기준):
  금 23:00  job_refresh_universe()     — universe.json 갱신
  일 01:00  job_collect_prices()       — yf.download() 배치 수집
  일 03:00  job_score_fundamentals()   — 상위 120개 펀더멘털 + AI 점수
  월 09:00  job_publish_cache()        — screener_cache.json 최종 확정

중간 저장 파일:
  universe.json              ← 금요일 갱신
  screener_price_stage.json  ← 일요일 가격 수집 완료
  screener_cache.json        ← 월요일 최종 결과 (서빙)
"""
from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from pathlib import Path

# ── 파일 경로 ──────────────────────────────────────────────────────────────────
_BASE = Path(__file__).parent.parent.parent  # integrated_investment_service/
UNIVERSE_FILE = _BASE / "universe.json"
PRICE_STAGE_FILE = _BASE / "screener_price_stage.json"
CACHE_FILE = _BASE / "screener_cache.json"


# ── GCS blob 이름 ──────────────────────────────────────────────────────────────
_BLOB_UNIVERSE    = "screener/universe.json"
_BLOB_PRICE_STAGE = "screener/price_stage.json"
_BLOB_CACHE       = "screener/cache.json"

_BLOB_MAP = {
    UNIVERSE_FILE:    _BLOB_UNIVERSE,
    PRICE_STAGE_FILE: _BLOB_PRICE_STAGE,
    CACHE_FILE:       _BLOB_CACHE,
}


# ── 헬퍼 ───────────────────────────────────────────────────────────────────────
def _load_json(path: Path) -> dict | None:
    from .gcs import load_json as gcs_load_json
    blob = _BLOB_MAP.get(path)
    if blob:
        return gcs_load_json(blob, path)
    try:
        return json.loads(path.read_text()) if path.exists() else None
    except Exception:
        return None


def _save_json(path: Path, data: dict) -> None:
    from .gcs import save_json as gcs_save_json
    blob = _BLOB_MAP.get(path)
    if blob:
        gcs_save_json(blob, path, data)
    else:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


# ── 잡 함수 ───────────────────────────────────────────────────────────────────
def job_refresh_universe() -> None:
    """[금 23:00 KST] S&P500 + NASDAQ 종목 리스트 갱신."""
    print(f"[scheduler] job_refresh_universe 시작 — {datetime.now()}")
    try:
        from .universe import refresh_universe
        data = refresh_universe()
        print(f"[scheduler] universe 갱신 완료: {data.get('total_count')}개")
    except Exception:
        print("[scheduler] job_refresh_universe 실패")
        traceback.print_exc()


def job_collect_prices() -> None:
    """[일 01:00 KST] yf.download() 배치로 전 종목 가격 수집 → screener_price_stage.json."""
    print(f"[scheduler] job_collect_prices 시작 — {datetime.now()}")
    try:
        from .universe import get_us_index_universe
        from .snapshot import collect_snapshots_batch

        symbols = sorted(get_us_index_universe())
        print(f"[scheduler] {len(symbols)}개 종목 수집 시작")

        rows = collect_snapshots_batch(
            symbols,
            bench_6m=0.0,
            bench_12m=0.0,
            batch_size=200,
            pause_sec=10.0,
        )

        payload = {
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "symbol_count": len(rows),
            "rows": rows,
        }
        _save_json(PRICE_STAGE_FILE, payload)
        print(f"[scheduler] job_collect_prices 완료: {len(rows)}개 → {PRICE_STAGE_FILE}")
    except Exception:
        print("[scheduler] job_collect_prices 실패")
        traceback.print_exc()


def job_score_fundamentals() -> None:
    """[일 03:00 KST] 상위 300개 종목 펀더멘털 fetch + AI 점수 산출."""
    print(f"[scheduler] job_score_fundamentals 시작 — {datetime.now()}")
    try:
        import time

        from .snapshot import fetch_symbol_snapshot

        stage = _load_json(PRICE_STAGE_FILE)
        if not stage or not stage.get("rows"):
            print("[scheduler] price_stage 없음, 스킵")
            return

        rows: dict = stage["rows"]

        # rs_raw 기준 상위 300개 선정 (UI 표시 종목 충분히 커버)
        sorted_syms = sorted(rows, key=lambda s: rows[s].get("rs_raw", 0.0), reverse=True)
        top300 = sorted_syms[:300]

        # 벤치마크 재계산 (전체 평균)
        all_rs = [rows[s]["rs_raw"] for s in rows if rows[s].get("rs_raw") is not None]
        bench_6m = sum(all_rs) / len(all_rs) if all_rs else 0.0
        bench_12m = bench_6m

        print(f"[scheduler] 상위 {len(top300)}개 펀더멘털 fetch 중 (1.0초 간격)...")
        enriched: dict[str, dict] = {}
        for i, sym in enumerate(top300):
            try:
                row = fetch_symbol_snapshot(sym, bench_6m, bench_12m, include_info=True)
                enriched[sym] = row if row else rows[sym]
            except Exception:
                enriched[sym] = rows[sym]
            if i < len(top300) - 1:
                time.sleep(1.0)

        for sym in sorted_syms[300:]:
            enriched[sym] = rows[sym]

        stage["rows"] = enriched
        stage["fundamentals_at"] = datetime.now(timezone.utc).isoformat()
        _save_json(PRICE_STAGE_FILE, stage)
        print(f"[scheduler] job_score_fundamentals 완료: top {len(top300)}개 enriched")
    except Exception:
        print("[scheduler] job_score_fundamentals 실패")
        traceback.print_exc()


def job_publish_cache() -> None:
    """[월 09:00 KST] screener_price_stage.json → screener_cache.json 확정 (프론트 서빙)."""
    print(f"[scheduler] job_publish_cache 시작 — {datetime.now()}")
    try:
        stage = _load_json(PRICE_STAGE_FILE)
        if not stage or not stage.get("rows"):
            print("[scheduler] price_stage 없음, 스킵")
            return

        rows_dict: dict = stage["rows"]
        rows_list = sorted(rows_dict.values(), key=lambda r: r.get("rs_raw", 0.0), reverse=True)

        # rs_raw → score (0-99 백분위 변환)
        n = len(rows_list)
        for rank, row in enumerate(rows_list):
            percentile = round((n - 1 - rank) / max(n - 1, 1) * 99)
            row["score"] = percentile
            row.setdefault("ai_score", percentile)
            row.setdefault("rs_score", percentile)

        payload = {
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "dataset_size": len(rows_list),
            "results": rows_list,
            "refresh_policy": "매주 월요일 오전 9시(KST) 갱신",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        _save_json(CACHE_FILE, payload)
        print(f"[scheduler] job_publish_cache 완료: {len(rows_list)}개 → {CACHE_FILE}")
    except Exception:
        print("[scheduler] job_publish_cache 실패")
        traceback.print_exc()
