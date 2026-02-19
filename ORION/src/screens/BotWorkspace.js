import Icon from '../components/Icon.js';
import AnalysisView from './AnalysisView.js';

const { useState } = React;

const BotWorkspace = ({ setCurrentScreen }) => {
    const [tradingMode, setTradingMode] = useState('trading'); // Local state for trading mode
    return (
        <div className="flex h-[calc(100vh-64px)] bg-slate-50 overflow-hidden">
            <aside className="w-20 bg-white border-r border-slate-200 flex flex-col items-center py-6 gap-6 shrink-0">
                <div className="w-12 h-12 bg-[#0A2647] rounded-2xl flex items-center justify-center text-white font-black text-xs">WON</div>
                <div className="flex-1 w-full flex flex-col items-center gap-6 mt-4">
                    <div className="p-3 bg-indigo-50 text-indigo-600 rounded-2xl"><Icon name="activity" className="w-6 h-6"/></div>
                    <div className="p-3 text-slate-300"><Icon name="history" className="w-6 h-6"/></div>
                    <div className="p-3 text-slate-300"><Icon name="message-square" className="w-6 h-6"/></div>
                    <div className="p-3 text-slate-300"><Icon name="settings" className="w-6 h-6"/></div>
                </div>
            </aside>
            <div className="flex-1 flex flex-col min-w-0">
                <div className="h-16 border-b border-slate-200 bg-white flex items-center justify-between px-6 shrink-0">
                    <div className="flex items-center gap-4">
                        <div>
                            <h2 className="text-lg font-black text-slate-900 flex items-center gap-2">
                                William O'Neil Bot <span className="bg-emerald-100 text-emerald-600 text-[10px] px-2 py-0.5 rounded-full font-bold">LIVE</span>
                            </h2>
                            <p className="text-xs text-slate-400 font-bold uppercase tracking-tighter">CAN SLIM Growth Strategy</p>
                        </div>
                    </div>
                    <div className="flex bg-slate-100 p-1.5 rounded-2xl border border-slate-200 shadow-inner">
                        <button onClick={() => setTradingMode('trading')} className={`px-5 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 ${tradingMode === 'trading' ? 'bg-white text-slate-900 shadow-md border border-slate-200' : 'text-slate-400'}`}>
                            <Icon name="line-chart" className="w-4 h-4"/> 트레이딩 모드
                        </button>
                        <button onClick={() => setTradingMode('analysis')} className={`px-5 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 ${tradingMode === 'analysis' ? 'bg-white text-indigo-600 shadow-md border border-slate-200' : 'text-slate-400'}`}>
                            <Icon name="file-text" className="w-4 h-4"/> 분석 모드
                        </button>
                    </div>
                </div>
                <div className="flex-1 overflow-y-auto p-6">
                    {tradingMode === 'trading' ? (
                        <div className="h-full flex flex-col gap-6 animate-in">
                            <div className="flex-1 bg-white rounded-[32px] border border-slate-200 shadow-sm flex items-center justify-center relative overflow-hidden group">
                                <div className="text-center relative z-10">
                                    <Icon name="line-chart" className="w-10 h-10 text-slate-300 mx-auto mb-4"/>
                                    <p className="text-slate-400 font-bold text-lg mb-1">TradingView Chart Container</p>
                                </div>
                            </div>
                            <div className="h-64 grid grid-cols-3 gap-6 shrink-0">
                                <div className="col-span-2 bg-white rounded-[32px] border border-slate-200 shadow-sm p-8">
                                    <div className="flex justify-between items-center mb-6">
                                        <h4 className="font-bold text-slate-900">Quick Order Panel</h4>
                                    </div>
                                    <div className="flex gap-6 h-12">
                                        <button className="flex-1 bg-rose-50 text-rose-600 py-3 rounded-2xl font-black border border-rose-100">SELL</button>
                                        <button className="flex-1 bg-emerald-50 text-emerald-600 py-3 rounded-2xl font-black border border-emerald-100">BUY</button>
                                    </div>
                                </div>
                                <div className="bg-slate-900 rounded-[32px] shadow-xl p-8 text-white">
                                    <h4 className="font-bold text-slate-400 text-xs mb-4 uppercase tracking-widest">Active Position</h4>
                                    <div className="text-3xl font-black text-rose-400">-1.42%</div>
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="bg-white rounded-[40px] p-10 border border-slate-200 shadow-sm min-h-full">
                            <div className="flex items-center justify-between mb-10 pb-8 border-b border-slate-100">
                                <div className="flex items-center gap-6">
                                    <div className="w-16 h-16 bg-slate-100 rounded-[24px] flex items-center justify-center border border-slate-200">
                                        <Icon name="bar-chart-2" className="w-8 h-8 text-slate-700"/>
                                    </div>
                                    <div>
                                        <h2 className="text-3xl font-black text-slate-900 tracking-tight">Apple Inc. (AAPL)</h2>
                                        <span className="text-rose-500 font-bold text-xs bg-rose-50 px-2 py-0.5 rounded-md">매수 금지 (AVOID)</span>
                                    </div>
                                </div>
                                <div className="text-right">
                                    <div className="text-4xl font-black text-slate-900">$255.78</div>
                                    <div className="text-rose-500 font-black text-lg">-2.27%</div>
                                </div>
                            </div>
                            <AnalysisView />
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default BotWorkspace;