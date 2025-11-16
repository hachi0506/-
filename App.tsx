import React, { useState, useCallback, useEffect } from 'react';
import { AppState } from './types';
import type { Player, GameSuggestion, GamePrompt } from './types';
import { WelcomeScreen } from './components/WelcomeScreen';
import { GameSelectionScreen } from './components/GameSelectionScreen';
import { GameplayScreen } from './components/GameplayScreen';
import { Loader } from './components/common/Loader';
import { Confetti } from './components/common/Confetti';
import { suggestGames, generateGamePrompt } from './services/geminiService';
import { initializeAudio, playErrorSound } from './services/audioService';

const App: React.FC = () => {
  const [appState, setAppState] = useState<AppState>(AppState.Welcome);
  const [players, setPlayers] = useState<Player[]>([]);
  const [gameSuggestions, setGameSuggestions] = useState<GameSuggestion[]>([]);
  const [selectedGame, setSelectedGame] = useState<GameSuggestion | null>(null);
  const [currentPrompt, setCurrentPrompt] = useState<GamePrompt | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [showConfetti, setShowConfetti] = useState<boolean>(false);
  
  const handleError = (message: string) => {
    playErrorSound();
    setError(message);
    setIsLoading(false);
  };

  const handlePlayersSubmitted = useCallback(async (newPlayers: Player[]) => {
    setPlayers(newPlayers);
    setIsLoading(true);
    setError(null);
    setShowConfetti(true);
    setTimeout(() => setShowConfetti(false), 5000); // Confetti lasts 5 seconds

    try {
      const suggestions = await suggestGames();
      setGameSuggestions(suggestions);
      setAppState(AppState.SelectingGame);
    } catch (e) {
      handleError(e instanceof Error ? e.message : '不明なエラーが発生しました。');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const fetchNextPrompt = useCallback(async (game: GameSuggestion, currentPlayers: Player[]) => {
    setIsLoading(true);
    setError(null);
    try {
      const prompt = await generateGamePrompt(game.type, currentPlayers);
      setCurrentPrompt(prompt);
    } catch(e) {
      handleError(e instanceof Error ? e.message : '不明なエラーが発生しました。');
    } finally {
      setIsLoading(false);
    }
  }, []);


  const handleGameSelected = useCallback((game: GameSuggestion) => {
    setSelectedGame(game);
    setAppState(AppState.PlayingGame);
    fetchNextPrompt(game, players);
  }, [players, fetchNextPrompt]);
  
  const handleNextPrompt = useCallback(() => {
    if (selectedGame) {
      fetchNextPrompt(selectedGame, players);
    }
  }, [selectedGame, players, fetchNextPrompt]);

  const handleReset = () => {
    setAppState(AppState.Welcome);
    setPlayers([]);
    setGameSuggestions([]);
    setSelectedGame(null);
    setCurrentPrompt(null);
    setIsLoading(false);
    setError(null);
    setShowConfetti(false);
  };
  
  // Effect to add a background style
  useEffect(() => {
    document.body.classList.add('gal-background');
    const style = document.createElement('style');
    style.innerHTML = `
      .gal-background {
        background: linear-gradient(135deg, #fbcfe8 0%, #fef3c7 100%);
        background-attachment: fixed;
      }
    `;
    document.head.appendChild(style);
    
    return () => {
      document.body.classList.remove('gal-background');
      if (document.head.contains(style)) {
        document.head.removeChild(style);
      }
    }
  }, []);

  const renderContent = () => {
    if (error) {
      return (
        <div className="min-h-screen flex flex-col items-center justify-center text-center p-4">
           <div className="bg-white/80 backdrop-blur-md p-8 rounded-2xl shadow-lg border border-red-200">
            <h2 className="text-2xl text-red-500 font-bold mb-4">エラー発生!😿</h2>
            <p className="text-gray-600 mb-6">{error}</p>
            <button onClick={handleReset} className="px-6 py-3 font-bold rounded-full shadow-lg transform transition-transform duration-150 active:scale-95 bg-pink-500 text-white hover:bg-pink-600">
              もっかいやる！
            </button>
          </div>
        </div>
      );
    }

    if (isLoading && appState !== AppState.PlayingGame) {
      return <div className="min-h-screen flex items-center justify-center"><Loader /></div>;
    }

    switch (appState) {
      case AppState.Welcome:
        return <WelcomeScreen onPlayersSubmitted={handlePlayersSubmitted} />;
      case AppState.SelectingGame:
        return <GameSelectionScreen suggestions={gameSuggestions} onSelectGame={handleGameSelected} />;
      case AppState.PlayingGame:
        if (selectedGame) {
          return (
            <GameplayScreen
              game={selectedGame}
              players={players}
              prompt={currentPrompt}
              isLoading={isLoading}
              onNextPrompt={handleNextPrompt}
              onEndGame={handleReset}
            />
          );
        }
        return null; // Should not happen
      default:
        return <WelcomeScreen onPlayersSubmitted={handlePlayersSubmitted} />;
    }
  };

  return (
    <div className="min-h-screen font-sans" onClick={initializeAudio}>
      {showConfetti && <Confetti />}
      {renderContent()}
    </div>
  );
};

export default App;