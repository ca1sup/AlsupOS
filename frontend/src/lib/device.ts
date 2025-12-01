import { toast } from 'react-toastify';

// --- HAPTICS ---
// Note: iOS Safari often blocks navigator.vibrate. 
// This works best on Android or Desktop, but is "safe" to run on iOS.
export const triggerHaptic = (pattern: number | number[] = 10) => {
  if (typeof navigator !== 'undefined' && navigator.vibrate) {
    navigator.vibrate(pattern);
  }
};

// --- TEXT TO SPEECH ---
let synthesis: SpeechSynthesis | null = null;
if (typeof window !== 'undefined') {
  synthesis = window.speechSynthesis;
}

export const stopSpeaking = () => {
  if (synthesis && synthesis.speaking) {
    synthesis.cancel();
  }
};

export const speakText = (text: string) => {
  if (!synthesis) {
    toast.error("Text-to-speech not supported on this device.");
    return;
  }

  // Cancel any ongoing speech
  if (synthesis.speaking) {
    synthesis.cancel();
  }

  const utterance = new SpeechSynthesisUtterance(text);
  
  // iOS specific voice optimization (Try to find "Samantha" or "Daniel")
  const voices = synthesis.getVoices();
  const preferredVoice = voices.find(v => 
    v.name.includes("Samantha") || // iOS Siri-like
    v.name.includes("Google US English") // Android
  );

  if (preferredVoice) {
    utterance.voice = preferredVoice;
  }

  utterance.rate = 1.0; 
  utterance.pitch = 1.0;
  
  synthesis.speak(utterance);
};