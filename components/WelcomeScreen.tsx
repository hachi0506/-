import React, { useState } from 'react';
import type { Player } from '../types';
import { Button } from './common/Button';
import { Card } from './common/Card';
import { PlayerTag } from './common/PlayerTag';
import { playAddPlayerSound, playSuccessSound } from '../services/audioService';

interface WelcomeScreenProps {
  onPlayersSubmitted: (players: Player[]) => void;
}

const SparklesIcon = () => (
    <svg xmlns="http://www.w.org/2000/svg" className="h-16 w-16 text-yellow-400" fill="currentColor" viewBox="0 0 20 20">
        <path fillRule="evenodd" d="M10 2.5a.75.75 0 01.75.75V5h1.75a.75.75 0 010 1.5H10.75v1.75a.75.75 0 01-1.5 0V6.5H7.5a.75.75 0 010-1.5H9.25V3.25A.75.75 0 0110 2.5zM3.25 8a.75.75 0 01.75-.75h1.75a.75.75 0 010 1.5H4a.75.75 0 01-.75-.75zM14 8a.75.75 0 01.75-.75h1.75a.75.75 0 010 1.5H14.75A.75.75 0 0114 8zm2.672 5.332a.75.75 0 01-.222.53l-1.332 1.332a.75.75 0 11-1.06-1.06l1.331-1.332a.75.75 0 011.282.53zM5.332 13.332a.75.75 0 011.282-.53l1.332 1.332a.75.75 0 11-1.06 1.06l-1.332-1.332a.75.75 0 01-.222-.53zM10 12.5a.75.75 0 01.75.75v1.75a.75.75 0 01-1.5 0V13.25a.75.75 0 01.75-.75z" clipRule="evenodd" />
    </svg>
);


export const WelcomeScreen: React.FC<WelcomeScreenProps> = ({ onPlayersSubmitted }) => {
  const [players, setPlayers] = useState<Player[]>([]);
  const [playerName, setPlayerName] = useState('');

  const handleAddPlayer = (e: React.FormEvent) => {
    e.preventDefault();
    if (playerName.trim() && !players.some(p => p.name === playerName.trim())) {
      playAddPlayerSound();
      setPlayers([...players, { id: Date.now(), name: playerName.trim() }]);
      setPlayerName('');
    }
  };

  const handleRemovePlayer = (id: number) => {
    setPlayers(players.filter(p => p.id !== id));
  };

  const handleSubmit = () => {
    playSuccessSound();
    onPlayersSubmitted(players);
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-4">
      <Card className="w-full max-w-md mx-auto">
        <div className="text-center mb-8">
            <div className="flex justify-center mb-4">
                <div className="w-24 h-24 rounded-full bg-white/50 flex items-center justify-center ring-4 ring-pink-300/50 shadow-lg">
                    <SparklesIcon/>
                </div>
            </div>
          <h1 className="text-4xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-pink-500 via-red-500 to-yellow-500">
            アゲてこ！飲みゲー
          </h1>
          <p className="text-gray-500 mt-2 font-semibold">AIが今夜を最強に盛り上げる✨</p>
        </div>

        <form onSubmit={handleAddPlayer} className="flex gap-2 mb-4">
          <input
            type="text"
            value={playerName}
            onChange={(e) => setPlayerName(e.target.value)}
            placeholder="プレイヤー名を入力してね"
            className="flex-grow bg-white/80 border border-gray-300 rounded-full px-5 py-3 focus:outline-none focus:ring-2 focus:ring-pink-400 transition-all placeholder:text-gray-400"
          />
          <Button type="submit" variant="secondary">追加</Button>
        </form>

        <div className="min-h-[80px] mb-6 p-2 bg-gray-500/10 rounded-2xl">
          <div className="flex flex-wrap gap-2">
            {players.map(player => (
              <PlayerTag
                key={player.id}
                name={player.name}
                onRemove={() => handleRemovePlayer(player.id)}
                className="animate-pop-in"
              />
            ))}
          </div>
        </div>

        <Button
          onClick={handleSubmit}
          disabled={players.length < 2}
          className="w-full text-lg"
        >
          {players.length < 2 ? `あと${2 - players.length}人！` : 'ゲームを選ぶっ！'}
        </Button>
      </Card>
    </div>
  );
};