import Icon from '../components/Icon.js';

const { useState } = React;

const AnalysisView = () => {
    const [tab, setTab] = useState('종합');
    
    return (
        <div className="space-y-6 animate-in">
            <div className="flex gap-2 border-b border-slate-200 pb-1">
                {['종합', '상세분석', 'CAN SLIM 스코어카드'].map(t => (
                    <button 
                        key={t}
                        onClick={() => setTab(t)}
                        className={`px-6 py-2 text-sm font-bold rounded-t-lg transition-all ${tab === t ? 'text-indigo-600 border-b-2 border-indigo-600 bg-indigo-50/50' : 'text-slate-400 hover:text-slate-600'}`}
                    >
                        {t}
                    </button>
                ))}
            </div>

            <div className="min-h-[500px]">
                {tab === '종합' && (
                    <div className="grid grid-cols-12 gap-6">
                        <div className="col-span-8 space-y-6">
                            <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
                                <h4 className="font-bold flex items-center gap-2 mb-4 text-rose-600"><Icon name="alert-triangle" className="w-5 h-5"/> 추세 및 거래량 경고</h4>
                                <div className="space-y-3">
                                    <div className="p-3 bg-slate-50 rounded-xl text-sm font-medium text-slate-700">🔴 10주 이평선 이탈: 대량 거래를 동반한 하향 돌파</div>
                                    <div className="p-3 bg-slate-50 rounded-xl text-sm font-medium text-slate-700">🔴 매도세 집중: 최근 25일 중 5일 분산일 발생</div>
                                </div>
                            </div>
                            <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
                                <h4 className="font-bold flex items-center gap-2 mb-4 text-indigo-600"><Icon name="history" className="w-5 h-5"/> 과거 패턴 맥락</h4>
                                <div className="h-24 bg-slate-50 rounded-xl flex items-center justify-center text-slate-400 text-sm text-center px-4">
                                    [타임라인 시각화 영역: 컵 생성 후 핸들 돌파 실패 및 하락 전환 패턴]
                                </div>
                            </div>
                        </div>
                        <div className="col-span-4 space-y-6">
                            <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm text-center">
                                <h4 className="font-bold mb-4 text-slate-700">RS 성과</h4>
                                <div className="w-32 h-32 rounded-full border-[12px] border-slate-100 border-t-rose-500 mx-auto mb-4 flex items-center justify-center">
                                    <span className="text-3xl font-black text-slate-800">47</span>
                                </div>
                                <span className="bg-rose-100 text-rose-600 px-3 py-1 rounded-full text-xs font-bold">심각한 후발주</span>
                            </div>
                            <div className="bg-slate-800 text-white p-6 rounded-2xl shadow-lg">
                                <h4 className="font-bold mb-4 flex items-center gap-2 text-slate-200"><Icon name="shield-alert" className="w-4 h-4 text-rose-400"/> 리스크 관리</h4>
                                <div className="mb-2 text-xs text-slate-400">8% 손절가 권장</div>
                                <div className="text-2xl font-black mb-4">$235.32</div>
                                <button className="w-full bg-rose-600 py-2 rounded-lg text-sm font-bold hover:bg-rose-700 transition-colors">매도 알림 설정</button>
                            </div>
                        </div>
                    </div>
                )}

                {tab === '상세분석' && (
                    <div className="grid grid-cols-2 gap-6">
                        {[1,2,3,4,5,6].map(i => (
                            <div key={i} className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm min-h-[200px] flex flex-col items-center justify-center text-slate-400 border-dashed">
                                <span className="font-bold text-lg mb-2 text-slate-300">상세 분석 섹션 {i}</span>
                                <span className="text-xs">[그래프 및 정밀 데이터 배치 예정]</span>
                            </div>
                        ))}
                    </div>
                )}

                {tab === 'CAN SLIM 스코어카드' && (
                    <div className="grid grid-cols-12 gap-6">
                        <div className="col-span-4 bg-white p-8 rounded-2xl border border-slate-200 shadow-sm text-center flex flex-col justify-center">
                            <div className="text-6xl font-black text-slate-900 mb-2">42</div>
                            <div className="text-sm text-slate-400 font-bold tracking-widest mb-6 uppercase">Total Score</div>
                            <div className="bg-rose-50 text-rose-600 font-bold py-2 rounded-xl">Grade: C (Poor)</div>
                        </div>
                        <div className="col-span-8 bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
                            <div className="space-y-4">
                                {['C','A','N','S','L','I','M'].map((char, idx) => (
                                    <div key={char} className="flex items-center gap-4 p-3 hover:bg-slate-50 rounded-lg transition-colors">
                                        <div className="w-8 h-8 bg-indigo-100 text-indigo-700 rounded-lg flex items-center justify-center font-black">{char}</div>
                                        <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                                            <div className={`h-full ${idx < 2 ? 'bg-emerald-500' : 'bg-rose-500'}`} style={{width: `${idx < 2 ? 85 - (idx*10) : 30 + (idx*5)}%`}}></div>
                                        </div>
                                        <span className={`text-xs font-bold w-12 text-right ${idx < 2 ? 'text-emerald-600' : 'text-rose-500'}`}>{idx < 2 ? 'PASS' : 'FAIL'}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default AnalysisView;