import Header from './components/Header.js';
import HomeScreen from './screens/HomeScreen.js';
import LibraryScreen from './screens/LibraryScreen.js';
import BotWorkspace from './screens/BotWorkspace.js';
import TeachingScreen from './screens/TeachingScreen.js';
import ScreenerScreen from './screens/ScreenerScreen.js';

const { useState } = React;

const App = () => {
    const [currentScreen, setCurrentScreen] = useState('home');
    // tradingMode state is now managed locally within BotWorkspace,
    // but we need to pass setTradingMode to Header if it's meant to reset it.
    // For now, assuming Header only sets currentScreen to 'home' and BotWorkspace default to 'trading'.
    
    // To handle the Header's reset for tradingMode:
    const resetToHome = () => {
        setCurrentScreen('home');
        // If there's a global tradingMode, it would be reset here.
        // As per current structure, tradingMode is local to BotWorkspace.
        // So we just reset the screen.
    }

    return (
        <div className="min-h-screen bg-[#F8FAFC] text-slate-900">
            {/* Pass resetToHome to Header */}
            <Header setCurrentScreen={resetToHome} /> 
            <main>
                {currentScreen === 'home' && <HomeScreen setCurrentScreen={setCurrentScreen} />}
                {currentScreen === 'menu1' && <LibraryScreen setCurrentScreen={setCurrentScreen} />}
                {(currentScreen === 'menu1-trading' || currentScreen === 'menu1-analysis') && <BotWorkspace setCurrentScreen={setCurrentScreen} />}
                {currentScreen === 'menu2' && <TeachingScreen setCurrentScreen={setCurrentScreen} />}
                {currentScreen === 'menu3' && <ScreenerScreen setCurrentScreen={setCurrentScreen} />}
            </main>
        </div>
    );
};

export default App;