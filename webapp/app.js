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
const state = {
    tab: 'feed',
    filters: [],
    orderId: null,
    currentOrder: null,
    user: null,
    wheel: null,
    toastTimer: null,
};
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
        const detail = typeof data.detail === 'string' ? data.detail : data.detail?.message;
        throw new Error(detail || `Помилка запиту (${response.status})`);
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
        card.tabIndex = 0;
        card.setAttribute('role', 'button');
        card.setAttribute('aria-label', `Деталі замовлення: ${order.title}`);
        card.dataset.orderId = order.id;

        const meta = document.createElement('div');
        meta.className = 'order-meta';
        const category = document.createElement('span');
        category.className = 'category-tag';
        category.textContent = categoryName(order.category);
        const budget = document.createElement('span');
        budget.className = 'budget';
        budget.textContent = order.contact_unlocked
            ? (order.budget || 'Бюджет не вказано')
            : 'Деталі приховано';
        meta.append(category, budget);

        const title = document.createElement('h2');
        title.textContent = order.title;
        const summary = document.createElement('p');
        summary.className = 'order-summary';
        summary.textContent = order.summary;
        const openHint = document.createElement('span');
        openHint.className = 'open-hint';
        openHint.textContent = order.contact_unlocked ? 'Деталі відкриті' : 'Натисніть, щоб переглянути';

        const footer = document.createElement('div');
        footer.className = 'order-footer';
        const source = document.createElement('span');
        source.textContent = `${order.source_name}${order.created_at ? ` · ${formatDate(order.created_at)}` : ''}`;

        const actions = document.createElement('div');
        actions.className = 'order-actions';
        if (order.contact_unlocked) {
            const proposal = document.createElement('button');
            proposal.type = 'button';
            proposal.className = 'text-button';
            proposal.dataset.action = 'proposal';
            proposal.dataset.orderId = order.id;
            proposal.textContent = 'AI-відгук';
            actions.append(proposal);
        }

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
        card.append(meta, title, summary, openHint, footer);
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
    const [data, wheel] = await Promise.all([
        apiFetch('/api/user/profile'),
        apiFetch('/api/user/wheel'),
    ]);
    state.filters = data.filters || [];
    state.user = data.user;
    updateCategoryOptions();
    const user = data.user;
    document.getElementById('subscription-badge').textContent =
        user.has_subscription
            ? `Безліміт до ${formatDate(user.subscription_until)}`
            : `${user.contact_credits} безкоштовних контактів`;
    const profile = document.getElementById('profile-card');
    profile.replaceChildren();
    const title = document.createElement('h2');
    title.textContent = user.username ? `@${user.username}` : `Telegram ID: ${user.telegram_id}`;
    const access = document.createElement('p');
    access.textContent = user.has_subscription
        ? 'У вас активний безлімітний доступ до повних описів і контактів.'
        : `Залишилося безкоштовних відкриттів контактів: ${user.contact_credits}.`;
    const subscription = document.createElement('p');
    subscription.textContent = user.has_subscription
        ? `Безлімітний доступ до: ${formatDate(user.subscription_until)}`
        : 'Платні підписки скоро з’являться.';
    profile.append(title, access, subscription);
    renderWheel(wheel);
}

function renderWheel(wheel, resultText = '') {
    state.wheel = wheel;
    const button = document.getElementById('spin-wheel');
    const status = document.getElementById('wheel-status');
    const result = document.getElementById('wheel-result');
    const prizeList = document.getElementById('wheel-prizes');
    button.disabled = !wheel.can_spin;
    status.textContent = wheel.can_spin
        ? 'Є безкоштовне обертання — спробуйте виграти контакти або безліміт!'
        : `Наступне обертання: ${formatDate(wheel.next_spin_at)}.`;
    result.textContent = resultText;
    result.classList.toggle('hidden', !resultText);
    prizeList.replaceChildren();
    for (const prize of wheel.prizes || []) {
        const item = document.createElement('li');
        item.textContent = `${prize.label} — ${prize.probability}%`;
        prizeList.append(item);
    }
}

async function performWheelSpin() {
    const button = document.getElementById('spin-wheel');
    const icon = document.getElementById('wheel-icon');
    button.disabled = true;
    icon.classList.add('spinning');
    try {
        const [result] = await Promise.all([
            apiFetch('/api/user/wheel/spin', { method: 'POST' }),
            new Promise(resolve => setTimeout(resolve, 1800)),
        ]);
        tg?.HapticFeedback?.notificationOccurred('success');
        await loadProfile();
        renderWheel(state.wheel, `Ваш приз: ${result.prize.label}!`);
        if (state.currentOrder) {
            state.currentOrder.contact_credits = result.contact_credits;
        }
    } catch (error) {
        showToast(error.message);
        button.disabled = !state.wheel?.can_spin;
    } finally {
        icon.classList.remove('spinning');
    }
}

function renderOrderDetails(order) {
    state.currentOrder = order;
    document.getElementById('detail-category').textContent = categoryName(order.category);
    document.getElementById('detail-title').textContent = order.title;
    document.getElementById('detail-summary').textContent = order.summary;
    document.getElementById('detail-source').textContent = `Джерело: ${order.source_name}`;
    document.getElementById('detail-budget').textContent = order.budget
        ? `Бюджет: ${order.budget}`
        : 'Бюджет приховано до відкриття';

    const descriptionSection = document.getElementById('full-description-section');
    const description = document.getElementById('detail-full-description');
    const gate = document.getElementById('contact-gate');
    const unlock = document.getElementById('unlock-contact');
    const contact = document.getElementById('contact-link');
    const hasDetails = Boolean(order.full_description);
    let safeContactUrl = null;
    try {
        const parsedUrl = new URL(order.contact_url);
        if (['http:', 'https:'].includes(parsedUrl.protocol)) safeContactUrl = parsedUrl.href;
    } catch {
        safeContactUrl = null;
    }
    descriptionSection.classList.toggle('hidden', !hasDetails);
    description.textContent = hasDetails ? order.full_description : '';
    contact.classList.toggle('hidden', !safeContactUrl);
    contact.href = safeContactUrl || '#';
    unlock.classList.toggle('hidden', hasDetails);
    gate.replaceChildren();

    if (hasDetails) {
        gate.textContent = order.has_subscription
            ? 'Повний доступ активний за підпискою.'
            : 'Контакт уже відкрито — повторно списувати відкриття не потрібно.';
        if (!safeContactUrl) gate.textContent += ' Посилання на джерело некоректне або недоступне.';
        return;
    }

    if (order.contact_credits > 0) {
        gate.textContent = `Короткий опис і джерело доступні всім. Одне з ${order.contact_credits} безкоштовних відкриттів покаже повний опис і контакт.`;
        unlock.textContent = 'Відкрити контакт · 1 спроба';
        unlock.disabled = false;
        return;
    }

    gate.textContent = 'Безкоштовні відкриття закінчилися. Отримайте додаткові контакти у колесі або дочекайтеся підписки.';
    unlock.classList.add('hidden');
    const wheelButton = document.createElement('button');
    wheelButton.type = 'button';
    wheelButton.className = 'text-button';
    wheelButton.dataset.action = 'wheel-tab';
    wheelButton.textContent = 'Перейти до колеса можливостей';
    gate.append(wheelButton);
}

async function openOrder(orderId) {
    state.orderId = Number(orderId);
    const modal = document.getElementById('order-modal');
    document.getElementById('detail-title').textContent = 'Завантаження…';
    document.getElementById('detail-summary').textContent = '';
    document.getElementById('contact-gate').textContent = '';
    modal.showModal();
    tg?.BackButton?.show();
    tg?.HapticFeedback?.impactOccurred('light');
    try {
        renderOrderDetails(await apiFetch(`/api/orders/${state.orderId}`));
    } catch (error) {
