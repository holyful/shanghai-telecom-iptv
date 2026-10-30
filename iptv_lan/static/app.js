/* HomeCast: same-origin, buildless Shanghai Telecom IPTV frontend. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const state = {
    status: null, connected: false, channels: [], channelsLoaded: false,
    channelsError: false, loadedSuccess: undefined, selectedId: null,
    group: null, query: '', programmes: [], logs: [], logsLoaded: false,
    guideController: null, guideSequence: 0, pollTimer: null, polling: null,
    refreshPending: false, saving: false, lastLogsFetch: 0,
    channelsLoading: false, logsLoading: false, channelBoundary: Infinity,
  };
  const number = new Intl.NumberFormat('zh-CN');
  const timeZone = 'Asia/Shanghai';
  const timeFormat = new Intl.DateTimeFormat('zh-CN', { timeZone, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
  const shortDate = new Intl.DateTimeFormat('zh-CN', { timeZone, month: '2-digit', day: '2-digit' });
  const longDate = new Intl.DateTimeFormat('zh-CN', { timeZone, year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' });
  const calendarDate = new Intl.DateTimeFormat('en-US', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit' });
  const epoch = () => Date.now() / 1000;
  const validTime = value => typeof value === 'number' && Number.isFinite(value) && value > 0;
  const time = value => validTime(value) ? timeFormat.format(new Date(value * 1000)) : '--';
  const dateTime = value => validTime(value) ? `${shortDate.format(new Date(value * 1000))} ${time(value)}` : '--';
  const count = value => Number.isFinite(value) ? number.format(value) : '--';
  function dateValue(date = new Date()) {
    const parts = Object.fromEntries(calendarDate.formatToParts(date).map(part => [part.type, part.value]));
    return `${parts.year}-${parts.month}-${parts.day}`;
  }
  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined && text !== null) element.textContent = String(text);
    return element;
  }
  function icon(name) {
    const element = node('i');
    element.dataset.lucide = name;
    element.setAttribute('aria-hidden', 'true');
    return element;
  }
  function icons() {
    if (window.lucide) window.lucide.createIcons({ attrs: { 'aria-hidden': 'true', focusable: 'false' } });
  }
  function text(id, value) { $(id).textContent = value ?? ''; }
  function show(id, visible) { $(id).hidden = !visible; }
  function programmeValid(programme) {
    return programme && validTime(programme.start) && validTime(programme.end) && programme.end > programme.start;
  }
  function active(programme) {
    return programmeValid(programme) && programme.start <= epoch() && programme.end > epoch();
  }
  function progress(programme) {
    const bar = node('progress');
    bar.max = 100;
    bar.value = Math.min(100, Math.max(0, ((epoch() - programme.start) / (programme.end - programme.start)) * 100));
    bar.setAttribute('aria-label', '节目播出进度');
    return bar;
  }
  async function request(path, { method = 'GET', body, signal } = {}) {
    const controller = new AbortController();
    const abort = () => controller.abort();
    if (signal?.aborted) controller.abort();
    signal?.addEventListener('abort', abort, { once: true });
    const timeout = setTimeout(abort, 12000);
    try {
      const options = { method, signal: controller.signal, cache: 'no-store', credentials: 'same-origin', headers: { Accept: 'application/json' } };
      if (method === 'POST') {
        options.headers['Content-Type'] = 'application/json';
        options.headers['X-Requested-With'] = 'HomeCast';
        options.body = JSON.stringify(body ?? {});
      }
      const response = await fetch(path, options);
      if (!response.ok) throw new Error(`服务返回 HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      if (error.name === 'AbortError' && !signal?.aborted) throw new Error('请求超时，请稍后重试');
      if (error instanceof TypeError) throw new Error('无法连接服务，请检查网络');
      throw error;
    } finally {
      clearTimeout(timeout);
      signal?.removeEventListener('abort', abort);
    }
  }
  let toastTimer;
  function toast(message) {
    clearTimeout(toastTimer);
    text('toast', message);
    show('toast', true);
    toastTimer = setTimeout(() => show('toast', false), 4500);
  }
  function updateRefreshButton() {
    const busy = state.refreshPending || state.status?.state === 'refreshing';
    $('refresh-button').disabled = busy || !state.connected;
    $('refresh-button').querySelector('svg')?.classList.toggle('spin', busy);
    text('refresh-label', busy ? '更新中' : '立即更新');
  }
  function openSubscriptions() {
    $('subscription-m3u').value = new URL('/m3u/xteve.m3u', state.status.public_url).href;
    $('subscription-xmltv').value = new URL('/xmltv/xteve.xml', state.status.public_url).href;
    text('subscriptions-feedback', '');
    $('subscriptions-dialog').showModal();
  }
  async function copySubscription(button) {
    const kind = button.dataset.copy;
    const input = $('subscription-' + kind);
    const feedback = $('subscriptions-feedback');
    button.disabled = true;
    feedback.classList.remove('success');
    text('subscriptions-feedback', '');
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(input.value);
      } else {
        // Trusted LANs commonly use HTTP, where the Clipboard API is unavailable.
        input.focus(); input.select();
        if (!document.execCommand('copy')) throw new Error('Clipboard unavailable');
      }
      feedback.classList.add('success');
      text('subscriptions-feedback', `${kind.toUpperCase()} 订阅链接已复制`);
    } catch {
      input.focus(); input.select();
      text('subscriptions-feedback', '浏览器未允许自动复制，地址已选中');
    } finally { button.disabled = false; }
  }
  function renderStatus() {
    const status = state.status;
    $('connection').dataset.state = state.connected ? status?.state : 'offline';
    text('connection-label', !state.connected ? '连接中断' : ({ idle: '运行正常', refreshing: '更新中', error: '更新异常' }[status.state] || '状态未知'));
    show('connection-error', !state.connected);
    updateRefreshButton();
    $('subscriptions-open').disabled = !status;
    if (!status) return;
    text('channel-count', count(status.channel_count));
    text('programme-count', count(status.programme_count));
    text('coverage-end', dateTime(status.coverage_end));
    text('next-refresh', status.auto_refresh ? time(status.next_refresh) : '已关闭');
    text('next-refresh-date', status.auto_refresh && validTime(status.next_refresh) ? shortDate.format(new Date(status.next_refresh * 1000)) : '');
    text('channel-updated', validTime(status.last_success) ? `${dateTime(status.last_success)} 更新` : '尚未更新');
    text('last-attempt', validTime(status.last_attempt) ? `最近尝试 ${dateTime(status.last_attempt)}` : '尚无更新记录');
    text('app-version', status.version ? `v${String(status.version).replace(/^v/, '')}` : '');
    text('footer-cache', !state.connected ? '服务离线 · 已显示数据未同步' : status.cache_available ? '本地缓存可用' : '尚无本地缓存');
    const error = status.state === 'error';
    show('update-error', error);
    text('update-error-text', error ? `上次更新未完成：${status.last_error || '未知错误'}。${status.cache_available ? '现有缓存仍可使用。' : '当前没有可用缓存。'}` : '');
    const refreshing = status.state === 'refreshing';
    show('refresh-progress', refreshing);
    if (refreshing) {
      const value = Math.min(100, Math.max(0, Number(status.progress) || 0));
      text('refresh-stage', status.stage || '正在更新频道与节目单');
      text('progress-value', `${Math.round(value)}%`);
      $('progress-bar').value = value;
    }
    $('settings-open').disabled = !state.connected;
  }
  function renderGroups() {
    const groups = new Map();
    state.channels.forEach(channel => {
      const group = channel.group || '未分组';
      groups.set(group, (groups.get(group) || 0) + 1);
    });
    if (state.group !== null && !groups.has(state.group)) state.group = null;
    const fragment = document.createDocumentFragment();
    function filter(label, value, amount) {
      const button = node('button', 'filter', label);
      button.type = 'button';
      button.setAttribute('aria-pressed', String(state.group === value));
      const total = node('span', 'filter-count', amount);
      total.setAttribute('aria-hidden', 'true');
      button.append(total);
      button.addEventListener('click', () => {
        state.group = value;
        for (const other of $('group-filters').children) other.setAttribute('aria-pressed', String(other === button));
        renderChannels();
      });
      fragment.append(button);
    }
    filter('全部', null, state.channels.length);
    groups.forEach((amount, group) => filter(group, group, amount));
    $('group-filters').replaceChildren(fragment);
  }
  function channelShows(channel) {
    const programmes = [channel.current, channel.next].filter(programmeValid);
    return { current: programmes.find(active), next: programmes.find(p => p.start > epoch()) };
  }
  function showCell(programme, isCurrent) {
    const cell = node('td', isCurrent ? 'current-cell' : 'next-cell');
    if (programme) {
      cell.append(node('span', 'show-title', programme.title || '未命名节目'), node('div', 'show-time', `${time(programme.start)} - ${time(programme.end)}`));
      if (isCurrent) { const bar = progress(programme); bar.className = 'row-progress'; cell.append(bar); }
    } else cell.append(node('span', 'show-title muted', isCurrent ? '暂无当前节目' : '暂无节目预告'));
    return cell;
  }
  function renderChannels() {
    const query = state.query.trim().toLocaleLowerCase();
    const filtered = state.channels.filter(channel => (state.group === null || (channel.group || '未分组') === state.group)
      && `${channel.name} ${channel.group || ''} ${channel.quality || ''}`.toLocaleLowerCase().includes(query));
    const fragment = document.createDocumentFragment();
    filtered.forEach(channel => {
      const row = node('tr', channel.id === state.selectedId ? 'selected' : '');
      const cell = node('td');
      const name = node('button', 'channel-name', channel.name || '未命名频道');
      name.type = 'button';
      if (channel.id === state.selectedId) name.setAttribute('aria-current', 'true');
      name.setAttribute('aria-controls', 'programme-list');
      const details = node('div', 'channel-details');
      details.append(node('span', '', channel.group || '未分组'));
      if (channel.quality) details.append(node('span', /4k|uhd/i.test(channel.quality) ? 'quality ultra' : 'quality', channel.quality));
      cell.append(name, details);
      const shows = channelShows(channel);
      const arrow = node('td'); arrow.append(icon('chevron-right'));
      row.append(cell, showCell(shows.current, true), showCell(shows.next, false), arrow);
      row.addEventListener('click', () => selectChannel(channel.id, true));
      fragment.append(row);
    });
    // Keep keyboard focus on the selected channel when a data refresh replaces rows.
    const focusedName = $('channel-body').contains(document.activeElement) ? document.activeElement.textContent : null;
    $('channel-body').replaceChildren(fragment);
    if (focusedName) Array.from($('channel-body').querySelectorAll('button')).find(button => button.textContent === focusedName)?.focus({ preventScroll: true });
    text('filtered-count', state.channelsLoaded ? filtered.length : '--');
    text('list-summary', state.channelsLoaded ? `显示 ${filtered.length} / ${state.channels.length} 个频道` : '等待频道数据');
    show('channels-empty', filtered.length === 0);
    show('search-clear', state.query.length > 0);
    show('channels-retry', state.channelsError);
    const emptyIcon = $('channels-empty').querySelector('svg, i');
    if (emptyIcon) emptyIcon.replaceWith(icon(state.channelsError ? 'wifi-off' : state.channelsLoaded ? 'list-video' : 'loader-circle'));
    if (state.channelsError) {
      text('channels-empty-title', '频道读取失败');
      text('channels-empty-detail', '服务恢复后可重新读取频道');
    } else if (!state.channelsLoaded) {
      text('channels-empty-title', '正在读取频道');
      text('channels-empty-detail', '连接上海电信频道库');
    } else {
      text('channels-empty-title', state.channels.length ? '没有匹配的频道' : '频道库为空');
      text('channels-empty-detail', state.channels.length ? '没有符合当前搜索与分组条件的频道' : state.status?.state === 'refreshing' ? '频道更新完成后将在这里显示' : '尚未获取到频道，可尝试立即更新');
    }
    icons();
  }
  async function loadChannels({ refreshGuide = true } = {}) {
    if (state.channelsLoading) return;
    state.channelsLoading = true;
    const requestedVersion = state.status?.last_success;
    try {
      const data = await request('/api/channels');
      if (!Array.isArray(data.channels)) throw new Error('频道数据格式不正确');
      state.channels = data.channels.filter(channel => channel && channel.id !== undefined).map(channel => ({ ...channel, id: String(channel.id) }));
      state.channelsLoaded = true;
      state.channelsError = false;
      state.loadedSuccess = requestedVersion;
      state.channelBoundary = Infinity;
      // Current/next snapshots expire at programme boundaries, even without a daily refresh.
      for (const channel of state.channels) {
        for (const programme of [channel.current, channel.next].filter(programmeValid)) {
          for (const boundary of [programme.start, programme.end]) {
            if (boundary > epoch()) state.channelBoundary = Math.min(state.channelBoundary, boundary);
          }
        }
      }
      const previousId = state.selectedId;
      if (!state.channels.some(channel => channel.id === state.selectedId)) state.selectedId = state.channels[0]?.id ?? null;
      renderGroups();
      renderChannels();
      if (refreshGuide || previousId !== state.selectedId) selectChannel(state.selectedId, false);
    } catch (error) {
      state.channelsError = true;
      renderChannels();
      if (state.channels.length) toast(`频道更新失败，保留已有列表。${error.message}`);
    } finally { state.channelsLoading = false; }
  }
  async function selectChannel(id, userInitiated) {
    state.selectedId = id;
    if (userInitiated) {
      renderChannels();
      $('workspace').dataset.mobileView = 'guide';
      if (window.matchMedia('(max-width: 800px)').matches) $('guide-back').focus({ preventScroll: true });
    }
    const channel = state.channels.find(item => item.id === id);
    text('guide-title', channel?.name || '尚未选择频道');
    text('guide-meta', channel ? [channel.group || '未分组', channel.quality].filter(Boolean).join(' · ') : '--');
    await loadProgrammes();
  }
  function guideEmpty(title, detail, retry = false) {
    text('guide-empty-title', title); text('guide-empty-detail', detail);
    show('guide-empty', true); show('guide-retry', retry);
  }
  async function loadProgrammes() {
    state.guideController?.abort();
    const sequence = ++state.guideSequence;
    const channelId = state.selectedId;
    state.programmes = [];
    $('programme-list').replaceChildren();
    show('programme-list', false); show('guide-live', false); show('jump-now', false);
    $('programme-list').removeAttribute('aria-busy');
    updateGuideDate();
    if (channelId === null) { guideEmpty('暂无节目单', '等待频道数据'); return; }
    const controller = new AbortController();
    state.guideController = controller;
    const date = $('programme-date').value;
    $('programme-list').setAttribute('aria-busy', 'true');
    guideEmpty('正在读取节目单', date);
    try {
      const data = await request(`/api/channels/${encodeURIComponent(channelId)}/programmes?date=${encodeURIComponent(date)}`, { signal: controller.signal });
      if (sequence !== state.guideSequence) return;
      if (!Array.isArray(data.programmes)) throw new Error('节目单数据格式不正确');
      state.programmes = data.programmes.filter(programmeValid).sort((a, b) => a.start - b.start);
      renderProgrammes();
      jumpNow();
    } catch (error) {
      if (sequence !== state.guideSequence || controller.signal.aborted) return;
      guideEmpty('节目单读取失败', error.message, true);
    } finally {
      if (sequence === state.guideSequence) $('programme-list').removeAttribute('aria-busy');
    }
  }
  function updateGuideDate() {
    const value = $('programme-date').value;
    const today = value === dateValue();
    const date = new Date(`${value}T12:00:00+08:00`);
    text('guide-date-label', Number.isNaN(date.getTime()) ? '请选择日期' : `${today ? '今天 · ' : ''}${new Intl.DateTimeFormat('zh-CN', { timeZone, month: 'long', day: 'numeric', weekday: 'short' }).format(date)}`);
    $('date-today').disabled = today;
  }
  function renderProgrammes() {
    const fragment = document.createDocumentFragment();
    let nextFound = false;
    let hasCurrent = false;
    state.programmes.forEach(programme => {
      const live = active(programme);
      const past = programme.end <= epoch();
      const upcoming = !live && !past && !nextFound;
      if (upcoming) nextFound = true;
      if (live) hasCurrent = true;
      const item = node('li', `programme ${live ? 'current' : past ? 'past' : upcoming ? 'upcoming' : ''}`);
      if (live) item.setAttribute('aria-current', 'true');
      const starts = node('time', '', time(programme.start));
      starts.dateTime = new Date(programme.start * 1000).toISOString();
      const content = node('div', 'programme-content');
      content.append(node('div', 'programme-title', programme.title || '未命名节目'));
      const meta = node('div', 'programme-meta');
      meta.append(node('span', '', `${Math.round((programme.end - programme.start) / 60)} 分钟 · ${time(programme.end)} 结束`));
      if (live || upcoming || past) meta.append(node('span', 'programme-tag', live ? '正在播出' : upcoming ? '接下来' : '已结束'));
      content.append(meta);
      if (live) content.append(progress(programme));
      item.append(starts, content); fragment.append(item);
    });
    const scroll = $('programme-list').scrollTop;
    $('programme-list').replaceChildren(fragment);
    $('programme-list').scrollTop = scroll;
    show('programme-list', state.programmes.length > 0);
    show('guide-empty', state.programmes.length === 0);
    show('guide-live', hasCurrent); show('jump-now', hasCurrent);
    if (!state.programmes.length) guideEmpty('当日暂无节目', '该频道在所选日期没有节目数据');
  }
  function jumpNow() {
    const current = $('programme-list').querySelector('.current');
    if (current) $('programme-list').scrollTop = current.offsetTop - $('programme-list').offsetTop - 12;
    else $('programme-list').scrollTop = 0;
  }
  async function loadLogs() {
    if (state.logsLoading) return;
    state.logsLoading = true;
    $('logs-refresh').disabled = true;
    try {
      const data = await request('/api/logs');
      if (!Array.isArray(data.logs)) throw new Error('日志数据格式不正确');
      state.logs = data.logs.filter(log => log && typeof log === 'object').sort((a, b) => b.time - a.time);
      state.logsLoaded = true;
      state.lastLogsFetch = Date.now();
      show('logs-error', false);
      renderLogs();
    } catch (error) {
      text('logs-error', `日志读取失败：${error.message}`); show('logs-error', true);
      text('logs-empty', '暂无可显示的日志');
    } finally { state.logsLoading = false; $('logs-refresh').disabled = false; }
  }
  function renderLogs() {
    const logs = state.logs.filter(log => $('log-level').value === 'all' || log.level === $('log-level').value);
    const fragment = document.createDocumentFragment();
    logs.forEach(log => {
      const row = node('li', 'log-row');
      const stamp = node('time', '', dateTime(log.time));
      if (validTime(log.time)) stamp.dateTime = new Date(log.time * 1000).toISOString();
      row.append(stamp, node('span', `log-level ${log.level === 'error' ? 'error' : ''}`, log.level === 'error' ? '错误' : '信息'), node('span', 'log-message', log.message));
      fragment.append(row);
    });
    $('log-list').replaceChildren(fragment);
    show('logs-empty', logs.length === 0);
    text('logs-empty', state.logs.length ? '没有符合筛选条件的日志' : '暂无更新记录');
  }
  function poll() {
    if (state.polling) return state.polling;
    clearTimeout(state.pollTimer);
    state.polling = (async () => {
      try {
        const status = await request('/api/status');
        if (!['idle', 'refreshing', 'error'].includes(status.state)) throw new Error('服务状态格式不正确');
        state.status = status; state.connected = true;
        renderStatus();
        const refreshGuide = !state.channelsLoaded || state.channelsError || state.loadedSuccess !== status.last_success;
        const shouldLoadChannels = refreshGuide || epoch() >= state.channelBoundary;
        const shouldLoadLogs = !state.logsLoaded || status.state === 'refreshing' || shouldLoadChannels || Date.now() - state.lastLogsFetch >= 15000;
        // Slow guide/log responses must not hold up the status polling cadence.
        if (shouldLoadChannels) loadChannels({ refreshGuide });
        if (shouldLoadLogs) loadLogs();
      } catch (error) {
        state.connected = false;
        text('connection-error-text', `${error.message}。${state.channelsLoaded ? '已保留当前频道与节目数据。' : '尚未读取到频道数据。'}`);
        renderStatus();
        if (!state.channelsLoaded) { state.channelsError = true; renderChannels(); }
      } finally {
        state.polling = null;
        state.pollTimer = setTimeout(poll, state.status?.state === 'refreshing' ? 2000 : 5000);
      }
    })();
    return state.polling;
  }
  async function refresh() {
    if (state.refreshPending || state.status?.state === 'refreshing') return;
    state.refreshPending = true; updateRefreshButton();
    try {
      const data = await request('/api/refresh', { method: 'POST', body: {} });
      toast(data.started ? '已开始更新频道与节目单' : '更新任务已在运行');
      if (state.polling) await state.polling;
      await poll();
    } catch (error) { toast(`无法开始更新：${error.message}`); }
    finally { state.refreshPending = false; updateRefreshButton(); }
  }
  function updateSettingsControls() {
    const managed = new Set(state.status?.managed_settings || []);
    for (const [id, key] of [['refresh-time', 'refresh_time'], ['auto-refresh', 'auto_refresh']]) {
      $(id).disabled = state.saving || managed.has(key);
      $(id).title = managed.has(key) ? '由容器环境变量管理' : '';
    }
    $('settings-save').disabled = state.saving || (managed.has('refresh_time') && managed.has('auto_refresh'));
    $('settings-save').title = managed.size === 2 ? '由容器环境变量管理' : '';
    for (const id of ['settings-close', 'settings-cancel']) $(id).disabled = state.saving;
  }
  function openSettings() {
    if (!state.status) { toast('服务状态尚未就绪'); return; }
    $('refresh-time').value = state.status.refresh_time || '05:00';
    $('auto-refresh').checked = Boolean(state.status.auto_refresh);
    text('settings-feedback', '');
    $('settings-feedback').classList.remove('success');
    updateSettingsControls();
    $('settings-dialog').showModal();
  }
  function closeSettings() { if (!state.saving) $('settings-dialog').close(); }
  async function saveSettings(event) {
    event.preventDefault();
    if (state.saving || !$('settings-form').reportValidity()) return;
    const settings = { refresh_time: $('refresh-time').value, auto_refresh: $('auto-refresh').checked };
    if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(settings.refresh_time)) { text('settings-feedback', '请选择有效的每日更新时间'); return; }
    state.saving = true;
    updateSettingsControls();
    text('settings-feedback', '正在保存…'); $('settings-feedback').classList.remove('success');
    try {
      const result = await request('/api/settings', { method: 'POST', body: settings });
      Object.assign(state.status, settings, result);
      $('settings-feedback').classList.add('success');
      text('settings-feedback', '设置已保存');
      renderStatus();
      if (state.polling) await state.polling;
      await poll();
    } catch (error) { text('settings-feedback', `保存失败：${error.message}`); }
    finally {
      state.saving = false;
      updateSettingsControls();
    }
  }
  function changeDate(value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return;
    $('programme-date').value = value;
    loadProgrammes();
  }
  function moveDate(days) {
    const date = new Date(`${$('programme-date').value || dateValue()}T12:00:00+08:00`);
    date.setUTCDate(date.getUTCDate() + days); changeDate(dateValue(date));
  }
  $('programme-date').value = dateValue();
  text('today-label', longDate.format(new Date()));
  $('refresh-button').disabled = true;
  $('settings-open').disabled = true;
  $('subscriptions-open').disabled = true;
  $('subscriptions-open').addEventListener('click', openSubscriptions);
  $('subscriptions-close').addEventListener('click', () => $('subscriptions-dialog').close());
  document.querySelectorAll('[data-copy]').forEach(button => button.addEventListener('click', () => copySubscription(button)));
  $('channel-search').addEventListener('input', event => { state.query = event.target.value; renderChannels(); });
  $('search-clear').addEventListener('click', () => { state.query = ''; $('channel-search').value = ''; renderChannels(); $('channel-search').focus(); });
  $('channels-retry').addEventListener('click', () => state.connected ? loadChannels() : poll());
  $('reconnect').addEventListener('click', poll);
  $('refresh-button').addEventListener('click', refresh);
  $('guide-retry').addEventListener('click', loadProgrammes);
  $('programme-date').addEventListener('change', event => {
    if (!event.target.value) { event.target.value = dateValue(); }
    changeDate(event.target.value);
  });
  $('date-prev').addEventListener('click', () => moveDate(-1));
  $('date-next').addEventListener('click', () => moveDate(1));
  $('date-today').addEventListener('click', () => changeDate(dateValue()));
  $('jump-now').addEventListener('click', jumpNow);
  $('guide-back').addEventListener('click', () => {
    $('workspace').dataset.mobileView = 'channels';
    $('channel-body').querySelector('[aria-current="true"]')?.focus({ preventScroll: true });
  });
  $('logs-refresh').addEventListener('click', loadLogs);
  $('log-level').addEventListener('change', renderLogs);
  $('settings-open').addEventListener('click', openSettings);
  $('settings-close').addEventListener('click', closeSettings);
  $('settings-cancel').addEventListener('click', closeSettings);
  $('settings-dialog').addEventListener('cancel', event => { if (state.saving) event.preventDefault(); });
  $('settings-form').addEventListener('submit', saveSettings);
  window.addEventListener('online', poll);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) poll(); });
  setInterval(() => {
    text('today-label', longDate.format(new Date()));
    updateGuideDate();
    if (state.channelsLoaded) renderChannels();
    if (state.programmes.length) renderProgrammes();
  }, 30000);
  icons();
  poll();
})();
