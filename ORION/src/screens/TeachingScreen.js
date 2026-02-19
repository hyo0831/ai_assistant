import Icon from '../components/Icon.js';

const TeachingScreen = ({ setCurrentScreen }) => (
    <div className="max-w-4xl mx-auto px-6 py-12 animate-in">
        <button onClick={() => setCurrentScreen('home')} className="flex items-center text-slate-400 hover:text-slate-900 mb-8 font-bold text-sm">
            <Icon name="chevron-left" className="w-4 h-4 mr-1"/> 홈으로 돌아가기
        </button>
        <div className="bg-white rounded-[40px] border border-slate-200 shadow-2xl overflow-hidden">
            <div className="p-10 bg-indigo-600 text-white relative">
                <h2 className="text-3xl font-black mb-2">AI 티칭 머신</h2>
                <p className="text-indigo-100">당신의 직관과 매매 기록을 결합하여 독보적인 투자 AI를 만듭니다.</p>
            </div>
            <div className="p-12 bg-slate-50 min-h-[450px]">
                <div className="bg-white p-12 rounded-[32px] border border-slate-200 text-center shadow-lg">
                    <Icon name="briefcase" className="w-16 h-16 text-indigo-400 mx-auto mb-6" />
                    <h3 className="font-black text-2xl text-slate-800 mb-3">증권사 계좌 연동</h3>
                    <button className="bg-slate-900 text-white px-10 py-4 rounded-2xl font-bold shadow-xl flex items-center gap-2 mx-auto mt-6">
                        Open API 연결하기 <Icon name="arrow-right" className="w-4 h-4"/>
                    </button>
                </div>
            </div>
        </div>
    </div>
);

export default TeachingScreen;