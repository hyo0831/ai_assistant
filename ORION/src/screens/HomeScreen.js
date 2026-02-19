import Icon from '../components/Icon.js';

const HomeScreen = ({ setCurrentScreen }) => (
    <div className="max-w-6xl mx-auto px-6 py-12 animate-in">
        <div className="text-center mb-16">
            <h1 className="text-5xl font-black text-slate-900 mb-4 tracking-tight"> 투자 헌팅 시스템 , <span className="text-indigo-600">ORION</span></h1>
            <p className="text-lg text-slate-500 font-medium">시장의 가장 밝은 별처럼, 핵심을 포착하는 압도적 기술력</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div onClick={() => setCurrentScreen('menu1')} className="group bg-white p-8 rounded-[32px] border border-slate-200 shadow-sm hover:shadow-xl hover:border-indigo-300 transition-all cursor-pointer relative overflow-hidden">
                <div className="relative z-10">
                    <div className="w-14 h-14 bg-indigo-600 rounded-2xl flex items-center justify-center mb-6 shadow-lg text-white">
                        <Icon name="library" className="w-7 h-7" />
                    </div>
                    <h3 className="text-2xl font-bold text-slate-900 mb-2">투자 대가 봇 라이브러리</h3>
                    <p className="text-slate-500 text-sm leading-relaxed mb-6">전설적인 투자자들의 철학을 이식받은 AI 봇을 만나보세요.</p>
                    <div className="flex items-center text-indigo-600 font-bold text-sm">
                        라이브러리 입장 <Icon name="arrow-right" className="w-4 h-4 ml-1 group-hover:translate-x-1 transition-transform"/>
                    </div>
                </div>
            </div>

            <div onClick={() => setCurrentScreen('menu2')} className="group bg-white p-8 rounded-[32px] border border-slate-200 shadow-sm hover:shadow-xl hover:border-emerald-300 transition-all cursor-pointer relative overflow-hidden">
                <div className="relative z-10">
                    <div className="w-14 h-14 bg-emerald-600 rounded-2xl flex items-center justify-center mb-6 shadow-lg text-white">
                        <Icon name="cpu" className="w-7 h-7" />
                    </div>
                    <h3 className="text-2xl font-bold text-slate-900 mb-2">AI 티칭 머신</h3>
                    <p className="text-slate-500 text-sm leading-relaxed mb-6">자신만의 매매 기록을 학습시켜 개인 맞춤형 AI를 구축합니다.</p>
                    <div className="flex items-center text-emerald-600 font-bold text-sm">
                        봇 빌더 시작 <Icon name="arrow-right" className="w-4 h-4 ml-1 group-hover:translate-x-1 transition-transform"/>
                    </div>
                </div>
            </div>

            <div onClick={() => setCurrentScreen('menu3')} className="group bg-white p-8 rounded-[32px] border border-slate-200 shadow-sm hover:shadow-xl hover:border-amber-300 transition-all cursor-pointer relative overflow-hidden">
                <div className="relative z-10">
                    <div className="w-14 h-14 bg-amber-500 rounded-2xl flex items-center justify-center mb-6 shadow-lg text-white">
                        <Icon name="search" className="w-7 h-7" />
                    </div>
                    <h3 className="text-2xl font-bold text-slate-900 mb-2">AI 스크리너</h3>
                    <p className="text-slate-500 text-sm leading-relaxed mb-6">자연어 질문만으로 조건에 맞는 급등주를 즉시 찾아냅니다.</p>
                    <div className="flex items-center text-amber-600 font-bold text-sm">
                        스크리닝 시작 <Icon name="arrow-right" className="w-4 h-4 ml-1 group-hover:translate-x-1 transition-transform"/>
                    </div>
                </div>
            </div>
        </div>
    </div>
);

export default HomeScreen;