document.addEventListener('DOMContentLoaded', () => {
  document.documentElement.classList.add('career-ready');

  // --- Generic radio-card highlight (season decisions, pace picker, offers) ---
  const wireRadioGroup = (itemSelector) => {
    document.querySelectorAll(itemSelector).forEach(item => {
      const radio = item.querySelector('input[type="radio"]');
      if (!radio) return;
      const group = item.closest('form') || document;
      const sync = () => item.classList.toggle('is-selected', radio.checked);
      radio.addEventListener('change', () => {
        group.querySelectorAll(itemSelector).forEach(el => el.classList.remove('is-selected'));
        sync();
      });
      sync();
    });
  };
  wireRadioGroup('.decision-option');
  wireRadioGroup('.pace-option');
  wireRadioGroup('.offer-card');

  // --- Retirement result card: draw a shareable PNG on canvas ---
  const canvas = document.getElementById('result-card-canvas');
  if (canvas && window.CAREER_RESULT_CARD) {
    const ctx = canvas.getContext('2d');
    const d = window.CAREER_RESULT_CARD;
    const W = canvas.width, H = canvas.height;

    const bg = ctx.createLinearGradient(0, 0, 0, H);
    bg.addColorStop(0, '#171c22');
    bg.addColorStop(1, '#0a0d11');
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, W, H);

    ctx.strokeStyle = 'rgba(217,255,63,.5)';
    ctx.lineWidth = 3;
    ctx.strokeRect(10, 10, W - 20, H - 20);

    ctx.fillStyle = '#d9ff3f';
    ctx.font = '700 20px Inter, sans-serif';
    ctx.fillText('144 CAREER · BASEBALL LIFE', 48, 70);

    ctx.fillStyle = '#f5f7fa';
    ctx.font = '900 64px "Barlow Condensed", sans-serif';
    ctx.fillText(d.name, 48, 150);

    ctx.fillStyle = '#8c96a3';
    ctx.font = '600 20px Inter, sans-serif';
    ctx.fillText(`${d.nationality} · ${d.position} · ${d.bats}`, 48, 185);
    ctx.fillText(`마지막 소속: ${d.lastTeam}`, 48, 215);

    // OVR badge
    ctx.fillStyle = 'rgba(217,255,63,.12)';
    ctx.fillRect(48, 250, 200, 130);
    ctx.fillStyle = '#d9ff3f';
    ctx.font = '700 16px Inter, sans-serif';
    ctx.fillText('PEAK OVR', 68, 285);
    ctx.font = '900 60px "Barlow Condensed", sans-serif';
    ctx.fillText(String(d.peakRating), 68, 350);

    ctx.fillStyle = 'rgba(255,255,255,.04)';
    ctx.fillRect(272, 250, 400, 130);
    ctx.fillStyle = '#f5f7fa';
    ctx.font = '700 16px Inter, sans-serif';
    ctx.fillText('PEAK MARKET VALUE', 292, 285);
    ctx.font = '900 40px "Barlow Condensed", sans-serif';
    ctx.fillText('₩' + d.peakValue.toLocaleString(), 292, 335);

    const stats = [
      ['GAMES', d.games],
      [d.primaryLabel, d.primaryValue],
      [d.secondaryLabel, d.secondaryValue],
      ['TITLES', d.titles],
      ['TRANSFERS', d.transfers],
    ];
    let sy = 430;
    stats.forEach(([label, value]) => {
      ctx.fillStyle = '#69737f';
      ctx.font = '700 14px Inter, sans-serif';
      ctx.fillText(label, 48, sy);
      ctx.fillStyle = '#f5f7fa';
      ctx.font = '800 34px "Barlow Condensed", sans-serif';
      ctx.fillText(String(value), 220, sy + 4);
      sy += 60;
    });

    ctx.fillStyle = '#d9ff3f';
    ctx.font = '700 16px Inter, sans-serif';
    ctx.fillText('CAREER SCORE', 48, sy + 30);
    ctx.font = '900 46px "Barlow Condensed", sans-serif';
    ctx.fillStyle = '#f5f7fa';
    ctx.fillText(String(d.careerScore), 48, sy + 80);

    ctx.fillStyle = '#59636e';
    ctx.font = '600 14px Inter, sans-serif';
    ctx.fillText('144CHALLENGE.CAREER', 48, H - 30);

    const saveBtn = document.getElementById('save-card-btn');
    if (saveBtn) {
      saveBtn.addEventListener('click', () => {
        const link = document.createElement('a');
        link.download = `${d.name}_career_card.png`;
        link.href = canvas.toDataURL('image/png');
        link.click();
      });
    }
  }
});
