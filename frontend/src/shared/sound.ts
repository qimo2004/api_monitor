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

export function playAlertSound(): void {
  if (!isSoundEnabled()) return;
  try {
    const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
    const oscillator = ctx.createOscillator();
    const gain = ctx.createGain();
    oscillator.connect(gain);
    gain.connect(ctx.destination);
    oscillator.type = 'sine';
    oscillator.frequency.setValueAtTime(800, ctx.currentTime);
    oscillator.frequency.setValueAtTime(1000, ctx.currentTime + 0.1);
    oscillator.frequency.setValueAtTime(1200, ctx.currentTime + 0.2);
    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5);
    oscillator.start(ctx.currentTime);
    oscillator.stop(ctx.currentTime + 0.5);
    // 重复一次
    oscillator.start(ctx.currentTime + 0.6);
    oscillator.stop(ctx.currentTime + 1.1);
  } catch {
    // 静默失败，声音提醒不可用时不影响功能
  }
}
