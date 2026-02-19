#!/usr/bin/env python3
"""
ORION 투자 진단 시스템 - 웹 버전
Flask 기반의 웹 서비스
"""

from flask import Flask, render_template, request, jsonify
from datetime import datetime
import json
import sys
import os
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
load_dotenv()

from modules.survey import load_survey
from modules.ai_report import ai_personality_analyze, PERSONALITY_TYPES
import pandas as pd
import json
from pathlib import Path

# OpenAI API Key .env에서 로드
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# 종목 데이터 경로
DATA_DIR = Path(__file__).parent / "ai-screener-bot" / "backend" / "data"

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# 설문 데이터 캐시
SURVEYS = {}

@app.route('/')
def index():
    """메인 페이지"""
    return render_template('index.html')


@app.route('/api/get-survey/<market_type>')
def get_survey(market_type):
    """특정 시장의 설문 데이터 가져오기"""
    if market_type not in ['korean', 'abroad', 'coin']:
        return jsonify({'error': '잘못된 시장 타입'}), 400

    try:
        if market_type not in SURVEYS:
            SURVEYS[market_type] = load_survey(market_type)

        survey_data = SURVEYS[market_type]
        questions = [
            {
                'id': q.get('id', f'q{i}'),
                'question': q.get('text', q.get('question', '')),
                'options': q.get('options', [])
            }
            for i, q in enumerate(survey_data.get('questions', []), 1)
        ]

        return jsonify({'questions': questions})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/analyze', methods=['POST'])
def analyze():
    """투자 성향 분석"""
    try:
        data = request.json
        market_type = data.get('market_type')
        answers = data.get('answers', {})

        if not market_type or market_type not in ['korean', 'abroad', 'coin']:
            return jsonify({'error': '잘못된 시장 타입'}), 400

        if not OPENAI_API_KEY:
            return jsonify({'error': '.env 파일에 OPENAI_API_KEY를 설정하세요'}), 500

        if not answers:
            return jsonify({'error': '설문 응답이 없습니다'}), 400

        # 답변 형식 변환 (객관식 + 주관식 통합)
        formatted_answers = {}
        for q_id, response in answers.items():
            if isinstance(response, dict):
                # 객관식 + 주관식 조합
                choices = response.get('choices', [])
                custom = response.get('custom', '')
                # 객관식과 주관식을 함께 문자열로 표현
                parts = []
                if choices:
                    parts.append(', '.join(choices))
                if custom:
                    parts.append(f"(추가: {custom})")
                formatted_answers[q_id] = ' '.join(parts) if parts else ''
            else:
                # 이전 형식 호환성
                formatted_answers[q_id] = str(response)

        # AI 분석 실행 (.env에서 로드한 API 키 사용)
        analysis, nickname = ai_personality_analyze(formatted_answers, market_type, OPENAI_API_KEY)

        # 성향 정보 추가
        personality_info = None
        for ptype in PERSONALITY_TYPES.get(market_type, []):
            if ptype['name'] in nickname:
                personality_info = ptype
                break

        result = {
            'analysis': analysis,
            'nickname': nickname,
            'personality_info': personality_info,
            'timestamp': datetime.now().isoformat()
        }

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': f'분석 중 오류: {str(e)}'}), 500


@app.route('/api/personality-types/<market_type>')
def get_personality_types(market_type):
    """성향 타입 정보 조회"""
    if market_type not in PERSONALITY_TYPES:
        return jsonify({'error': '잘못된 시장 타입'}), 400

    types = PERSONALITY_TYPES[market_type]
    return jsonify({'types': types})


# ══════════════════════════════════════════════════════════════════
#  종목 스크리너
# ══════════════════════════════════════════════════════════════════

@app.route('/api/screener/recommend', methods=['POST'])
def screener_recommend():
    """종목 추천 (LLM 기반 동적 조건 생성)"""
    try:
        data = request.json
        market = data.get('market', 'ALL')
        query = data.get('query', '')

        if not query:
            return jsonify({'error': '종목에 대해 질문해주세요'}), 400

        if not market or market == 'ALL':
            return jsonify({'error': '시장을 선택하세요'}), 400

        # CSV 로드
        csv_path = DATA_DIR / "sample_universe.csv"
        if not csv_path.exists():
            return jsonify({'error': '종목 데이터 파일이 없습니다'}), 500

        df = pd.read_csv(csv_path)

        # 시장 필터
        if market != 'ALL':
            df = df[df['market'] == market].copy()

        if len(df) == 0:
            return jsonify({'error': '해당 시장의 종목이 없습니다'}), 400

        # LLM이 쿼리를 분석하여 조건 생성
        conditions, recommendation = _generate_conditions_from_query(query, market, df)

        # 점수 계산
        stocks = _score_stocks(df, conditions)

        # 상위 5개만 반환
        top_stocks = stocks.head(5)

        stocks_list = []
        for idx, row in top_stocks.iterrows():
            stock = {
                'symbol': str(row.get('symbol', '')),
                'name': str(row.get('name', '')),
                'market': str(row.get('market', '')),
                'price': float(row.get('price', 0)) if pd.notna(row.get('price')) else 0,
                'per': float(row.get('per', 0)) if pd.notna(row.get('per')) else 0,
                'pbr': float(row.get('pbr', 0)) if pd.notna(row.get('pbr')) else 0,
                'roe': float(row.get('roe', 0)) if pd.notna(row.get('roe')) else 0,
                'tags': [t.strip() for t in str(row.get('tags', '')).split('|') if t.strip()] if pd.notna(row.get('tags')) else [],
                'score': float(row.get('total_score', 0)),
            }
            stocks_list.append(stock)

        return jsonify({
            'recommendation': recommendation,
            'stocks': stocks_list,
            'conditions': conditions,
            'market': market,
            'count': len(stocks_list)
        })

    except Exception as e:
        return jsonify({'error': f'추천 중 오류: {str(e)}'}), 500


def _generate_conditions_from_query(query, market, df):
    """LLM이 사용자 쿼리를 분석하여 스크리닝 조건 생성"""
    if not OPENAI_API_KEY:
        return [], {'formula_name': '맞춤형 스크리닝', 'description': query}

    market_name = {
        'KOSPI': '코스피',
        'KOSDAQ': '코스닥',
        'NYSE': 'NYSE',
        'NASDAQ': '나스닥',
    }.get(market, market)

    # 데이터 통계 생성
    stats = {
        'per_median': float(df['per'].median()) if 'per' in df.columns else 15,
        'per_low': float(df['per'].quantile(0.3)) if 'per' in df.columns else 10,
        'pbr_median': float(df['pbr'].median()) if 'pbr' in df.columns else 1.0,
        'pbr_low': float(df['pbr'].quantile(0.3)) if 'pbr' in df.columns else 0.7,
        'roe_high': float(df['roe'].quantile(0.7)) if 'roe' in df.columns else 15,
        'volume_high': float(df['avg_volume_20'].quantile(0.7)) if 'avg_volume_20' in df.columns else 1000000,
    }

    system_prompt = (
        "당신은 투자 조건검색 AI입니다. "
        "사용자의 질문을 분석하여 최대 10개의 스크리닝 조건을 생성합니다. "
        "각 조건은 구체적인 수치를 포함해야 합니다. "
        "JSON 형식으로만 응답하세요."
    )

    user_prompt = f"""
사용자 쿼리: {query}
시장: {market_name}

이용 가능한 지표:
- per_low: 저 PER 조건 (권장값: {stats['per_low']:.1f} 이하)
- pbr_low: 저 PBR 조건 (권장값: {stats['pbr_low']:.2f} 이상)
- roe_high: 높은 ROE 조건 (권장값: {stats['roe_high']:.1f}% 이상)
- volume_high: 거래량 많음 (권장값: {stats['volume_high']:,.0f}주 이상)
- dividend_high: 높은 배당율 (수익률 기준)
- momentum_up: 상승 추세 (최근 가격 변화)
- foreign_buy: 외국인 순매수
- tech_trend: 기술 지표 강도

다음 JSON만 응답:
{{
  "formula_name": "공식 이름 (간단하고 직관적)",
  "description": "공식 설명 (1-2문장)",
  "conditions": [
    {{
      "name": "조건명",
      "description": "구체적인 설명 (수치 포함)",
      "type": "지표타입"
    }}
  ]
}}

조건은 최대 10개, 최소 3개 이상 생성하세요.
"""

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=1500
        )
        text = response.choices[0].message.content
        data = json.loads(text)

        conditions = data.get('conditions', [])
        recommendation = {
            'formula_name': data.get('formula_name', '맞춤형 스크리닝'),
            'description': data.get('description', query)
        }

        return conditions, recommendation

    except Exception as e:
        print(f"LLM 오류: {e}")
        return [], {'formula_name': '맞춤형 스크리닝', 'description': query}


def _score_stocks(df, conditions):
    """종목들을 조건에 따라 점수 계산"""
    if df.empty or not conditions:
        df['total_score'] = 50
        return df.sort_values('total_score', ascending=False)

    scores = {}

    for condition_name in df.index:
        score = 0
        condition_count = 0

        for cond in conditions:
            cond_type = cond.get('type', '').lower()

            # PER 기반 조건
            if cond_type == 'per_low' and 'per' in df.columns:
                per_val = df.loc[condition_name, 'per']
                if pd.notna(per_val) and per_val < 20:
                    score += (20 - per_val) / 20 * 10
                condition_count += 1

            # PBR 기반 조건
            elif cond_type == 'pbr_low' and 'pbr' in df.columns:
                pbr_val = df.loc[condition_name, 'pbr']
                if pd.notna(pbr_val) and pbr_val < 1.5:
                    score += (1.5 - pbr_val) / 1.5 * 10
                condition_count += 1

            # ROE 기반 조건
            elif cond_type == 'roe_high' and 'roe' in df.columns:
                roe_val = df.loc[condition_name, 'roe']
                if pd.notna(roe_val) and roe_val > 10:
                    score += min(roe_val / 30 * 10, 10)
                condition_count += 1

            # 거래량 기반 조건
            elif cond_type == 'volume_high' and 'avg_volume_20' in df.columns:
                vol_val = df.loc[condition_name, 'avg_volume_20']
                if pd.notna(vol_val) and vol_val > 1000000:
                    score += min(vol_val / 5000000 * 10, 10)
                condition_count += 1

            # 기타 조건들도 동일하게 처리
            else:
                score += 5
                condition_count += 1

        scores[condition_name] = score / max(condition_count, 1) * 10

    df['total_score'] = df.index.map(scores).fillna(50)
    return df.sort_values('total_score', ascending=False)


@app.route('/api/screener/markets')
def screener_markets():
    """사용 가능한 시장 목록"""
    markets = [
        {'value': 'ALL', 'label': '전체'},
        {'value': 'KOSPI', 'label': '📈 코스피'},
        {'value': 'KOSDAQ', 'label': '📊 코스닥'},
        {'value': 'NASDAQ', 'label': '🌍 나스닥'},
    ]
    return jsonify({'markets': markets})


if __name__ == '__main__':
    app.run(debug=True, port=5001, host='0.0.0.0')
