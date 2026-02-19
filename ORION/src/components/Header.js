import Icon from './Icon.js';

const Header = ({ setCurrentScreen, setTradingMode }) => (
    <header className="sticky top-0 z-50 bg-white border-b border-slate-200 h-16 flex items-center justify-between px-6">
        <div 
            className="flex items-center gap-2 cursor-pointer hover:opacity-80 transition-opacity"
            onClick={() => { setCurrentScreen('home'); setTradingMode('trading'); }}
        >
            <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center shadow-md shadow-indigo-100">
                <Icon name="target" className="text-white w-5 h-5" />
            </div>
            <span className="text-xl font-black text-slate-900 tracking-tighter">ORION AI</span>
        </div>
        <div className="flex items-center gap-4">
            <div className="hidden md:flex items-center bg-slate-100 px-4 py-2 rounded-full border border-slate-200/50">
                <Icon name="search" className="w-4 h-4 text-slate-400 mr-2"/>
                <input type="text" placeholder="종목 검색 / 기능 검색" className="bg-transparent text-sm outline-none w-48 text-slate-600"/>
            </div>
            <button className="p-2 hover:bg-slate-100 rounded-full relative transition-colors">
                <Icon name="bell" className="w-5 h-5 text-slate-500"/>
                <span className="absolute top-2 right-2 w-2 h-2 bg-rose-500 rounded-full border border-white"></span>
            </button>
            <div className="w-8 h-8 bg-slate-200 rounded-full flex items-center justify-center border border-slate-300">
                <Icon name="user" className="w-4 h-4 text-slate-500"/>
            </div>
        </div>
    </header>
);

export default Header;