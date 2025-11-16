let audioCtx: AudioContext | null = null;

const initAudio = () => {
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
  }
};

interface PlaySoundOptions {
  type?: OscillatorType;
  frequency?: number;
  duration?: number;
  volume?: number;
  rampDown?: boolean;
}

const playSound = ({
  type = 'sine',
  frequency = 440,
  duration = 0.1,
  volume = 0.5,
  rampDown = true,
}: PlaySoundOptions) => {
  if (!audioCtx) return;

  const oscillator = audioCtx.createOscillator();
  const gainNode = audioCtx.createGain();

  oscillator.connect(gainNode);
  gainNode.connect(audioCtx.destination);

  oscillator.type = type;
  oscillator.frequency.value = frequency;
  gainNode.gain.setValueAtTime(volume, audioCtx.currentTime);

  if (rampDown) {
    gainNode.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + duration);
  }

  oscillator.start(audioCtx.currentTime);
  oscillator.stop(audioCtx.currentTime + duration);
};

export const playAddPlayerSound = () => {
  initAudio();
  playSound({ type: 'triangle', frequency: 440, duration: 0.1, volume: 0.3 });
  setTimeout(() => playSound({ type: 'triangle', frequency: 660, duration: 0.1, volume: 0.3 }), 100);
};

export const playSuccessSound = () => {
  initAudio();
  playSound({ type: 'sine', frequency: 523.25, duration: 0.1, volume: 0.3 }); // C5
  setTimeout(() => playSound({ type: 'sine', frequency: 659.25, duration: 0.1, volume: 0.3 }), 100); // E5
  setTimeout(() => playSound({ type: 'sine', frequency: 783.99, duration: 0.1, volume: 0.3 }), 200); // G5
};

export const playClickSound = () => {
  initAudio();
  playSound({ type: 'sine', frequency: 350, duration: 0.08, volume: 0.2 });
};

export const playErrorSound = () => {
  initAudio();
  playSound({ type: 'square', frequency: 220, duration: 0.2, volume: 0.2 });
  setTimeout(() => playSound({ type: 'square', frequency: 164, duration: 0.3, volume: 0.2 }), 200);
};

// This function should be called on the first user interaction
export const initializeAudio = () => {
  initAudio();
};
