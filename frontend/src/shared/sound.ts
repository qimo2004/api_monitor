/**
 * 告警声音提醒工具
 * 使用 Web Audio API 生成提示音，无需外部音频文件
 */

const SOUND_KEY = 'alert_sound_enabled';

export function isSoundEnabled(): boolean {
  return localStorage.getItem(SOUND_KEY) !== 'false';
}

export function setSoundEnabled(enabled: boolean): void {
  localStorage.setItem(SOUND_KEY, String(enabled));
}

function createBeep(ctx: AudioContext, startTime: number, duration: number): void {
  const oscillator = ctx.createOscillator();
  const gain = ctx.createGain();
  oscillator.connect(gain);
  gain.connect(ctx.destination);
  oscillator.type = 'sine';
  oscillator.frequency.setValueAtTime(800, startTime);
  oscillator.frequency.setValueAtTime(1000, startTime + 0.1);
  oscillator.frequency.setValueAtTime(1200, startTime + 0.2);
  gain.gain.setValueAtTime(0.3, startTime);
  gain.gain.exponentialRampToValueAtTime(0.01, startTime + duration);
  oscillator.start(startTime);
  oscillator.stop(startTime + duration);
}

export function playAlertSound(): void {
  if (!isSoundEnabled()) return;
  try {
    const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
    // 第一次提示音
    createBeep(ctx, ctx.currentTime, 0.5);
    // 第二次提示音（必须使用独立的 OscillatorNode）
    createBeep(ctx, ctx.currentTime + 0.6, 0.5);
  } catch {
    // 静默失败，声音提醒不可用时不影响功能
  }
}
