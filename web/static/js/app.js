/**
 * Porta GEAR - Console de Controle de Acesso
 * Identidade Visual e Arquitetura: GEAR (Grupo de Estudos Avançados em Robótica - UFMG)
 * Proteção com Autenticação de Administrador e Validação Anti-Bypass
 */

// Chave para persistência da credencial de sessão do navegador
const AUTH_STORAGE_KEY = 'gear_auth_token';

function getAuthToken() {
  return sessionStorage.getItem(AUTH_STORAGE_KEY) || '';
}

function setAuthToken(token) {
  if (token) {
    sessionStorage.setItem(AUTH_STORAGE_KEY, token);
  } else {
    sessionStorage.removeItem(AUTH_STORAGE_KEY);
  }
}

// Wrapper seguro de requisições HTTP: injeta credencial e intercepta tentativas não autorizadas
async function authFetch(url, options = {}) {
  options.headers = options.headers || {};
  const token = getAuthToken();
  if (token) {
    options.headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(url, options);

  // Se o servidor rejeitar com 401, a tela de bloqueio é forçada imediatamente
  if (res.status === 401) {
    setAuthToken(null);
    pararPolling();
    showAuthOverlay('Acesso não autorizado ou sessão expirada. Digite a senha.');
    throw new Error('401 Unauthorized');
  }

  return res;
}

// Estado da Aplicação
const state = {
  doorOpen: false,
  doorRemainingTime: 0,
  currentMode: 'PRODUCAO',
  users: [],
  filtroMembros: 'todos',
  logs: [],
  logPage: 1,
  logPageSize: 20,
  logMaxPages: 3,
  logSearch: '',
  isScanning: false,
  nextSuggestedId: '001',
  wizardData: {
    id: '',
    nome: '',
    uid: ''
  }
};

let pollTimer = null;

function iniciarPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(fetchStatus, 1500);
}

function pararPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function iniciarPainel() {
  fetchStatus();
  fetchUsers();
  fetchLogs();
  iniciarPolling();
}

// Sintetizador de Som Web Audio
function playAudioTone(type = 'unlock') {
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    const ctx = new AudioContext();

    if (type === 'unlock') {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(800, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(1200, ctx.currentTime + 0.15);
      gain.gain.setValueAtTime(0.18, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.28);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.28);
    } else if (type === 'denied') {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(220, ctx.currentTime);
      osc.frequency.setValueAtTime(160, ctx.currentTime + 0.15);
      gain.gain.setValueAtTime(0.18, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.3);
    }
  } catch (e) {}
}

// Toast Notifier
function showToast(message, type = 'success') {
  const container = document.getElementById('toast-shelf');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast-item ${type}`;
  toast.innerHTML = `
    <span>${type === 'error' ? '❌' : type === 'warning' ? '⚠️' : '✅'}</span>
    <div>${message}</div>
  `;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(8px)';
    toast.style.transition = 'all 0.25s ease';
    setTimeout(() => toast.remove(), 250);
  }, 4000);
}

// Controle de Modais
function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.add('show');
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.remove('show');
}

/* ==========================================================================
   TELA DE BLOQUEIO / AUTENTICAÇÃO
   ========================================================================== */
function showAuthOverlay(msg = '') {
  const overlay = document.getElementById('auth-overlay');
  const errBox = document.getElementById('auth-error-box');
  const pwdInput = document.getElementById('input-senha-login');

  if (errBox) {
    if (msg) {
      errBox.textContent = msg;
      errBox.style.display = 'block';
    } else {
      errBox.style.display = 'none';
    }
  }
  if (overlay) {
    overlay.classList.remove('hidden');
    overlay.style.display = 'flex';
  }
  if (pwdInput) {
    pwdInput.value = '';
    setTimeout(() => pwdInput.focus(), 150);
  }
}

function hideAuthOverlay() {
  const overlay = document.getElementById('auth-overlay');
  if (overlay) {
    overlay.classList.add('hidden');
    overlay.style.display = 'none';
  }
}

async function verificarAutenticacaoInicial() {
  const token = getAuthToken();
  if (!token) {
    showAuthOverlay();
    return;
  }

  try {
    const res = await fetch('/api/auth/verificar', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (res.ok) {
      hideAuthOverlay();
      iniciarPainel();
    } else {
      setAuthToken(null);
      showAuthOverlay('Sessão expirada. Digite a senha do administrador.');
    }
  } catch (e) {
    showAuthOverlay();
  }
}

async function realizarLogin(e) {
  if (e) e.preventDefault();

  const pwdInput = document.getElementById('input-senha-login');
  const errBox = document.getElementById('auth-error-box');
  const btn = document.getElementById('btn-submit-login');
  const btnText = document.getElementById('btn-submit-login-text');

  const senha = (pwdInput ? pwdInput.value : '').trim();
  if (!senha) return;

  if (btn) btn.disabled = true;
  if (btnText) btnText.textContent = 'Desbloqueando...';
  if (errBox) errBox.style.display = 'none';

  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ senha })
    });
    const data = await res.json();

    if (data.sucesso && data.token) {
      setAuthToken(data.token);
      hideAuthOverlay();
      showToast('Painel desbloqueado com sucesso!');
      iniciarPainel();
    } else {
      if (errBox) {
        errBox.textContent = data.erro || 'Senha incorreta. Tente novamente.';
        errBox.style.display = 'flex';
      }
      if (pwdInput) {
        pwdInput.focus();
        pwdInput.select();
      }
    }
  } catch (err) {
    if (errBox) {
      errBox.textContent = 'Erro ao conectar ao servidor.';
      errBox.style.display = 'flex';
    }
  } finally {
    if (btn) btn.disabled = false;
    if (btnText) btnText.textContent = 'Desbloquear';
  }
}

async function realizarLogout() {
  if (!confirm('Deseja bloquear o painel de acesso da porta?')) return;

  try {
    await authFetch('/api/auth/logout', { method: 'POST' });
  } catch (e) {}

  setAuthToken(null);
  pararPolling();
  showAuthOverlay('Painel bloqueado com segurança.');
  showToast('Painel trancado.', 'warning');
}



function toggleVisibilidadeSenha(inputId, btn) {
  const input = document.getElementById(inputId);
  if (!input) return;
  if (input.type === 'password') {
    input.type = 'text';
    if (btn) btn.textContent = '🙈';
  } else {
    input.type = 'password';
    if (btn) btn.textContent = '👁️';
  }
}

function toggleVisibilidadeSenhaSvg(inputId, btn) {
  const input = document.getElementById(inputId);
  if (!input) return;
  const isPassword = input.type === 'password';
  input.type = isPassword ? 'text' : 'password';

  const svg = btn ? btn.querySelector('svg') : null;
  if (svg) {
    if (isPassword) {
      // Ícone de olho cortado (modo texto visível)
      svg.innerHTML = `
        <path d="M12 7c2.76 0 5 2.24 5 5 0 .65-.13 1.26-.36 1.83l2.92 2.92c1.51-1.26 2.7-2.89 3.44-4.75-1.73-4.39-6-7.5-11-7.5-1.4 0-2.74.25-3.98.7l2.16 2.16C10.74 7.13 11.35 7 12 7zM2 4.27l2.28 2.28.46.46C3.08 8.3 1.78 10.02 1 12c1.73 4.39 6 7.5 11 7.5 1.55 0 3.03-.3 4.38-.84l.42.42L19.73 22 21 20.73 3.27 3 2 4.27zM7.53 9.8l1.55 1.55c-.05.21-.08.43-.08.65 0 1.66 1.34 3 3 3 .22 0 .44-.03.65-.08l1.55 1.55c-.67.33-1.41.53-2.2.53-2.76 0-5-2.24-5-5 0-.79.2-1.53.53-2.2zm4.31-.78l3.15 3.15.02-.16c0-1.66-1.34-3-3-3l-.17.01z"/>
      `;
    } else {
      // Ícone de olho normal (modo senha oculta)
      svg.innerHTML = `
        <path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/>
      `;
    }
  }
}

/* ==========================================================================
   ATUALIZAÇÃO DE STATUS
   ========================================================================== */
async function fetchStatus() {
  try {
    const res = await authFetch('/api/status');
    const data = await res.json();
    if (!data.sucesso) return;

    // Estado da Fechadura
    const isOpen = data.porta.aberta;
    state.doorOpen = isOpen;
    state.doorRemainingTime = data.porta.tempo_restante;

    const statDoorText = document.getElementById('stat-door-text');
    const statDoorIcon = document.getElementById('stat-door-icon');
    const unlockBtnLabel = document.getElementById('btn-unlock-label');

    const heroCard = document.getElementById('door-hero-card');
    const heroTitle = document.getElementById('door-hero-title');
    const heroCaption = document.getElementById('door-hero-caption');

    if (isOpen) {
      if (statDoorText) {
        statDoorText.textContent = `Aberta (${data.porta.tempo_restante.toFixed(1)}s)`;
        statDoorText.style.color = 'var(--color-success)';
      }
      if (statDoorIcon) {
        statDoorIcon.style.color = 'var(--color-success)';
      }
      if (unlockBtnLabel) {
        unlockBtnLabel.textContent = `Aberta (${data.porta.tempo_restante.toFixed(1)}s)`;
      }
      if (heroCard) {
        heroCard.classList.add('open');
        heroTitle.textContent = 'Fechadura Destravada (Relé Ativo)';
        heroTitle.style.color = 'var(--color-success)';
        heroCaption.textContent = `Acesso liberado &bull; Retornando ao bloqueio em ${data.porta.tempo_restante.toFixed(1)} segundos...`;
      }
    } else {
      if (statDoorText) {
        statDoorText.textContent = 'Trancada';
        statDoorText.style.color = 'var(--gear-ink)';
      }
      if (statDoorIcon) {
        statDoorIcon.style.color = 'var(--gear-red)';
      }
      if (unlockBtnLabel) {
        unlockBtnLabel.textContent = 'Destravar Fechadura';
      }
      if (heroCard) {
        heroCard.classList.remove('open');
        heroTitle.textContent = 'Fechadura Trancada';
        heroTitle.style.color = 'var(--gear-ink)';
        heroCaption.textContent = data.porta.ultimo_acionamento
          ? `Último acesso liberado às ${data.porta.ultimo_acionamento} &bull; Relé em repouso`
          : 'Acesso bloqueado por segurança &bull; Fechadura pronta para leitura';
      }
    }

    // Estatísticas
    document.getElementById('stat-total').textContent = data.estatisticas.total_usuarios;
    document.getElementById('stat-active').textContent = data.estatisticas.usuarios_ativos;

    // Modo Operacional
    state.currentMode = data.modo;
    applyModeUI(data.modo);

  } catch (err) {
    // 401 é tratado por authFetch
  }
}

// Aplica Modo na Interface
function applyModeUI(modo) {
  const isCadastro = modo === 'CADASTRO';

  const pillProd = document.getElementById('pill-mode-producao');
  const pillCad = document.getElementById('pill-mode-cadastro');
  const strip = document.getElementById('mode-strip');
  const stripText = document.getElementById('mode-strip-text');
  const stripBtn = document.getElementById('mode-strip-action-btn');

  const cadastroActions = document.getElementById('cadastro-actions-group');
  const producaoNotice = document.getElementById('producao-mode-notice');

  if (isCadastro) {
    if (pillProd) pillProd.className = 'mode-pill-btn';
    if (pillCad) pillCad.className = 'mode-pill-btn active cadastro';
    if (strip) strip.className = 'mode-banner-strip cadastro';
    if (stripText) {
      stripText.innerHTML = `
        <strong>Modo de Cadastro:</strong> Leitor livre para registro e substituição de tags. Abertura automática da porta suspensa.
      `;
    }
    if (stripBtn) {
      stripBtn.textContent = 'Voltar para Modo Produção';
      stripBtn.onclick = () => setSystemMode('PRODUCAO');
    }

    if (cadastroActions) cadastroActions.style.display = 'flex';
    if (producaoNotice) producaoNotice.style.display = 'none';

  } else {
    if (pillProd) pillProd.className = 'mode-pill-btn active producao';
    if (pillCad) pillCad.className = 'mode-pill-btn';
    if (strip) strip.className = 'mode-banner-strip producao';
    if (stripText) {
      stripText.innerHTML = `
        <strong>Modo de Produção:</strong> Leitor e fechadura operando continuamente para liberação de membros cadastrados.
      `;
    }
    if (stripBtn) {
      stripBtn.textContent = 'Mudar para Modo Cadastro';
      stripBtn.onclick = () => setSystemMode('CADASTRO');
    }

    if (cadastroActions) cadastroActions.style.display = 'none';
    if (producaoNotice) producaoNotice.style.display = 'flex';
  }
}

// Alterar Modo
async function setSystemMode(novoModo) {
  try {
    const res = await authFetch('/api/modo', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ modo: novoModo })
    });
    const data = await res.json();
    if (data.sucesso) {
      showToast(data.mensagem);
      fetchStatus();
      fetchUsers();
    } else {
      showToast(data.erro || 'Falha ao alterar modo', 'error');
    }
  } catch (e) {
    // 401 tratado por authFetch
  }
}

// Acionar Abertura da Fechadura
async function triggerOpenDoor() {
  try {
    const res = await authFetch('/api/porta/abrir', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ duracao: 3.5 })
    });
    const data = await res.json();
    if (data.sucesso) {
      playAudioTone('unlock');
      showToast('🚪 Fechadura destravada com sucesso!');
      fetchStatus();
      fetchLogs();
    } else {
      showToast(data.erro || 'Falha ao acionar a fechadura', 'error');
    }
  } catch (e) {
    // 401 tratado por authFetch
  }
}

// Buscar Membros
async function fetchUsers() {
  const searchInput = document.getElementById('user-search-input');
  const busca = searchInput ? searchInput.value.trim() : '';

  try {
    const url = busca ? `/api/usuarios?busca=${encodeURIComponent(busca)}` : '/api/usuarios';
    const res = await authFetch(url);
    const data = await res.json();
    if (!data.sucesso) return;

    state.users = data.usuarios;
    state.nextSuggestedId = data.proximo_id;

    renderUsersTable(data.usuarios);
  } catch (e) {
    // 401 tratado por authFetch
  }
}

function setFiltroMembros(filtro) {
  state.filtroMembros = filtro;
  ['todos', 'ativos', 'inativos'].forEach(f => {
    const btn = document.getElementById(`filter-btn-${f}`);
    if (btn) btn.classList.toggle('active', f === filtro);
  });
  renderUsersTable(state.users);
}

function renderUsersTable(users) {
  const tbody = document.getElementById('users-table-rows');
  if (!tbody) return;

  const validos = (users || []).filter(u => !u.excluido);
  const total = validos.length;
  const ativos = validos.filter(u => u.ativo).length;
  const inativos = total - ativos;

  const elTodos = document.getElementById('count-membros-todos');
  const elAtivos = document.getElementById('count-membros-ativos');
  const elInativos = document.getElementById('count-membros-inativos');
  if (elTodos) elTodos.textContent = total;
  if (elAtivos) elAtivos.textContent = ativos;
  if (elInativos) elInativos.textContent = inativos;

  let filtrados = users || [];
  if (state.filtroMembros === 'ativos') {
    filtrados = filtrados.filter(u => !u.excluido && u.ativo);
  } else if (state.filtroMembros === 'inativos') {
    filtrados = filtrados.filter(u => !u.excluido && !u.ativo);
  }

  if (filtrados.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="5" style="text-align: center; color: var(--gear-slate); padding: 36px;">
          ${state.filtroMembros !== 'todos' ? 'Nenhum membro com a situação selecionada.' : 'Nenhum membro cadastrado.'}
        </td>
      </tr>
    `;
    return;
  }

  const isCadastro = state.currentMode === 'CADASTRO';

  tbody.innerHTML = users.map(u => {
    const isExcluded = u.excluido;
    const statusHtml = isExcluded
      ? `<span class="badge-status desligado"><span class="status-dot-sm"></span>Desligado</span>`
      : u.ativo
      ? `<span class="badge-status ativo"><span class="status-dot-sm"></span>Liberado</span>`
      : `<span class="badge-status inativo"><span class="status-dot-sm"></span>Bloqueado</span>`;

    let actionsHtml = '';
    if (isExcluded) {
      actionsHtml = `<span style="color: var(--gear-slate); font-size: 0.8rem;">Histórico mantido</span>`;
    } else if (!isCadastro) {
      actionsHtml = `
        <div class="row-actions">
          <button class="btn-action-pill" style="opacity: 0.8;" onclick="alert('Para cadastrar ou trocar cartões, ative o Modo Cadastro no topo.')" title="Requer Modo Cadastro">
            🔒 Modo Produção
          </button>
        </div>
      `;
    } else {
      actionsHtml = `
        <div class="row-actions">
          <button class="btn-action-pill trocar-cartao" onclick="abrirModalTrocarCartao('${u.id}', '${u.nome}', '${u.uid_cartao}')" title="Substituir cartão RFID">
            🔁 Trocar Cartão
          </button>
          <button class="btn-action-pill editar" onclick="abrirModalEditarNome('${u.id}', '${u.nome}')" title="Editar nome">
            ✏️ Editar
          </button>
          <button class="btn-action-icon toggle" onclick="toggleUserStatus('${u.id}', ${!u.ativo})" title="${u.ativo ? 'Bloquear acesso' : 'Liberar acesso'}">
            ${u.ativo ? '⏸️' : '▶️'}
          </button>
          <button class="btn-action-icon delete" onclick="confirmDeleteUser('${u.id}', '${u.nome}')" title="Remover membro">
            🗑️
          </button>
        </div>
      `;
    }

    return `
      <tr>
        <td><span class="badge-id">${u.id}</span></td>
        <td><strong>${u.nome}</strong></td>
        <td><span class="badge-uid">${u.uid_cartao}</span></td>
        <td>${statusHtml}</td>
        <td>${actionsHtml}</td>
      </tr>
    `;
  }).join('');
}

/* ==========================================================================
   1. CADASTRO MANUAL
   ========================================================================== */
function abrirModalCadastroManual() {
  document.getElementById('manual-membro-id').value = state.nextSuggestedId;
  document.getElementById('manual-membro-nome').value = '';
  document.getElementById('manual-membro-uid').value = '';
  document.getElementById('manual-membro-ativo').checked = true;
  openModal('modal-cadastro-manual');
  setTimeout(() => document.getElementById('manual-membro-nome').focus(), 150);
}

async function salvarCadastroManual(event) {
  event.preventDefault();

  const id = document.getElementById('manual-membro-id').value.trim();
  const nome = document.getElementById('manual-membro-nome').value.trim();
  const uid = document.getElementById('manual-membro-uid').value.trim();
  const ativo = document.getElementById('manual-membro-ativo').checked;

  if (!id || !nome || !uid) {
    showToast('Preencha todos os campos obrigatórios.', 'warning');
    return;
  }

  try {
    const res = await authFetch('/api/usuarios', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, nome, uid_cartao: uid, ativo })
    });
    const data = await res.json();
    if (data.sucesso) {
      showToast(data.mensagem);
      closeModal('modal-cadastro-manual');
      fetchUsers();
      fetchStatus();
    } else {
      showToast(data.erro || 'Falha ao cadastrar membro.', 'error');
    }
  } catch (e) {
    // 401 tratado por authFetch
  }
}

/* ==========================================================================
   2. CADASTRO AUTOMATIZADO (WIZARD ESTILO TERMINAL)
   ========================================================================== */
function iniciarCadastroAutomatizado() {
  state.wizardData = {
    id: state.nextSuggestedId,
    nome: '',
    uid: ''
  };

  setWizardStep(1);

  document.getElementById('wiz-id-badge').textContent = state.nextSuggestedId;
  document.getElementById('wiz-input-nome').value = '';
  document.getElementById('wiz-input-uid').value = '';

  openModal('modal-cadastro-automatizado');
  setTimeout(() => document.getElementById('wiz-input-nome').focus(), 150);
}

function setWizardStep(stepNumber) {
  document.querySelectorAll('.wizard-step-panel').forEach(p => p.classList.remove('active'));
  document.getElementById(`wiz-step-${stepNumber}`).classList.add('active');

  for (let i = 1; i <= 3; i++) {
    const node = document.getElementById(`wiz-node-${i}`);
    if (!node) continue;
    node.className = 'wizard-step-node';
    if (i < stepNumber) {
      node.classList.add('done');
    } else if (i === stepNumber) {
      node.classList.add('active');
    }
  }
}

function wizardAvancarParaLeitura() {
  const nome = document.getElementById('wiz-input-nome').value.trim();
  if (!nome) {
    showToast('Digite o nome do membro para prosseguir.', 'warning');
    document.getElementById('wiz-input-nome').focus();
    return;
  }

  state.wizardData.nome = nome;
  document.getElementById('wiz-display-nome').textContent = nome;
  document.getElementById('wiz-display-id').textContent = state.wizardData.id;

  setWizardStep(2);
  setTimeout(() => {
    const input = document.getElementById('wiz-input-uid');
    if (input) input.focus();
    capturarTagParaWizard();
  }, 200);
}

function wizardVoltarPasso1() {
  setWizardStep(1);
  setTimeout(() => document.getElementById('wiz-input-nome').focus(), 150);
}

async function wizardConfirmarLeitura() {
  const uid = document.getElementById('wiz-input-uid').value.trim();
  if (!uid) {
    showToast('Aproxime o cartão no leitor ou informe o UID.', 'warning');
    document.getElementById('wiz-input-uid').focus();
    return;
  }

  state.wizardData.uid = uid;

  try {
    const res = await authFetch('/api/usuarios', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id: state.wizardData.id,
        nome: state.wizardData.nome,
        uid_cartao: uid,
        ativo: true
      })
    });
    const data = await res.json();

    if (data.sucesso) {
      playAudioTone('unlock');

      document.getElementById('wiz-resumo-nome').textContent = state.wizardData.nome;
      document.getElementById('wiz-resumo-id').textContent = state.wizardData.id;
      document.getElementById('wiz-resumo-uid').textContent = uid;

      setWizardStep(3);
      fetchUsers();
      fetchStatus();
    } else {
      playAudioTone('denied');
      showToast(data.erro || 'Falha ao cadastrar membro.', 'error');
    }
  } catch (e) {
    // 401 tratado por authFetch
  }
}

function setupWizardInputEvents() {
  const inputNome = document.getElementById('wiz-input-nome');
  if (inputNome) {
    inputNome.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        wizardAvancarParaLeitura();
      }
    });
  }

  const inputUid = document.getElementById('wiz-input-uid');
  if (inputUid) {
    inputUid.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        wizardConfirmarLeitura();
      }
    });
  }
}

/* ==========================================================================
   TROCAR CARTÃO
   ========================================================================== */
function abrirModalTrocarCartao(id, nome, currentUid) {
  document.getElementById('troca-cartao-user-id').value = id;
  document.getElementById('troca-cartao-user-name').textContent = `${nome} (ID: ${id})`;
  document.getElementById('troca-cartao-current-uid').textContent = currentUid;
  document.getElementById('troca-cartao-novo-uid').value = '';
  openModal('modal-trocar-cartao');
  setTimeout(() => document.getElementById('troca-cartao-novo-uid').focus(), 150);
}

async function salvarTrocaCartao(event) {
  event.preventDefault();

  const id = document.getElementById('troca-cartao-user-id').value;
  const novoUid = document.getElementById('troca-cartao-novo-uid').value.trim();

  if (!novoUid) {
    showToast('Informe o novo UID do cartão.', 'warning');
    return;
  }

  try {
    const res = await authFetch(`/api/usuarios/${id}/trocar-cartao`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ novo_uid: novoUid })
    });
    const data = await res.json();
    if (data.sucesso) {
      showToast(data.mensagem);
      closeModal('modal-trocar-cartao');
      fetchUsers();
      fetchStatus();
    } else {
      showToast(data.erro || 'Falha ao substituir cartão.', 'error');
    }
  } catch (e) {
    // 401 tratado por authFetch
  }
}

/* ==========================================================================
   EDITAR NOME
   ========================================================================== */
function abrirModalEditarNome(id, currentName) {
  document.getElementById('edit-nome-user-id').value = id;
  document.getElementById('edit-nome-user-id-display').value = id;
  document.getElementById('edit-nome-valor').value = currentName;
  openModal('modal-editar-nome');
  setTimeout(() => document.getElementById('edit-nome-valor').focus(), 150);
}

async function salvarEdicaoNome(event) {
  event.preventDefault();

  const id = document.getElementById('edit-nome-user-id').value;
  const novoNome = document.getElementById('edit-nome-valor').value.trim();

  if (!novoNome) {
    showToast('Informe o novo nome do membro.', 'warning');
    return;
  }

  try {
    const res = await authFetch(`/api/usuarios/${id}/trocar-nome`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ novo_nome: novoNome })
    });
    const data = await res.json();
    if (data.sucesso) {
      showToast(data.mensagem);
      closeModal('modal-editar-nome');
      fetchUsers();
    } else {
      showToast(data.erro || 'Falha ao atualizar nome.', 'error');
    }
  } catch (e) {
    // 401 tratado por authFetch
  }
}

/* ==========================================================================
   STATUS E REMOÇÃO
   ========================================================================== */
async function toggleUserStatus(id, newStatus) {
  try {
    const res = await authFetch(`/api/usuarios/${id}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ativo: newStatus })
    });
    const data = await res.json();
    if (data.sucesso) {
      showToast(data.mensagem);
      fetchUsers();
      fetchStatus();
    } else {
      showToast(data.erro || 'Erro ao alterar permissão', 'error');
    }
  } catch (e) {
    // 401 tratado por authFetch
  }
}

async function confirmDeleteUser(id, nome) {
  if (!confirm(`Deseja realmente remover o membro '${nome}' (ID: ${id})?\n\nO acesso à porta será revogado e o histórico será preservado.`)) {
    return;
  }

  try {
    const res = await authFetch(`/api/usuarios/${id}`, { method: 'DELETE' });
    const data = await res.json();
    if (data.sucesso) {
      showToast(data.mensagem);
      fetchUsers();
      fetchStatus();
    } else {
      showToast(data.erro || 'Falha ao remover cadastro', 'error');
    }
  } catch (e) {
    // 401 tratado por authFetch
  }
}

/* ==========================================================================
   VERIFICAÇÃO RÁPIDA DE CARTÃO
   ========================================================================== */
async function checarCartao() {
  const input = document.getElementById('check-card-input');
  const uid = input ? input.value.trim() : '';
  const resultBox = document.getElementById('check-result-box');

  if (!uid) {
    showToast('Informe o UID do cartão para verificar.', 'warning');
    return;
  }

  try {
    const res = await authFetch('/api/leitor/identificar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ uid })
    });
    const data = await res.json();

    if (!data.sucesso) {
      showToast(data.erro || 'Erro na verificação do cartão', 'error');
      return;
    }

    if (resultBox) {
      resultBox.classList.add('show');
      if (data.modo === 'CADASTRO') {
        if (data.ja_cadastrado) {
          resultBox.className = 'check-result-card success';
          resultBox.innerHTML = `
            <strong>Cartão Cadastrado:</strong> Pertence a <strong>${data.usuario.nome}</strong> (ID: ${data.usuario.id}) &bull; Situação: ${data.usuario.ativo ? 'Ativo' : 'Inativo'}.
          `;
        } else {
          resultBox.className = 'check-result-card success';
          resultBox.innerHTML = `
            <strong>Cartão Livre:</strong> UID <code>${data.uid}</code> não está vinculado a nenhum membro. Pronto para cadastro!
          `;
        }
      } else {
        if (data.autorizado) {
          playAudioTone('unlock');
          resultBox.className = 'check-result-card success';
          resultBox.innerHTML = `
            🔓 <strong>Acesso Autorizado:</strong> Membro <strong>${data.usuario.nome}</strong> (ID: ${data.usuario.id}) &bull; Fechadura destravada!
          `;
        } else {
          playAudioTone('denied');
          resultBox.className = 'check-result-card denied';
          resultBox.innerHTML = `
            ⛔ <strong>Acesso Negado:</strong> ${formatReason(data.motivo)} (UID: ${data.uid}).
          `;
        }
      }
    }

    fetchStatus();
    fetchLogs();
  } catch (e) {
    // 401 tratado por authFetch
  }
}

/* ==========================================================================
   HISTÓRICO DE ACESSOS (PAGINADO & EXPORTÁVEL)
   ========================================================================== */
async function fetchLogs() {
  try {
    const res = await authFetch('/api/registros?limite=60');
    const data = await res.json();
    if (!data.sucesso) return;

    state.logs = data.registros || [];
    renderLogsTable();
  } catch (e) {
    // 401 tratado por authFetch
  }
}

function formatReason(reason) {
  switch (reason) {
    case 'acesso_autorizado': return 'Acesso Autorizado';
    case 'usuario_inativo': return 'Acesso Negado: Membro Inativo';
    case 'cartao_nao_cadastrado': return 'Acesso Negado: Cartão Desconhecido';
    case 'liberacao_remota_console': return 'Liberação Remota via Console';
    case 'liberacao_remota_web': return 'Liberação Remota via Painel Web';
    case 'liberacao_remota_rfid': return 'Abertura Autorizada RFID';
    default: return reason || 'Registrado';
  }
}

function onLogSearchInput() {
  const input = document.getElementById('log-search-input');
  state.logSearch = input ? input.value.trim().toLowerCase() : '';
  state.logPage = 1;
  renderLogsTable();
}

function mudarPaginaLogs(delta) {
  state.logPage += delta;
  renderLogsTable();
}

function renderLogsTable() {
  const tbody = document.getElementById('logs-table-rows');
  if (!tbody) return;

  let filtrados = state.logs || [];
  if (state.logSearch) {
    filtrados = filtrados.filter(l =>
      (l.usuario_nome && l.usuario_nome.toLowerCase().includes(state.logSearch)) ||
      (l.uid_cartao && l.uid_cartao.toLowerCase().includes(state.logSearch)) ||
      (l.usuario_id && l.usuario_id.toLowerCase().includes(state.logSearch)) ||
      (l.motivo && l.motivo.toLowerCase().includes(state.logSearch))
    );
  }

  const totalItens = filtrados.length;
  const pageSize = state.logPageSize || 20;
  const maxPages = Math.min(state.logMaxPages || 3, Math.ceil(totalItens / pageSize) || 1);

  if (state.logPage > maxPages) state.logPage = maxPages;
  if (state.logPage < 1) state.logPage = 1;

  const inicio = (state.logPage - 1) * pageSize;
  const fim = Math.min(inicio + pageSize, totalItens);
  const paginaItens = filtrados.slice(inicio, fim);

  // Atualiza controles de paginação
  const infoEl = document.getElementById('log-pagination-info');
  const currentEl = document.getElementById('log-page-current');
  const btnPrev = document.getElementById('btn-log-prev');
  const btnNext = document.getElementById('btn-log-next');

  if (infoEl) infoEl.textContent = totalItens > 0 ? `Mostrando ${inicio + 1}–${fim} de ${totalItens} registros` : 'Nenhum registro';
  if (currentEl) currentEl.textContent = `Página ${state.logPage} de ${maxPages}`;
  if (btnPrev) btnPrev.disabled = (state.logPage <= 1);
  if (btnNext) btnNext.disabled = (state.logPage >= maxPages || fim >= totalItens);

  if (paginaItens.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="5" style="text-align: center; color: var(--gear-slate); padding: 36px;">
          ${state.logSearch ? 'Nenhum registro encontrado para o termo buscado.' : 'Nenhum registro de acesso registrado.'}
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = paginaItens.map(l => {
    const timeFormatted = l.data_hora ? l.data_hora.replace('T', ' ').substring(0, 19) : '-';
    const statusBadge = l.autorizado
      ? `<span class="badge-status ativo"><span class="status-dot-sm"></span>Autorizado</span>`
      : `<span class="badge-status inativo"><span class="status-dot-sm"></span>Negado</span>`;

    return `
      <tr>
        <td style="font-family: ui-monospace, monospace; color: var(--gear-slate); font-size: 0.85rem;">${timeFormatted}</td>
        <td><strong>${l.usuario_nome || '<em style="color: var(--gear-slate)">Console / Remoto</em>'}</strong></td>
        <td><span class="badge-uid">${l.uid_cartao}</span></td>
        <td>${statusBadge}</td>
        <td>${formatReason(l.motivo)}</td>
      </tr>
    `;
  }).join('');
}

function baixarLogsCSV() {
  if (!state.logs || state.logs.length === 0) {
    showToast('Nenhum registro disponível para download.', 'warning');
    return;
  }

  const linhas = ["Data e Hora;Membro;ID Usuario;Cartao UID;Resultado;Motivo"];
  state.logs.forEach(l => {
    const dt = l.data_hora ? l.data_hora.replace('T', ' ').substring(0, 19) : '-';
    const nome = (l.usuario_nome || 'Console / Remoto').replace(/;/g, ',');
    const uid = l.uid_cartao || '-';
    const uId = l.usuario_id || '-';
    const res = l.autorizado ? 'AUTORIZADO' : 'NEGADO';
    const motivo = formatReason(l.motivo).replace(/;/g, ',');
    linhas.push(`${dt};${nome};${uId};${uid};${res};${motivo}`);
  });

  const conteudo = "\uFEFF" + linhas.join("\r\n");
  const blob = new Blob([conteudo], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `historico_acessos_porta_gear_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
  showToast('Download do arquivo CSV concluído!');
}

/* ==========================================================================
   CAPTURA DIRETA NO LEITOR HARDWARE PN532 (SOB DEMANDA)
   ========================================================================== */
async function capturarTagDoLeitor(targetInputId, feedbackElemId, btnElemId) {
  if (state.isScanning) {
    showToast('Já existe uma leitura do leitor em andamento.', 'warning');
    return;
  }

  const input = document.getElementById(targetInputId);
  const feedback = document.getElementById(feedbackElemId);
  const btn = btnElemId ? document.getElementById(btnElemId) : null;
  const textoOriginalBtn = btn ? btn.innerHTML : '';

  state.isScanning = true;
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '⏳ Lendo...';
  }
  if (feedback) {
    feedback.style.display = 'block';
    feedback.style.color = 'var(--gear-blue)';
    feedback.innerHTML = '<span class="pulse-reading">📡 Aproxime o cartão físico no leitor PN532...</span>';
  }

  try {
    const res = await authFetch('/api/leitor/capturar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ timeout: 15.0 })
    });

    const data = await res.json();
    if (data.sucesso && data.uid) {
      if (input) {
        input.value = data.uid;
        input.classList.add('flash-success');
        setTimeout(() => input.classList.remove('flash-success'), 1200);
      }
      playAudioTone('unlock');
      if (feedback) {
        feedback.style.color = 'var(--color-success)';
        feedback.innerHTML = `✅ <strong>Cartão lido:</strong> <code>${data.uid}</code>`;
      }
      showToast(`Cartão ${data.uid} lido com sucesso!`);
    } else {
      if (feedback) {
        feedback.style.color = 'var(--color-danger)';
        feedback.textContent = data.erro || 'Nenhum cartão detectado.';
      }
      showToast(data.erro || 'Nenhum cartão detectado.', 'warning');
    }
  } catch (e) {
    if (feedback) {
      feedback.style.color = 'var(--color-danger)';
      feedback.textContent = 'Tempo esgotado ou leitor indisponível.';
    }
  } finally {
    state.isScanning = false;
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = textoOriginalBtn;
    }
  }
}

function capturarTagParaCheck() {
  capturarTagDoLeitor('check-card-input', 'check-card-feedback', 'btn-ler-check-card');
}

function capturarTagParaWizard() {
  capturarTagDoLeitor('wiz-input-uid', 'wiz-scan-feedback', 'btn-wiz-ler');
}

function capturarTagParaTroca() {
  capturarTagDoLeitor('troca-cartao-novo-uid', 'troca-cartao-feedback', 'btn-troca-ler');
}

function capturarTagParaManual() {
  capturarTagDoLeitor('manual-membro-uid', 'manual-membro-feedback', 'btn-manual-ler');
}

// Troca de Abas da Sidebar
function setupTabs() {
  const navButtons = document.querySelectorAll('.sidebar-nav-btn');
  navButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const tabName = btn.dataset.tab;
      navButtons.forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      const targetPane = document.getElementById(`pane-${tabName}`);
      if (targetPane) targetPane.classList.add('active');

      if (tabName === 'membros') fetchUsers();
      if (tabName === 'historico') fetchLogs();
    });
  });
}

// Máscaras automáticas em inputs hexadecimais
function setupInputMasks() {
  const hexInputs = [
    document.getElementById('manual-membro-uid'),
    document.getElementById('wiz-input-uid'),
    document.getElementById('troca-cartao-novo-uid'),
    document.getElementById('check-card-input')
  ];

  hexInputs.forEach(input => {
    if (!input) return;
    input.addEventListener('input', () => {
      input.value = input.value.replace(/[^a-fA-F0-9]/g, '').toUpperCase();
    });
  });

  const checkInput = document.getElementById('check-card-input');
  if (checkInput) {
    checkInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        checarCartao();
      }
    });
  }

  const searchInput = document.getElementById('user-search-input');
  if (searchInput) {
    let debounce;
    searchInput.addEventListener('input', () => {
      clearTimeout(debounce);
      debounce = setTimeout(fetchUsers, 220);
    });
  }
}

// Inicialização segura
window.addEventListener('DOMContentLoaded', () => {
  setupTabs();
  setupInputMasks();
  setupWizardInputEvents();

  // Verifica autenticação antes de carregar dados protegidos
  verificarAutenticacaoInicial();
});
