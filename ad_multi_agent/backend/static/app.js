/**
 * CineAI Agentic Assistant Director Dashboard — Frontend Logic
 */

document.addEventListener('DOMContentLoaded', () => {
  // State
  let currentSceneId = 'SC01';
  let executionMode = 'fast'; // 'fast' | 'agent'
  let isRunning = false;
  let currentAssessment = null;

  // DOM Elements
  const sceneSelect = document.getElementById('sceneSelect');
  const analyzeBtn = document.getElementById('analyzeBtn');
  const modeFastBtn = document.getElementById('modeFastBtn');
  const modeAgentBtn = document.getElementById('modeAgentBtn');
  const demoPresets = document.querySelectorAll('.preset-btn');
  
  // Pipeline Nodes
  const nodeRoot = document.getElementById('nodeRoot');
  const nodeParallelBox = document.getElementById('nodeParallelBox');
  const nodeReplan = document.getElementById('nodeReplan');
  const pipelineStatusBadge = document.getElementById('pipelineStatusBadge');
  
  const miniNodes = {
    weather: document.getElementById('nodeWeather'),
    location: document.getElementById('nodeLocation'),
    camera: document.getElementById('nodeCamera'),
    stunt: document.getElementById('nodeStunt'),
    cast: document.getElementById('nodeCast'),
  };

  // Dossier
  const dossierSceneId = document.getElementById('dossierSceneId');
  const dossierTitle = document.getElementById('dossierTitle');
  const dossierLogline = document.getElementById('dossierLogline');
  const dossierLocation = document.getElementById('dossierLocation');
  const dossierSetting = document.getElementById('dossierSetting');
  const dossierDate = document.getElementById('dossierDate');
  const dossierStunt = document.getElementById('dossierStunt');
  const dossierCharacters = document.getElementById('dossierCharacters');
  const dossierElements = document.getElementById('dossierElements');

  // Status & Replan
  const globalStatusPill = document.getElementById('globalStatusPill');
  const globalStatusText = document.getElementById('globalStatusText');
  const replanContainer = document.getElementById('replanContainer');
  const replanAlertDesc = document.getElementById('replanAlertDesc');
  const failedDeptsBadges = document.getElementById('failedDeptsBadges');
  const replanStrategyText = document.getElementById('replanStrategyText');
  const replanAlternativesList = document.getElementById('replanAlternativesList');

  // Terminal Drawer
  const agentTelemetryDrawer = document.getElementById('agentTelemetryDrawer');
  const toggleTerminalBtn = document.getElementById('toggleTerminalBtn');
  const closeDrawerBtn = document.getElementById('closeDrawerBtn');
  const terminalFeed = document.getElementById('terminalFeed');
  const exportReportBtn = document.getElementById('exportReportBtn');
  const toastContainer = document.getElementById('toastContainer');

  // 1. Initialize Live SMPTE Timecode
  initTimecode();

  // 2. Fetch Scenes from API
  fetchScenes();

  // 3. Event Listeners
  sceneSelect.addEventListener('change', (e) => {
    selectScene(e.target.value);
  });

  demoPresets.forEach(btn => {
    btn.addEventListener('click', () => {
      const sceneId = btn.getAttribute('data-scene');
      selectScene(sceneId, true);
    });
  });

  modeFastBtn.addEventListener('click', () => {
    setMode('fast');
  });

  modeAgentBtn.addEventListener('click', () => {
    setMode('agent');
  });

  analyzeBtn.addEventListener('click', () => {
    runAnalysis();
  });

  toggleTerminalBtn.addEventListener('click', () => {
    agentTelemetryDrawer.classList.toggle('closed');
  });

  closeDrawerBtn.addEventListener('click', () => {
    agentTelemetryDrawer.classList.add('closed');
  });

  exportReportBtn.addEventListener('click', () => {
    copyReportToClipboard();
  });

  // Attach JSON Drawer Toggles
  document.querySelectorAll('.json-toggle-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-target');
      const drawer = document.getElementById(targetId);
      if (drawer) {
        drawer.classList.toggle('open');
        const chevron = btn.querySelector('.chevron');
        if (chevron) {
          chevron.textContent = drawer.classList.contains('open') ? '▲' : '▼';
        }
      }
    });
  });

  // Initial Run on Page Load for SC01
  setTimeout(() => {
    runAnalysis();
  }, 400);

  /* ==========================================================================
     Timecode Simulator
     ========================================================================== */
  function initTimecode() {
    let h = 0, m = 17, s = 45, f = 0;
    const tcHours = document.getElementById('tcHours');
    const tcMinutes = document.getElementById('tcMinutes');
    const tcSeconds = document.getElementById('tcSeconds');
    const tcFrames = document.getElementById('tcFrames');

    setInterval(() => {
      f++;
      if (f >= 24) { f = 0; s++; }
      if (s >= 60) { s = 0; m++; }
      if (m >= 60) { m = 0; h++; }
      if (h >= 24) { h = 0; }

      if (tcHours) tcHours.textContent = String(h).padStart(2, '0');
      if (tcMinutes) tcMinutes.textContent = String(m).padStart(2, '0');
      if (tcSeconds) tcSeconds.textContent = String(s).padStart(2, '0');
      if (tcFrames) tcFrames.textContent = String(f).padStart(2, '0');
    }, 1000 / 24);
  }

  /* ==========================================================================
     Scene Selection & State
     ========================================================================== */
  function setMode(mode) {
    executionMode = mode;
    modeFastBtn.classList.toggle('active', mode === 'fast');
    modeAgentBtn.classList.toggle('active', mode === 'agent');
    logToTerminal('SYSTEM', `Execution mode switched to: ${mode === 'fast' ? 'Instant DB Ground Truth (<50ms)' : 'Live Vertex AI Gemini 2.5 Multi-Agent'}`);
  }

  function selectScene(sceneId, triggerAnalyze = false) {
    currentSceneId = sceneId;
    sceneSelect.value = sceneId;

    // Update active preset button
    demoPresets.forEach(b => {
      b.classList.toggle('active', b.getAttribute('data-scene') === sceneId);
    });

    // Reset visual nodes
    resetPipelineNodes();

    // Fetch details to populate dossier
    fetchSceneDetails(sceneId);

    if (triggerAnalyze) {
      runAnalysis();
    }
  }

  async function fetchScenes() {
    try {
      const res = await fetch('/api/scenes');
      const data = await res.json();
      if (data.scenes && data.scenes.length > 0) {
        sceneSelect.innerHTML = '';
        data.scenes.forEach(s => {
          const opt = document.createElement('option');
          opt.value = s.scene_id;
          opt.textContent = `${s.scene_id} - ${s.title} (${s.location_name || 'Set'})`;
          sceneSelect.appendChild(opt);
        });
        sceneSelect.value = currentSceneId;
      }
    } catch (err) {
      console.warn('Using local preset list:', err);
    }
  }

  async function fetchSceneDetails(sceneId) {
    try {
      const res = await fetch(`/api/scenes/${sceneId}`);
      if (!res.ok) return;
      const data = await res.json();
      if (data.found && data.scene) {
        updateDossier(data.scene);
      }
    } catch (err) {
      console.error('Failed to fetch scene details:', err);
    }
  }

  function updateDossier(scene) {
    dossierSceneId.textContent = scene.scene_id || currentSceneId;
    dossierTitle.textContent = scene.title || 'Untitled Scene';
    dossierLogline.textContent = scene.logline || 'No logline available.';
    dossierLocation.textContent = `${scene.location_name || 'Set'}, ${scene.city || 'Chennai'}`;
    dossierSetting.textContent = `${scene.int_ext || 'EXT'} • ${scene.shoot_time || 'DAY'}`;
    dossierDate.textContent = `${scene.shoot_date || '2026-09-10'} • ${scene.shoot_time || '17:45'}`;
    dossierStunt.textContent = scene.stunt_level || 'NONE';
    dossierCharacters.textContent = scene.primary_characters || 'Hero, Cast';
    dossierElements.textContent = scene.action_beats || scene.department_notes_art || 'Dialogue, scene coverage';
  }

  /* ==========================================================================
     Pipeline Graph Node Helpers
     ========================================================================== */
  function resetPipelineNodes() {
    nodeRoot.className = 'workflow-node root-node';
    nodeParallelBox.className = 'workflow-parallel-box';
    nodeReplan.className = 'workflow-node replan-node';
    pipelineStatusBadge.textContent = 'READY TO EXECUTE';
    pipelineStatusBadge.style.color = '#a5b4fc';

    Object.values(miniNodes).forEach(node => {
      node.className = 'mini-node';
      node.querySelector('.mini-badge').textContent = 'IDLE';
    });
  }

  function markRunning() {
    isRunning = true;
    analyzeBtn.classList.add('running');
    analyzeBtn.querySelector('.btn-text').textContent = 'ANALYZING...';
    pipelineStatusBadge.textContent = 'EXECUTING WORKFLOW';
    pipelineStatusBadge.style.color = '#f59e0b';
    nodeRoot.classList.add('running');

    Object.values(miniNodes).forEach(node => {
      node.classList.add('running');
      node.querySelector('.mini-badge').textContent = 'CHECKING';
    });
  }

  function markFinished() {
    isRunning = false;
    analyzeBtn.classList.remove('running');
    analyzeBtn.querySelector('.btn-text').textContent = 'ANALYZE SCENE';
    nodeRoot.classList.remove('running');
    nodeRoot.classList.add('done');
  }

  /* ==========================================================================
     Scene Analysis Execution
     ========================================================================== */
  async function runAnalysis() {
    if (isRunning) return;
    markRunning();
    logToTerminal('USER', `Analyze scene ${currentSceneId} (Mode: ${executionMode})`);

    if (executionMode === 'fast') {
      try {
        const res = await fetch('/api/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ scene_id: currentSceneId, mode: 'fast' }),
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Analysis request failed');
        }

        const data = await res.json();
        currentAssessment = data;
        
        // Small delay for smooth visual transition
        setTimeout(() => {
          renderAssessment(data);
          markFinished();
        }, 200);

      } catch (err) {
        showToast(`Analysis Error: ${err.message}`, 'error');
        markFinished();
      }
    } else {
      // Live Streaming Mode via Server-Sent Events
      runStreamingAgent();
    }
  }

  async function runStreamingAgent() {
    // Open telemetry drawer automatically in streaming mode
    agentTelemetryDrawer.classList.remove('closed');
    logToTerminal('SYSTEM', `Dispatching ADK multi-agent orchestrator for ${currentSceneId}...`);

    try {
      const response = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scene_id: currentSceneId, mode: 'agent' }),
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop(); // Keep the rest

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const rawJson = line.slice(6);
            try {
              const event = JSON.parse(rawJson);
              handleStreamEvent(event);
            } catch (e) {
              // Ignore non-json lines
            }
          }
        }
      }

      markFinished();
      showToast(`Multi-Agent workflow finished for ${currentSceneId}`, 'success');
    } catch (err) {
      logToTerminal('ERROR', err.message);
      showToast(`Agent stream error: ${err.message}`, 'error');
      markFinished();
    }
  }

  function handleStreamEvent(event) {
    if (event.type === 'start') {
      logToTerminal('SYSTEM', event.message);
    } else if (event.type === 'ground_truth') {
      currentAssessment = event.data;
      renderAssessment(event.data);
    } else if (event.type === 'agent_event') {
      const author = event.author || 'agent';
      const text = event.text || '';
      logToTerminal(author.toUpperCase(), text);
      
      // Update individual node in pipeline if author matches
      const deptKey = author.replace('_agent', '').toLowerCase();
      if (miniNodes[deptKey]) {
        miniNodes[deptKey].classList.remove('running');
        miniNodes[deptKey].classList.add(text.includes('"ready_for_shooting": false') ? 'fail' : 'pass');
        miniNodes[deptKey].querySelector('.mini-badge').textContent = text.includes('"ready_for_shooting": false') ? 'FAIL' : 'PASS';
      }
    } else if (event.type === 'log') {
      if (event.text && !event.text.includes('Session ID:')) {
        logToTerminal('RUNNER', event.text);
      }
    } else if (event.type === 'complete') {
      logToTerminal('SYSTEM', event.message);
    }
  }

  /* ==========================================================================
     Render Department Findings & Recommendations
     ========================================================================== */
  function renderAssessment(data) {
    const { scene_brief, departments, all_departments_ready, failed_departments, replan } = data;

    // Update Dossier
    if (scene_brief) {
      updateDossier(scene_brief);
    }

    // Global Status Indicator
    if (all_departments_ready) {
      globalStatusPill.className = 'production-status-pill';
      globalStatusText.textContent = 'READY TO SHOOT';
      pipelineStatusBadge.textContent = 'ALL DEPARTMENTS READY';
      pipelineStatusBadge.style.color = '#34d399';
      nodeReplan.className = 'workflow-node replan-node';
      replanContainer.classList.add('hidden');
    } else {
      globalStatusPill.className = 'production-status-pill blocked';
      globalStatusText.textContent = 'PRODUCTION BLOCKED';
      pipelineStatusBadge.textContent = 'REPLAN ENGAGED';
      pipelineStatusBadge.style.color = '#f87171';
      nodeReplan.className = 'workflow-node replan-node running done';
      renderReplanPanel(replan, failed_departments);
    }

    // 1. Weather
    const w = departments.weather || {};
    const wReady = w.ready_for_shooting === true;
    renderDeptCard('weather', wReady, w.reason || (wReady ? 'Weather is optimal for shoot.' : 'Exceeds threshold.'));
    miniNodes.weather.className = `mini-node ${wReady ? 'pass' : 'fail'}`;
    miniNodes.weather.querySelector('.mini-badge').textContent = wReady ? 'PASS' : 'FAIL';
    
    const rain = w.metadata?.rain_probability ?? 0.1;
    const maxRain = w.metadata?.threshold_rain ?? 0.3;
    const wind = w.metadata?.wind_speed_kmh ?? 10;
    const maxWind = w.metadata?.threshold_wind ?? 25;
    
    document.getElementById('rainBar').style.width = `${Math.min(100, (rain / (maxRain || 1)) * 50)}%`;
    document.getElementById('rainBar').className = `metric-bar ${rain > maxRain ? 'danger' : ''}`;
    document.getElementById('rainVal').textContent = `${Math.round(rain * 100)}% / Max ${Math.round(maxRain * 100)}%`;

    document.getElementById('windBar').style.width = `${Math.min(100, (wind / (maxWind || 1)) * 50)}%`;
    document.getElementById('windBar').className = `metric-bar ${wind > maxWind ? 'danger' : ''}`;
    document.getElementById('windVal').textContent = `${wind} km/h / Max ${maxWind}`;
    
    document.getElementById('weatherJsonCode').textContent = JSON.stringify(w, null, 2);

    // 2. Location
    const l = departments.location || {};
    const lReady = l.ready_for_shooting === true;
    renderDeptCard('location', lReady, l.reason || 'Location feasibility evaluated.');
    miniNodes.location.className = `mini-node ${lReady ? 'pass' : 'fail'}`;
    miniNodes.location.querySelector('.mini-badge').textContent = lReady ? 'PASS' : 'FAIL';

    const permitEl = document.getElementById('permitStatus');
    const permitStatus = l.metadata?.permit_status || (l.metadata?.permit_required ? 'PENDING' : 'N/A');
    permitEl.textContent = permitStatus;
    permitEl.className = `permit-value ${permitStatus.toLowerCase()}`;
    document.getElementById('operatingHours').textContent = l.metadata?.operating_hours || '24x7';
    document.getElementById('accessConstraints').textContent = l.metadata?.access_constraints || 'Standard crew access';
    document.getElementById('locationJsonCode').textContent = JSON.stringify(l, null, 2);

    // 3. Camera
    const c = departments.camera || {};
    const cReady = c.ready_for_shooting === true;
    renderDeptCard('camera', cReady, c.reason || 'Camera gear status checked.');
    miniNodes.camera.className = `mini-node ${cReady ? 'pass' : 'fail'}`;
    miniNodes.camera.querySelector('.mini-badge').textContent = cReady ? 'PASS' : 'FAIL';

    const camListEl = document.getElementById('cameraList');
    camListEl.innerHTML = '';
    const camStatuses = c.metadata?.camera_statuses || [];
    if (camStatuses.length > 0) {
      camStatuses.forEach(cam => {
        const chip = document.createElement('div');
        const isAvail = (cam.status || '').toUpperCase() === 'AVAILABLE';
        chip.className = `gear-chip ${isAvail ? 'available' : 'maintenance'}`;
        chip.innerHTML = `
          <span class="gear-id">${cam.camera_id}</span>
          <span class="gear-status">${cam.status || 'SCHEDULED'}</span>
        `;
        camListEl.appendChild(chip);
      });
    } else {
      camListEl.innerHTML = '<span class="gear-notes">No camera hardware assigned</span>';
    }
    document.getElementById('cameraNotes').textContent = c.metadata?.notes || 'Standard dialogue coverage.';
    document.getElementById('cameraJsonCode').textContent = JSON.stringify(c, null, 2);

    // 4. Stunt
    const st = departments.stunt || {};
    const stReady = st.ready_for_shooting === true;
    renderDeptCard('stunt', stReady, st.reason || 'Stunt safety protocols verified.');
    miniNodes.stunt.className = `mini-node ${stReady ? 'pass' : 'fail'}`;
    miniNodes.stunt.querySelector('.mini-badge').textContent = stReady ? 'PASS' : 'FAIL';

    const stuntChecklistEl = document.getElementById('stuntChecklist');
    stuntChecklistEl.innerHTML = '';
    const checklist = st.metadata?.checklist || [];
    if (checklist.length > 0) {
      checklist.forEach(item => {
        const isConf = item.confirmed === true;
        const div = document.createElement('div');
        div.className = `checklist-item ${isConf ? 'checked' : 'unconfirmed'}`;
        div.innerHTML = `
          <span class="check-icon">${isConf ? '✓' : '✗'}</span>
          <span>${item.item} ${isConf ? '(Confirmed)' : '(Pending Verification)'}</span>
        `;
        stuntChecklistEl.appendChild(div);
      });
    } else {
      stuntChecklistEl.innerHTML = `
        <div class="checklist-item checked">
          <span class="check-icon">✓</span>
          <span>Stunt Level: ${st.metadata?.risk_level || 'NONE'}</span>
        </div>
        <div class="checklist-item checked">
          <span class="check-icon">✓</span>
          <span>No medical crew / harness dependency</span>
        </div>
      `;
    }
    document.getElementById('stuntJsonCode').textContent = JSON.stringify(st, null, 2);

    // 5. Cast
    const ca = departments.cast || {};
    const caReady = ca.ready_for_shooting === true;
    renderDeptCard('cast', caReady, ca.reason || 'Cast schedules confirmed.');
    miniNodes.cast.className = `mini-node ${caReady ? 'pass' : 'fail'}`;
    miniNodes.cast.querySelector('.mini-badge').textContent = caReady ? 'PASS' : 'FAIL';

    const castRosterEl = document.getElementById('castRoster');
    castRosterEl.innerHTML = '';
    const castList = ca.metadata?.cast || [];
    const availMap = ca.metadata?.cast_members_availability || {};

    if (castList.length > 0) {
      castList.forEach(actor => {
        const isAvail = availMap[actor.cast_id] === true || (actor.availability || '').toUpperCase() === 'FULL_DAY';
        const row = document.createElement('div');
        row.className = `cast-row ${isAvail ? 'available' : 'unavailable'}`;
        const initials = (actor.name || actor.cast_id).split(' ').map(n => n[0]).join('').slice(0, 2);
        row.innerHTML = `
          <div class="cast-avatar">${initials}</div>
          <div class="cast-details">
            <span class="cast-name">${actor.name} (${actor.cast_id})</span>
            <span class="cast-role">${actor.role_name || actor.role_on_call_sheet || 'Actor'}</span>
          </div>
          <span class="cast-avail-badge">${actor.availability || (isAvail ? 'AVAILABLE' : 'UNAVAILABLE')}</span>
        `;
        castRosterEl.appendChild(row);
      });
    } else {
      castRosterEl.innerHTML = '<span class="gear-notes">No primary cast mapped.</span>';
    }
    document.getElementById('castJsonCode').textContent = JSON.stringify(ca, null, 2);

    logToTerminal('AD_ORCHESTRATOR', `Assessment complete. Status: ${all_departments_ready ? 'ALL READY' : 'BLOCKED - ' + failed_departments.join(', ')}`);
  }

  function renderDeptCard(deptKey, isReady, reason) {
    const card = document.getElementById(`card${capitalize(deptKey)}`);
    const badge = document.getElementById(`${deptKey}Badge`);
    const reasonEl = document.getElementById(`${deptKey}Reason`);

    if (card && badge && reasonEl) {
      badge.textContent = isReady ? 'READY' : 'BLOCKED';
      badge.className = `dept-status-badge ${isReady ? 'ready' : 'blocked'}`;
      reasonEl.textContent = reason;
    }
  }

  /* ==========================================================================
     Replan Recommendation Matrix Rendering
     ========================================================================== */
  function renderReplanPanel(replan, failedDepts) {
    if (!replan) return;
    replanContainer.classList.remove('hidden');

    // Update failed department tags
    failedDeptsBadges.innerHTML = '';
    failedDepts.forEach(d => {
      const tag = document.createElement('span');
      tag.className = 'dept-fail-tag';
      tag.textContent = `${d.toUpperCase()} BLOCKED`;
      failedDeptsBadges.appendChild(tag);
    });

    replanAlertDesc.textContent = `Department check flagged blockers in ${failedDepts.join(', ').toUpperCase()}. Replan agent generated contingency scheduling recommendations.`;
    replanStrategyText.textContent = replan.search_strategy || 'Prioritized alternative READY scenes from production DB to avoid downtime.';

    // Populate alternatives
    replanAlternativesList.innerHTML = '';
    const alts = replan.alternatives || [];
    
    alts.forEach((alt, idx) => {
      const isTop = idx === 0;
      const card = document.createElement('div');
      card.className = 'alt-scene-card';
      const pct = Math.round(alt.score * 100);

      const changesHtml = (alt.required_changes || [])
        .map(c => `<li>${c}</li>`)
        .join('');

      card.innerHTML = `
        <div class="alt-left">
          <div class="alt-header-row">
            <span class="alt-id">${alt.scene_id}</span>
            <h4 class="alt-title">${alt.title || 'Alternative Scene'}</h4>
            <span class="alt-score-badge">★ ${pct}% Compatibility</span>
            ${isTop ? '<span class="preset-tag ready">Recommended Swap</span>' : ''}
          </div>
          <p class="alt-rationale">${alt.rationale}</p>
          <span class="alt-changes-title">REQUIRED SCHEDULE ADJUSTMENTS:</span>
          <ul class="alt-changes-list">${changesHtml}</ul>
        </div>
        <button class="alt-action-btn" data-swap-id="${alt.scene_id}">
          Approve Swap (${alt.scene_id})
        </button>
      `;

      card.querySelector('.alt-action-btn').addEventListener('click', () => {
        applyScheduleSwap(currentSceneId, alt.scene_id);
      });

      replanAlternativesList.appendChild(card);
    });
  }

  /* ==========================================================================
     Schedule Swap Simulation
     ========================================================================== */
  async function applyScheduleSwap(blockedSceneId, targetSceneId) {
    try {
      const res = await fetch('/api/replan/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          blocked_scene_id: blockedSceneId,
          target_scene_id: targetSceneId,
          reason: 'Assistant Director approved swap from CineAI recommendation',
        }),
      });

      const data = await res.json();
      if (data.success) {
        showToast(`Schedule Updated! Swapped ${targetSceneId} into current shoot slot.`, 'success');
        logToTerminal('REPLAN_AGENT', `Contingency executed: Swapped ${targetSceneId} for ${blockedSceneId}. Notifications sent to department leads.`);
        
        // Switch to the newly swapped scene
        setTimeout(() => {
          selectScene(targetSceneId, true);
        }, 1200);
      }
    } catch (err) {
      showToast(`Failed to apply swap: ${err.message}`, 'error');
    }
  }

  /* ==========================================================================
     Terminal Logging & Clipboard
     ========================================================================== */
  function logToTerminal(author, text) {
    const time = new Date().toTimeString().split(' ')[0];
    const entry = document.createElement('div');
    entry.className = `term-entry ${author.toLowerCase()}`;
    entry.innerHTML = `
      <span class="term-time">[${time}]</span>
      <span class="term-author">[${author}]</span>
      <span class="term-text">${escapeHtml(text)}</span>
    `;
    terminalFeed.appendChild(entry);
    terminalFeed.scrollTop = terminalFeed.scrollHeight;
  }

  function copyReportToClipboard() {
    if (!currentAssessment) {
      showToast('No assessment data to copy', 'error');
      return;
    }
    const { scene_brief, overall_status, failed_departments, replan } = currentAssessment;
    const reportText = `
=== CINEAI ASSISTANT DIRECTOR PRODUCTION BRIEF ===
Scene ID: ${scene_brief.scene_id} - ${scene_brief.title}
Location: ${scene_brief.location_name} (${scene_brief.int_ext})
Shoot Date/Time: ${scene_brief.shoot_date} ${scene_brief.shoot_time}
Overall Status: ${overall_status}
${failed_departments.length > 0 ? `Failed Departments: ${failed_departments.join(', ')}` : 'All 5 Departments READY for shooting.'}
${replan ? `Recommended Contingency Swap: ${replan.recommended_scene}` : ''}
===================================================
`.trim();

    navigator.clipboard.writeText(reportText).then(() => {
      showToast('Production Brief copied to clipboard!', 'success');
    });
  }

  function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${type === 'success' ? '✓' : '⚠️'}</span><span>${message}</span>`;
    toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.remove();
    }, 3500);
  }

  function capitalize(s) {
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  function escapeHtml(str) {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
});
