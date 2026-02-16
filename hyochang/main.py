"""
윌리엄 오닐 페르소나 투자 어시스턴트 (William O'Neil AI Investment Assistant)

Backward compatibility re-export layer.
All logic lives in core/* and cli.py.
"""
from core.config import *
from core.data_fetcher import *
from core.chart_generator import *
from core.ai_analyzer import *
from core.result_manager import *
from cli import main_v1, main_v2, main_compare, _select_chart_interval, _print_analysis_result, _collect_and_save_feedback

if __name__ == "__main__":
    import cli
    import runpy
    runpy.run_module("cli", run_name="__main__", alter_sys=True)
