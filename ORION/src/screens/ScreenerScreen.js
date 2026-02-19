import Icon from '../components/Icon.js';

const ScreenerScreen = ({ setCurrentScreen }) => (
    <div className="max-w-6xl mx-auto px-6 py-12 animate-in">
        <button onClick={() => setCurrentScreen('home')} className="flex items-center text-slate-400 hover:text-slate-900 mb-8 font-bold text-sm">
            <Icon name="chevron-left" className="w-4 h-4 mr-1"/> 홈으로 돌아가기
        </button>
        <div className="grid grid-cols-12 gap-8 h-[650px]">
            <div className="col-span-5 bg-white rounded-[40px] border border-slate-200 shadow-xl p-8 flex flex-col">
                <div className="flex items-center gap-3 mb-8">
                    <div className="w-10 h-10 bg-amber-100 rounded-xl flex items-center justify-center"><Icon name="message-square" className="w-5 h-5 text-amber-600"/></div>
                    <h3 className="font-black text-xl text-slate-900">AI Screener</h3>
                </div>
                <div className="flex-1 mb-6"><div className="bg-slate-100 p-5 rounded-[24px]">안녕하세요! 찾으시는 주도주 조건이 있나요?</div></div>
                <div className="relative">
                    <input type="text" placeholder="검색 조건을 말씀하세요..." className="w-full bg-slate-50 border-2 border-slate-100 rounded-[24px] py-4 px-6 text-sm font-bold"/>
                </div>
            </div>
            <div className="col-span-7 bg-white rounded-[40px] border border-slate-200 p-10">
                <h3 className="font-black text-2xl text-slate-900 mb-8">실시간 스캔 결과</h3>
                <div className="space-y-4">
                    {[{t:"TSLA", n:"Tesla Inc.", p:"$242.60", c:"+4.2%"}, {t:"NVDA", n:"NVIDIA", p:"$124.50", c:"+1.8%"}].map((s,i)=>(
                        <div key={i} className="flex items-center justify-between p-5 bg-white rounded-[24px] border border-slate-100 shadow-sm">
                            <div className="font-black">{s.t}</div>
                            <div className="font-black text-emerald-500">{s.c}</div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    </div>
);

export default ScreenerScreen;