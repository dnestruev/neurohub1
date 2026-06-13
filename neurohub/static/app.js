const providerSelect = document.querySelector('#provider');
const apiKeyInput = document.querySelector('#apiKey');
const rememberKey = document.querySelector('#rememberKey');
const modelInput = document.querySelector('#model');
const baseUrlInput = document.querySelector('#baseUrl');
const saveSettings = document.querySelector('#saveSettings');
const clearSettings = document.querySelector('#clearSettings');
const messagesEl = document.querySelector('#messages');
const chatForm = document.querySelector('#chatForm');
const promptInput = document.querySelector('#prompt');
const sendButton = document.querySelector('#send');
const statusEl = document.querySelector('#status');
const newChat = document.querySelector('#newChat');
const exportChat = document.querySelector('#exportChat');
const welcomeTemplate = document.querySelector('#welcomeTemplate');

let providers = [];
let messages = JSON.parse(localStorage.getItem('neurohub.messages') || '[]');
let settings = JSON.parse(localStorage.getItem('neurohub.settings') || '{}');

init();

async function init() {
  const response = await fetch('/api/providers');
  const data = await response.json();
  providers = data.providers;
  for (const provider of providers) {
    const option = document.createElement('option');
    option.value = provider.id;
    option.textContent = provider.id;
    providerSelect.append(option);
  }

  providerSelect.value = settings.provider || 'openai';
  rememberKey.checked = Boolean(settings.rememberKey);
  loadProviderSettings();
  renderMessages();
  setStatus('Готов к работе');
}

providerSelect.addEventListener('change', () => {
  settings.provider = providerSelect.value;
  loadProviderSettings();
  persistSettings();
});

saveSettings.addEventListener('click', () => {
  saveCurrentProviderSettings();
  setStatus('Настройки сохранены');
});

clearSettings.addEventListener('click', () => {
  const provider = providerSelect.value;
  delete settings.providers?.[provider];
  apiKeyInput.value = '';
  rememberKey.checked = false;
  fillProviderDefaults(provider);
  persistSettings();
  setStatus('Настройки провайдера очищены');
});

newChat.addEventListener('click', () => {
  messages = [];
  persistMessages();
  renderMessages();
  setStatus('Новый чат создан');
});

exportChat.addEventListener('click', () => {
  const blob = new Blob([JSON.stringify(messages, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `neurohub-chat-${new Date().toISOString().slice(0, 19).replaceAll(':', '-')}.json`;
  link.click();
  URL.revokeObjectURL(url);
});

chatForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const text = promptInput.value.trim();
  if (!text) return;

  saveCurrentProviderSettings();
  messages.push({ role: 'user', content: text });
  promptInput.value = '';
  renderMessages();
  setBusy(true, 'Отправляю запрос...');

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ ...currentPayload(), messages }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    messages.push({ role: 'assistant', content: data.content || 'Пустой ответ' });
    persistMessages();
    renderMessages();
    const usage = data.usage?.input || data.usage?.output ? ` · tokens ${data.usage.input ?? '?'} / ${data.usage.output ?? '?'}` : '';
    setStatus(`${data.provider} · ${data.model}${usage}`);
  } catch (error) {
    renderError(error.message);
    setStatus('Ошибка запроса');
  } finally {
    setBusy(false);
  }
});

promptInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
    chatForm.requestSubmit();
  }
});

function loadProviderSettings() {
  const provider = providerSelect.value;
  const saved = settings.providers?.[provider] || {};
  fillProviderDefaults(provider);
  modelInput.value = saved.model || modelInput.value;
  baseUrlInput.value = saved.baseUrl || baseUrlInput.value;
  apiKeyInput.value = settings.rememberKey ? saved.apiKey || '' : '';
}

function fillProviderDefaults(providerId) {
  const provider = providers.find((item) => item.id === providerId);
  modelInput.value = provider?.defaultModel || '';
  baseUrlInput.value = provider?.defaultBaseUrl || '';
}

function saveCurrentProviderSettings() {
  const provider = providerSelect.value;
  settings.provider = provider;
  settings.rememberKey = rememberKey.checked;
  settings.providers ||= {};
  settings.providers[provider] = {
    model: modelInput.value.trim(),
    baseUrl: baseUrlInput.value.trim(),
    apiKey: rememberKey.checked ? apiKeyInput.value.trim() : '',
  };
  persistSettings();
}

function currentPayload() {
  return {
    provider: providerSelect.value,
    apiKey: apiKeyInput.value.trim(),
    model: modelInput.value.trim(),
    baseUrl: baseUrlInput.value.trim(),
  };
}

function persistSettings() {
  localStorage.setItem('neurohub.settings', JSON.stringify(settings));
}

function persistMessages() {
  localStorage.setItem('neurohub.messages', JSON.stringify(messages));
}

function renderMessages() {
  messagesEl.replaceChildren();
  if (messages.length === 0) {
    messagesEl.append(welcomeTemplate.content.cloneNode(true));
    return;
  }
  for (const message of messages) renderMessage(message.role, message.content);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function renderMessage(role, content) {
  const wrapper = document.createElement('article');
  wrapper.className = `message ${role}`;
  const label = document.createElement('div');
  label.className = 'role';
  label.textContent = role === 'user' ? 'Ты' : 'NeuroHub';
  const bubble = document.createElement('div');
  bubble.className = 'bubble markdown';
  bubble.innerHTML = role === 'assistant' ? renderMarkdown(content) : escapeHtml(content).replaceAll('\n', '<br>');
  wrapper.append(label, bubble);
  messagesEl.append(wrapper);
}

function renderError(content) {
  const wrapper = document.createElement('article');
  wrapper.className = 'message assistant error';
  const label = document.createElement('div');
  label.className = 'role';
  label.textContent = 'Ошибка';
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = content;
  wrapper.append(label, bubble);
  messagesEl.append(wrapper);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function renderMarkdown(markdown) {
  const blocks = [];
  let text = escapeHtml(markdown).replace(/```([\s\S]*?)```/g, (_, code) => {
    const token = `@@CODE_${blocks.length}@@`;
    blocks.push(`<pre><code>${code.trim()}</code></pre>`);
    return token;
  });

  text = text
    .replace(/^### (.*)$/gm, '<h3>$1</h3>')
    .replace(/^## (.*)$/gm, '<h2>$1</h2>')
    .replace(/^# (.*)$/gm, '<h1>$1</h1>')
    .replace(/^[-*] (.*)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>')
    .split(/\n{2,}/)
    .map((part) => part.startsWith('<h') || part.startsWith('<ul') || part.startsWith('<pre') ? part : `<p>${part.replaceAll('\n', '<br>')}</p>`)
    .join('');

  return blocks.reduce((html, block, index) => html.replace(`@@CODE_${index}@@`, block), text);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function setBusy(isBusy, status = '') {
  sendButton.disabled = isBusy;
  sendButton.textContent = isBusy ? 'Думаю...' : 'Отправить';
  if (status) setStatus(status);
}

function setStatus(text) {
  statusEl.textContent = text;
}
