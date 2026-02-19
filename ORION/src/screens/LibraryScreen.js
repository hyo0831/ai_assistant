import Icon from '../components/Icon.js';

const LibraryScreen = ({ setCurrentScreen }) => (
    <div className="max-w-7xl mx-auto px-6 py-8 animate-in">
        <button onClick={() => setCurrentScreen('home')} className="flex items-center text-slate-400 hover:text-slate-900 mb-6 font-bold text-sm transition-colors">
            <Icon name="chevron-left" className="w-4 h-4 mr-1"/> 메인으로
        </button>
        <div className="text-center mb-12">
            <h2 className="text-3xl font-black text-slate-900 mb-2">Expert Library</h2>
            <p className="text-slate-500">당신의 투자 성향에 맞는 거장의 AI를 선택하세요.</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {[
                { name: "William O'Neil", style: "CAN SLIM & Momentum", color: "bg-[#0A2647] text-white", accent: "text-amber-400" },
                { name: "Warren Buffett", style: "Value & Long-term", color: "bg-[#1C315E] text-white", accent: "text-blue-200" },
                { name: "Jim Simons", style: "Quant & Mathematical", color: "bg-[#2D4263] text-white", accent: "text-emerald-200" }
            ].map((bot, i) => (
                <div key={i} onClick={() => setCurrentScreen('menu1-trading')} className={`aspect-[3/4] rounded-[32px] p-8 flex flex-col justify-between cursor-pointer hover:scale-[1.02] transition-all shadow-2xl relative overflow-hidden ${bot.color}`}>
                    <div className="absolute top-0 right-0 p-6 opacity-10"><Icon name="bot" className="w-32 h-32"/></div>
                    <div>
                        <div className="w-12 h-1 bg-white/30 mb-6 rounded-full"></div>
                        <h3 className="text-3xl font-black leading-tight mb-2 tracking-tight">{bot.name}</h3>
                        <p className={`text-sm font-bold uppercase tracking-widest ${bot.accent}`}>{bot.style}</p>
                    </div>
                    <button className="bg-white/10 backdrop-blur-md border border-white/20 text-white py-4 rounded-2xl font-bold hover:bg-white hover:text-slate-900 transition-all shadow-xl">
                        AI 봇 가동하기
                    </button>
                </div>
            ))}
        </div>
    </div>
);

export default LibraryScreen;