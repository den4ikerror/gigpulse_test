const tg = window.Telegram?.WebApp;
tg?.ready();
tg?.expand();

const initData = tg?.initData || '';
const categories = {
    graphic_design: 'Графічний дизайн',
    web_uiux_design: 'Веб-дизайн та UI/UX',
    other_design: 'Інший дизайн',
    copywriting: 'Копірайтинг і тексти',
    smm_social: 'SMM і соцмережі',
    video_editing: 'Відеомонтаж',
    frontend_backend: 'Frontend / Backend розробка',
    chatbots: 'Створення чат-ботів',
    '3d_visualization': '3D і візуалізація',
    logo_branding: 'Логотипи та брендинг',
    pr_influencers: 'PR і блогери',
    mobile_apps: 'Розробка мобільних застосунків',
    wordpress_cms: 'WordPress та CMS',
    qa_testing: 'QA і тестування',
    ai_data_automation: 'AI, дані й автоматизація',
    seo: 'SEO',
    targeted_ads: 'Таргетована реклама',
    translation: 'Переклад',
    photo_editing: 'Фото та обробка фото',
    audio_voiceover: 'Аудіо та озвучення',
    virtual_assistance: 'Віртуальна допомога та адміністрування',
};
const state = { tab: 'feed', filters: [], orderId: null, toastTimer: null };
const skillsStorageKey = 'gigpulse-user-skills';

async function apiFetch(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            'X-Telegram-Init-Data': initData,
            ...(options.headers || {}),
        },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(data.detail || `Помилка запиту (${response.status})`);
    }
    return data;
}

function showToast(message) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.remove('hidden');
    clearTimeout(state.toastTimer);
    state.toastTimer = setTimeout(() => toast.classList.add('hidden'), 3500);
}

function formatDate(value) {
    if (!value) return '';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString('uk-UA');
}

function categoryName(category) {
    return categories[category] || category;
}

function renderOrders(container, orders, emptyText) {
    container.replaceChildren();
    if (!orders?.length) {
        const empty = document.createElement('p');
        empty.className = 'empty-state';
        empty.textContent = emptyText;
        container.append(empty);
        return;
    }

    for (const order of orders) {
        const card = document.createElement('article');
        card.className = 'order-card';

        const meta = document.createElement('div');
        meta.className = 'order-meta';
        const category = document.createElement('span');
        category.className = 'category-tag';
        category.textContent = categoryName(order.category);
        const budget = document.createElement('span');
        budget.className = 'budget';
        budget.textContent = order.budget || 'Бюджет не вказано';
        meta.append(category, budget);

        const title = document.createElement('h2');
        title.textContent = order.title;
        const summary = document.createElement('p');
        summary.className = 'order-summary';
        summary.textContent = order.summary;

        const footer = document.createElement('div');
        footer.className = 'order-footer';
        const source = document.createElement('span');
        source.textContent = `${order.source_name}${order.created_at ? ` · ${formatDate(order.created_at)}` : ''}`;

        const actions = document.createElement('div');
        actions.className = 'order-actions';
        const proposal = document.createElement('button');
        proposal.type = 'button';
        proposal.className = 'text-button';
        proposal.dataset.action = 'proposal';
        proposal.dataset.orderId = order.id;
        proposal.textContent = 'AI-відгук';
        actions.append(proposal);

        let contactUrl = null;
        try {
            const parsedUrl = new URL(order.contact_url, location.href);
            if (['http:', 'https:'].includes(parsedUrl.protocol)) contactUrl = parsedUrl.href;
        } catch {
            contactUrl = null;
        }
        if (contactUrl) {
            const contact = document.createElement('a');
            contact.className = 'primary-button link-button';
            contact.href = contactUrl;
            contact.target = '_blank';
            contact.rel = 'noopener noreferrer';
            contact.textContent = 'Відгукнутися';
            actions.append(contact);
        }

        const favorite = document.createElement('button');
        favorite.type = 'button';
        favorite.className = 'icon-button';
        favorite.dataset.action = 'favorite';
        favorite.dataset.orderId = order.id;
        favorite.dataset.favorited = String(Boolean(order.is_favorite));
        favorite.textContent = order.is_favorite ? '★' : '☆';
        favorite.setAttribute('aria-label', order.is_favorite ? 'Видалити з обраного' : 'Додати в обране');
        actions.append(favorite);
        footer.append(source, actions);
        card.append(meta, title, summary, footer);
        container.append(card);
    }
}

async function loadOrders() {
    const container = document.getElementById('orders-list');
    container.innerHTML = '<p class="empty-state">Завантаження…</p>';
    const params = new URLSearchParams();
    const search = document.getElementById('search-input').value.trim();
    const category = document.getElementById('category-select').value;
    const minBudget = Number(document.getElementById('min-budget-input').value || 0);
    if (search) params.set('search', search);
    if (category) params.set('category', category);
    if (minBudget > 0) params.set('min_budget', String(minBudget));
    const data = await apiFetch(`/api/orders?${params}`);
    renderOrders(container, data.orders, 'За вашим запитом замовлень немає.');
}

async function loadFavorites() {
    const data = await apiFetch('/api/orders/favorites');
    renderOrders(document.getElementById('favorites-list'), data.orders, 'В обраному поки немає замовлень.');
}

function renderFilters() {
    const container = document.getElementById('filters-list');
    container.replaceChildren();
    for (const filter of state.filters) {
        const card = document.createElement('article');
        card.className = 'filter-card';
        const heading = document.createElement('label');
        heading.className = 'filter-heading';
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.checked = filter.enabled;
        checkbox.dataset.action = 'filter-enabled';
        checkbox.dataset.category = filter.category;
        const name = document.createElement('strong');
        name.textContent = categoryName(filter.category);
        heading.append(checkbox, name);

        const budgetLabel = document.createElement('label');
        budgetLabel.textContent = 'Мінімальний бюджет';
        const budget = document.createElement('input');
        budget.type = 'number';
        budget.min = '0';
        budget.step = '1';
        budget.value = filter.min_budget || 0;
        budget.dataset.action = 'filter-budget';
        budget.dataset.category = filter.category;
        budgetLabel.append(budget);

        const keywordsLabel = document.createElement('label');
        keywordsLabel.textContent = 'Ключові слова';
        const keywords = document.createElement('input');
        keywords.type = 'text';
        keywords.maxLength = 500;
        keywords.value = filter.keywords || '';
        keywords.placeholder = 'Наприклад: Python, React';
        keywords.dataset.action = 'filter-keywords';
        keywords.dataset.category = filter.category;
        keywordsLabel.append(keywords);
        card.append(heading, budgetLabel, keywordsLabel);
        container.append(card);
    }
}

async function loadFilters() {
    const data = await apiFetch('/api/user/filters');
    state.filters = data.filters || [];
    renderFilters();
}

async function saveFilter(category) {
    const filter = state.filters.find(item => item.category === category);
    if (!filter) return;
    const data = await apiFetch('/api/user/filters', {
        method: 'PUT',
        body: JSON.stringify(filter),
    });
    Object.assign(filter, data);
    updateCategoryOptions();
    showToast('Фільтр збережено');
}

function updateCategoryOptions() {
    const select = document.getElementById('category-select');
    const selected = select.value;
    select.replaceChildren(new Option('Усі категорії', ''));
    for (const filter of state.filters.filter(item => item.enabled)) {
        select.add(new Option(categoryName(filter.category), filter.category));
    }
    if ([...select.options].some(option => option.value === selected)) select.value = selected;
}

async function loadProfile() {
    const data = await apiFetch('/api/user/profile');
    state.filters = data.filters || [];
    updateCategoryOptions();
    const user = data.user;
    document.getElementById('subscription-badge').textContent =
        user.subscription_until && new Date(user.subscription_until) > new Date()
            ? `Тріал до ${formatDate(user.subscription_until)}`
            : 'Без активної підписки';
    const profile = document.getElementById('profile-card');
    profile.replaceChildren();
    const title = document.createElement('h2');
    title.textContent = user.username ? `@${user.username}` : `Telegram ID: ${user.telegram_id}`;
    const trial = document.createElement('p');
    trial.textContent = user.trial_used ? 'Пробний період уже активовано.' : 'Пробний період ще не активовано.';
    const subscription = document.createElement('p');
    subscription.textContent = user.subscription_until
        ? `Доступ до: ${formatDate(user.subscription_until)}`
        : 'Активної підписки немає.';
    profile.append(title, trial, subscription);
}

async function switchTab(tab) {
    state.tab = tab;
    document.querySelectorAll('.tab').forEach(button => {
        const active = button.dataset.tab === tab;
        button.classList.toggle('active', active);
        button.setAttribute('aria-selected', String(active));
    });
    document.querySelectorAll('.tab-content').forEach(section => {
        section.classList.toggle('hidden', section.id !== `content-${tab}`);
    });
    try {
        if (tab === 'feed') await loadOrders();
        if (tab === 'favorites') await loadFavorites();
        if (tab === 'filters') await loadFilters();
        if (tab === 'profile') await loadProfile();
        setMainButton(tab);
    } catch (error) {
        showToast(error.message);
    }
}

function setMainButton(tab) {
    if (!tg?.MainButton) return;
    tg.MainButton.offClick(refreshOrders);
    if (tab === 'feed') {
        tg.MainButton.setText('Оновити стрічку');
        tg.MainButton.onClick(refreshOrders);
        tg.MainButton.show();
    } else {
        tg.MainButton.hide();
    }
}

function refreshOrders() {
    loadOrders().catch(error => showToast(error.message));
}

function openProposalModal(orderId) {
    state.orderId = Number(orderId);
    const modal = document.getElementById('proposal-modal');
    document.getElementById('proposal-result').classList.add('hidden');
    document.getElementById('proposal-error').classList.add('hidden');
    document.getElementById('user-skills').value = localStorage.getItem(skillsStorageKey) || '';
    modal.showModal();
    tg?.BackButton?.show();
    tg?.HapticFeedback?.impactOccurred('light');
}

function closeProposalModal() {
    document.getElementById('proposal-modal').close();
    state.orderId = null;
    tg?.BackButton?.hide();
}

async function generateProposal() {
    const skills = document.getElementById('user-skills').value.trim();
    const result = document.getElementById('proposal-result');
    const errorNode = document.getElementById('proposal-error');
    if (skills.length < 2) {
        errorNode.textContent = 'Опишіть ваші навички (мінімум 2 символи).';
        errorNode.classList.remove('hidden');
        return;
    }
    localStorage.setItem(skillsStorageKey, skills);
    errorNode.classList.add('hidden');
    result.textContent = 'Генеруємо відгук…';
    result.classList.remove('hidden');
    try {
        const data = await apiFetch(`/api/orders/${state.orderId}/proposal`, {
            method: 'POST',
            body: JSON.stringify({ user_skills: skills }),
        });
        result.textContent = data.proposal;
    } catch (error) {
        result.classList.add('hidden');
        errorNode.textContent = error.message;
        errorNode.classList.remove('hidden');
    }
}

document.querySelector('.tabs').addEventListener('click', event => {
    const button = event.target.closest('[data-tab]');
    if (button) switchTab(button.dataset.tab);
});

document.getElementById('search-form').addEventListener('submit', event => {
    event.preventDefault();
    loadOrders().catch(error => showToast(error.message));
});

document.body.addEventListener('click', async event => {
    const button = event.target.closest('[data-action]');
    if (!button) return;
    if (button.dataset.action === 'proposal') openProposalModal(button.dataset.orderId);
    if (button.dataset.action === 'favorite') {
        try {
            const data = await apiFetch(`/api/orders/${button.dataset.orderId}/favorite`, { method: 'POST' });
            button.textContent = data.favorited ? '★' : '☆';
            button.dataset.favorited = String(data.favorited);
            button.setAttribute('aria-label', data.favorited ? 'Видалити з обраного' : 'Додати в обране');
            showToast(data.favorited ? 'Додано в обране' : 'Видалено з обраного');
            tg?.HapticFeedback?.notificationOccurred('success');
            if (state.tab === 'favorites' && !data.favorited) await loadFavorites();
        } catch (error) {
            showToast(error.message);
        }
    }
});

document.getElementById('filters-list').addEventListener('change', event => {
    const field = event.target;
    const category = field.dataset.category;
    const filter = state.filters.find(item => item.category === category);
    if (!filter) return;
    if (field.dataset.action === 'filter-enabled') filter.enabled = field.checked;
    if (field.dataset.action === 'filter-budget') filter.min_budget = Number(field.value || 0);
    if (field.dataset.action === 'filter-keywords') filter.keywords = field.value.trim() || null;
    saveFilter(category).catch(error => showToast(error.message));
});

document.getElementById('close-proposal').addEventListener('click', closeProposalModal);
document.getElementById('generate-proposal').addEventListener('click', generateProposal);
tg?.BackButton?.onClick(closeProposalModal);

async function initialize() {
    if (!initData) {
        showToast('Відкрийте застосунок через Telegram-бота.');
        return;
    }
    try {
        await loadProfile();
        await switchTab('feed');
    } catch (error) {
        showToast(error.message);
    }
}

initialize();
