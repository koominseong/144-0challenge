document.addEventListener('DOMContentLoaded', () => {
  document.documentElement.classList.add('career-ready');

  // --- New Career: league -> team dependent dropdown ---
  const leagueSelect = document.getElementById('league-select');
  const teamSelect = document.getElementById('team-select');
  if (leagueSelect && teamSelect && Array.isArray(window.CAREER_TEAMS)) {
    const teams = window.CAREER_TEAMS;

    const renderTeams = (leagueId, preselectTeamId) => {
      teamSelect.innerHTML = '';
      const matches = teams.filter(t => t.league_id === leagueId);
      if (!leagueId || matches.length === 0) {
        teamSelect.disabled = true;
        const opt = document.createElement('option');
        opt.value = '';
        opt.disabled = true;
        opt.selected = true;
        opt.textContent = leagueId ? '선택 가능한 팀이 없습니다' : '먼저 리그를 선택하세요';
        teamSelect.appendChild(opt);
        return;
      }
      teamSelect.disabled = false;
      const placeholder = document.createElement('option');
      placeholder.value = '';
      placeholder.disabled = true;
      placeholder.textContent = '소속팀 선택';
      teamSelect.appendChild(placeholder);
      let didPreselect = false;
      matches.forEach(t => {
        const opt = document.createElement('option');
        opt.value = t.team_id;
        opt.textContent = t.name;
        if (preselectTeamId && t.team_id === preselectTeamId) {
          opt.selected = true;
          didPreselect = true;
        }
        teamSelect.appendChild(opt);
      });
      if (!didPreselect) placeholder.selected = true;
    };

    leagueSelect.addEventListener('change', () => renderTeams(leagueSelect.value));
    // Initialize on load (handles browser back/forward restoring a selected league)
    if (leagueSelect.value) renderTeams(leagueSelect.value);
  }

  // --- Dashboard: highlight the chosen season decision before submit ---
  document.querySelectorAll('.decision-option input[type="radio"]').forEach(radio => {
    const sync = () => {
      radio.closest('.decision-option').classList.toggle('is-selected', radio.checked);
    };
    radio.addEventListener('change', () => {
      document.querySelectorAll('.decision-option').forEach(el => el.classList.remove('is-selected'));
      sync();
    });
    sync();
  });
});
