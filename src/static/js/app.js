// Основний JavaScript для веб-інтерфейсу системи аналізу конкурентів

class CompetitorAnalysisApp {
    constructor() {
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupTooltips();
        this.setupAutoRefresh();
        this.setupFormValidation();
        this.loadAutoSavedData();
    }

    setupEventListeners() {
        // Обробка форм
        document.addEventListener('DOMContentLoaded', () => {
            this.initializePage();
        });

        // Обробка кнопок видалення
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('delete-btn')) {
                this.handleDelete(e);
            }
        });

        // Обробка оновлення статусу
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('refresh-btn')) {
                this.refreshStatus(e);
            }
        });

        // Обробка перегляду результатів
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('view-result-btn')) {
                this.viewResult(e);
            }
        });

        // Автозбереження форм
        document.addEventListener('input', (e) => {
            if (e.target.classList.contains('auto-save')) {
                this.autoSave(e.target);
            }
        });
    }

    initializePage() {
        // Ініціалізація сторінки залежно від типу
        const page = document.body.dataset.page;
        
        switch(page) {
            case 'home':
                this.initHomePage();
                break;
            case 'config':
                this.initConfigPage();
                break;
            case 'analysis':
                this.initAnalysisPage();
                break;
            case 'batch':
                this.initBatchPage();
                break;
            case 'results':
                this.initResultsPage();
                break;
            case 'result':
                this.initResultPage();
                break;
        }
    }

    initHomePage() {
        // Ініціалізація головної сторінки
        this.loadConfigStats();
        this.setupConfigCards();
    }

    initConfigPage() {
        // Ініціалізація сторінки конфігурації
        this.setupFormValidation();
        this.setupKeywordCounter();
        this.setupUrlValidator();
    }

    initAnalysisPage() {
        // Ініціалізація сторінки аналізу
        this.showAnalysisDetails();
    }

    initBatchPage() {
        // Ініціалізація сторінки пакетного аналізу
        this.setupAutoRefresh();
        this.updateBatchProgress();
    }

    initResultsPage() {
        // Ініціалізація сторінки результатів
        this.setupResultFilters();
        this.setupPagination();
    }

    initResultPage() {
        // Ініціалізація сторінки окремого результату
        this.setupResultActions();
        this.setupTableSorting();
    }

    setupTooltips() {
        // Ініціалізація Bootstrap tooltips
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }

    setupAutoRefresh() {
        // Автоматичне оновлення для сторінок з динамічним контентом
        const autoRefreshElements = document.querySelectorAll('[data-auto-refresh]');
        
        autoRefreshElements.forEach(element => {
            const interval = parseInt(element.dataset.autoRefresh) * 1000;
            if (interval > 0) {
                setInterval(() => {
                    this.refreshElement(element);
                }, interval);
            }
        });
    }

    setupFormValidation() {
        // Налаштування валідації форм
        const forms = document.querySelectorAll('.needs-validation');
        
        forms.forEach(form => {
            form.addEventListener('submit', (e) => {
                if (!form.checkValidity()) {
                    e.preventDefault();
                    e.stopPropagation();
                }
                form.classList.add('was-validated');
            });
        });

        // Кастомна валідація
        this.setupCustomValidation();
    }

    setupCustomValidation() {
        // Валідація URL списків
        const urlTextareas = document.querySelectorAll('textarea[name="sites"]');
        urlTextareas.forEach(textarea => {
            textarea.addEventListener('blur', () => {
                this.validateUrls(textarea);
            });
        });

        // Валідація email списків
        const emailTextareas = document.querySelectorAll('textarea[name="email_recipients"]');
        emailTextareas.forEach(textarea => {
            textarea.addEventListener('blur', () => {
                this.validateEmails(textarea);
            });
        });
    }

    validateUrls(textarea) {
        const urls = textarea.value.split('\n').filter(url => url.trim());
        const invalidUrls = [];
        
        urls.forEach(url => {
            url = url.trim();
            if (url && !this.isValidUrl(url)) {
                invalidUrls.push(url);
            }
        });

        const feedback = textarea.parentNode.querySelector('.invalid-feedback');
        if (invalidUrls.length > 0) {
            textarea.classList.add('is-invalid');
            if (feedback) {
                feedback.textContent = `Невалідні URL: ${invalidUrls.join(', ')}`;
            }
            return false;
        } else {
            textarea.classList.remove('is-invalid');
            textarea.classList.add('is-valid');
            return true;
        }
    }

    validateEmails(textarea) {
        const emails = textarea.value.split('\n').filter(email => email.trim());
        const invalidEmails = [];
        
        emails.forEach(email => {
            email = email.trim();
            if (email && !this.isValidEmail(email)) {
                invalidEmails.push(email);
            }
        });

        const feedback = textarea.parentNode.querySelector('.invalid-feedback');
        if (invalidEmails.length > 0) {
            textarea.classList.add('is-invalid');
            if (feedback) {
                feedback.textContent = `Невалідні email: ${invalidEmails.join(', ')}`;
            }
            return false;
        } else {
            textarea.classList.remove('is-invalid');
            textarea.classList.add('is-valid');
            return true;
        }
    }

    isValidUrl(string) {
        try {
            new URL(string);
            return true;
        } catch (_) {
            return false;
        }
    }

    isValidEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }

    setupKeywordCounter() {
        // Лічильник ключових слів
        const keywordTextareas = document.querySelectorAll('textarea[name*="keywords"]');
        
        keywordTextareas.forEach(textarea => {
            const counter = this.createCounter(textarea);
            textarea.addEventListener('input', () => {
                this.updateCounter(textarea, counter);
            });
            this.updateCounter(textarea, counter);
        });
    }

    createCounter(textarea) {
        const counter = document.createElement('small');
        counter.className = 'text-muted keyword-counter';
        textarea.parentNode.appendChild(counter);
        return counter;
    }

    updateCounter(textarea, counter) {
        const keywords = textarea.value.split('\n').filter(k => k.trim()).length;
        counter.textContent = `Ключових слів: ${keywords}`;
    }

    setupUrlValidator() {
        // Валідатор URL в реальному часі
        const urlInputs = document.querySelectorAll('input[type="url"]');
        
        urlInputs.forEach(input => {
            input.addEventListener('input', () => {
                if (input.value && !this.isValidUrl(input.value)) {
                    input.classList.add('is-invalid');
                } else {
                    input.classList.remove('is-invalid');
                    if (input.value) {
                        input.classList.add('is-valid');
                    }
                }
            });
        });
    }

    handleDelete(e) {
        e.preventDefault();
        
        const entityType = e.target.dataset.type;
        const entityId = e.target.dataset.id;
        const entityName = e.target.dataset.name || 'цей елемент';

        if (confirm(`Ви впевнені, що хочете видалити ${entityName}?`)) {
            this.deleteEntity(entityType, entityId);
        }
    }

    async deleteEntity(type, id) {
        try {
            this.showLoading();
            
            const response = await fetch(`/${type}/${id}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (response.ok) {
                this.showSuccess('Елемент успішно видалено');
                setTimeout(() => {
                    location.reload();
                }, 1000);
            } else {
                throw new Error('Помилка при видаленні');
            }
        } catch (error) {
            this.showError('Помилка при видаленні: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }

    async refreshStatus(e) {
        e.preventDefault();
        
        const taskId = e.target.dataset.taskId;
        const statusElement = e.target.closest('.status-container');

        try {
            const response = await fetch(`/api/analysis/status/${taskId}`);
            const data = await response.json();
            
            this.updateStatusDisplay(statusElement, data);
        } catch (error) {
            this.showError('Помилка оновлення статусу');
        }
    }

    updateStatusDisplay(container, statusData) {
        // Оновлення відображення статусу
        const statusBadge = container.querySelector('.status-badge');
        const progressBar = container.querySelector('.progress-bar');
        const statusText = container.querySelector('.status-text');

        if (statusBadge) {
            statusBadge.className = `status-badge status-${statusData.status}`;
            statusBadge.textContent = statusData.status.toUpperCase();
        }

        if (progressBar) {
            progressBar.style.width = `${statusData.progress}%`;
            progressBar.setAttribute('aria-valuenow', statusData.progress);
        }

        if (statusText) {
            statusText.textContent = statusData.message;
        }
    }

    // 🆕 ВИПРАВЛЕНА ФУНКЦІЯ - Перегляд результату
    async viewResult(e) {
        e.preventDefault();
        
        const taskId = e.target.dataset.taskId;

        try {
            // Спочатку перевіряємо статус
            const statusResponse = await fetch(`/api/analysis/status/${taskId}`);
            const statusData = await statusResponse.json();
            
            if (statusData.status === 'completed') {
                // Відкриваємо результат в новій вкладці
                window.open(`/result/${taskId}`, '_blank');
            } else if (statusData.status === 'running' || statusData.status === 'pending') {
                // Відкриваємо сторінку очікування
                window.open(`/result/${taskId}`, '_blank');
            } else if (statusData.status === 'failed') {
                this.showError(`Аналіз провалився: ${statusData.message || 'Невідома помилка'}`);
            }
        } catch (error) {
            this.showError('Помилка завантаження результату: ' + error.message);
        }
    }

    // 🆕 НОВА ФУНКЦІЯ - Завантаження результату
    async downloadResult(taskId) {
        try {
            this.showInfo('Підготовка файлу для завантаження...');
            
            const response = await fetch(`/result/${taskId}/download`);
            
            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `analysis_result_${taskId.substring(0, 8)}.xlsx`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
                
                this.showSuccess('Файл завантажено');
            } else if (response.status === 404) {
                this.showError('Результат не знайдено');
            } else if (response.status === 202) {
                this.showWarning('Аналіз ще не завершено. Спробуйте пізніше.');
            } else {
                throw new Error(`HTTP ${response.status}`);
            }
        } catch (error) {
            console.error('Помилка завантаження:', error);
            this.showError('Помилка завантаження файлу: ' + error.message);
        }
    }

    // 🆕 НОВА ФУНКЦІЯ - Перегляд детальних результатів пакету
    viewBatchResults(batchId) {
        window.location.href = `/batch/${batchId}/results`;
    }

    // 🆕 ВИПРАВЛЕНА ФУНКЦІЯ - Показ результатів в модальному вікні
    async showResultModal(taskId) {
        const modal = document.getElementById('resultModal') || this.createResultModal();
        const modalBody = modal.querySelector('.modal-body');

        try {
            this.showModalLoading(modalBody);
            
            const response = await fetch(`/api/analysis/result/${taskId}`);
            
            if (response.ok) {
                const data = await response.json();
                this.displayResultInModal(modalBody, data);
            } else if (response.status === 202) {
                modalBody.innerHTML = `
                    <div class="alert alert-warning text-center">
                        <i class="fas fa-clock"></i>
                        <h5>Аналіз ще виконується</h5>
                        <p>Результат буде доступний після завершення аналізу.</p>
                        <a href="/result/${taskId}" class="btn btn-primary" target="_blank">
                            Відкрити сторінку очікування
                        </a>
                    </div>
                `;
            } else if (response.status === 404) {
                modalBody.innerHTML = `
                    <div class="alert alert-danger text-center">
                        <i class="fas fa-exclamation-triangle"></i>
                        <h5>Результат не знайдено</h5>
                        <p>Можливо, результат був видалений або ще не створений.</p>
                    </div>
                `;
            } else {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const modalInstance = new bootstrap.Modal(modal);
            modalInstance.show();
        } catch (error) {
            this.showError('Помилка завантаження результату: ' + error.message);
        }
    }

    createResultModal() {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.id = 'resultModal';
        modal.tabIndex = -1;
        modal.innerHTML = `
            <div class="modal-dialog modal-xl">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Результат аналізу</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body"></div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Закрити</button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        return modal;
    }

    displayResultInModal(container, resultData) {
        container.innerHTML = `
            <div class="mb-3">
                <h6>Сайт: <a href="${resultData.site_url}" target="_blank" class="text-decoration-none">${resultData.site_url}</a></h6>
                <small class="text-muted">Task ID: ${resultData.task_id}</small>
            </div>
            <hr>
            <div class="row mb-3 text-center">
                <div class="col-md-3">
                    <div class="h4 text-primary">${resultData.pages_analyzed}</div>
                    <small class="text-muted">Сторінок проаналізовано</small>
                </div>
                <div class="col-md-3">
                    <div class="h4 text-success">${resultData.positive_matches.length}</div>
                    <small class="text-muted">Позитивних збігів</small>
                </div>
                <div class="col-md-3">
                    <div class="h4 text-danger">${resultData.negative_matches.length}</div>
                    <small class="text-muted">Негативних збігів</small>
                </div>
                <div class="col-md-3">
                    <div class="h4 text-info">${resultData.analysis_time.toFixed(1)}с</div>
                    <small class="text-muted">Час аналізу</small>
                </div>
            </div>
            
            ${resultData.positive_matches.length > 0 ? `
            <h6 class="text-success">Позитивні збіги (топ 5):</h6>
            <div class="list-group mb-3" style="max-height: 300px; overflow-y: auto;">
                ${resultData.positive_matches.slice(0, 5).map(match => `
                    <div class="list-group-item">
                        <div class="d-flex w-100 justify-content-between">
                            <h6 class="mb-1"><span class="badge bg-success">${match.keyword}</span></h6>
                            <small><strong>${match.count}</strong> разів</small>
                        </div>
                        <p class="mb-1">
                            <small>
                                <a href="${match.url}" target="_blank" class="text-decoration-none">
                                    <i class="fas fa-external-link-alt"></i> ${match.url.length > 80 ? match.url.substring(0, 80) + '...' : match.url}
                                </a>
                            </small>
                        </p>
                        <small class="text-muted">${match.context}</small>
                    </div>
                `).join('')}
            </div>
            ${resultData.positive_matches.length > 5 ? `<p><small class="text-muted">... та ще ${resultData.positive_matches.length - 5} збігів</small></p>` : ''}
            ` : '<div class="alert alert-warning"><i class="fas fa-search"></i> Позитивні ключові слова не знайдені</div>'}
            
            ${resultData.negative_matches.length > 0 ? `
            <h6 class="text-danger">Негативні збіги:</h6>
            <div class="list-group mb-3" style="max-height: 300px; overflow-y: auto;">
                ${resultData.negative_matches.slice(0, 5).map(match => `
                    <div class="list-group-item">
                        <div class="d-flex w-100 justify-content-between">
                            <h6 class="mb-1"><span class="badge bg-danger">${match.keyword}</span></h6>
                            <small><strong>${match.count}</strong> разів</small>
                        </div>
                        <p class="mb-1">
                            <small>
                                <a href="${match.url}" target="_blank" class="text-decoration-none">
                                    <i class="fas fa-external-link-alt"></i> ${match.url.length > 80 ? match.url.substring(0, 80) + '...' : match.url}
                                </a>
                            </small>
                        </p>
                        <small class="text-muted">${match.context}</small>
                    </div>
                `).join('')}
            </div>
            ` : ''}
            
            <div class="d-flex justify-content-center gap-2 mt-3">
                <a href="/result/${resultData.task_id}" class="btn btn-primary" target="_blank">
                    <i class="fas fa-external-link-alt"></i> Детальний перегляд
                </a>
                <button class="btn btn-outline-primary" onclick="downloadResult('${resultData.task_id}')">
                    <i class="fas fa-download"></i> Завантажити Excel
                </button>
            </div>
        `;
    }

    showModalLoading(container) {
        container.innerHTML = `
            <div class="text-center">
                <div class="spinner-border" role="status">
                    <span class="visually-hidden">Завантаження...</span>
                </div>
                <p class="mt-2">Завантаження результату...</p>
            </div>
        `;
    }

    autoSave(element) {
        // Автозбереження даних в localStorage
        const key = `autosave_${element.name}`;
        localStorage.setItem(key, element.value);
        
        // Показ індикатора збереження
        this.showAutoSaveIndicator(element);
    }

    showAutoSaveIndicator(element) {
        const indicator = element.parentNode.querySelector('.autosave-indicator') || 
                         this.createAutoSaveIndicator(element);
        
        indicator.textContent = '✓ Збережено';
        indicator.style.opacity = '1';
        
        setTimeout(() => {
            indicator.style.opacity = '0';
        }, 2000);
    }

    createAutoSaveIndicator(element) {
        const indicator = document.createElement('small');
        indicator.className = 'autosave-indicator text-success';
        indicator.style.opacity = '0';
        indicator.style.transition = 'opacity 0.3s';
        element.parentNode.appendChild(indicator);
        return indicator;
    }

    loadAutoSavedData() {
        // Завантаження автозбережених даних
        const autoSaveElements = document.querySelectorAll('.auto-save');
        
        autoSaveElements.forEach(element => {
            const key = `autosave_${element.name}`;
            const savedValue = localStorage.getItem(key);
            
            if (savedValue && !element.value) {
                element.value = savedValue;
                this.showRestoreNotification(element);
            }
        });
    }

    showRestoreNotification(element) {
        const notification = document.createElement('div');
        notification.className = 'alert alert-info alert-dismissible fade show';
        notification.innerHTML = `
            Відновлено автозбережені дані
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        element.parentNode.insertBefore(notification, element);
        
        setTimeout(() => {
            notification.remove();
        }, 5000);
    }

    updateBatchProgress() {
        // Оновлення прогресу пакетного аналізу
        const batchId = document.body.dataset.batchId;
        if (!batchId) return;

        const updateProgress = async () => {
            try {
                const response = await fetch(`/batch/${batchId}/status`);
                const data = await response.json();
                
                this.updateBatchDisplay(data);
                
                // Продовжуємо оновлення якщо аналіз ще виконується
                if (data.status === 'running' || data.status === 'pending') {
                    setTimeout(updateProgress, 10000); // Кожні 10 секунд
                }
            } catch (error) {
                console.error('Помилка оновлення прогресу:', error);
            }
        };

        updateProgress();
    }

    updateBatchDisplay(batchData) {
        // Оновлення відображення пакетного аналізу
        const progressBar = document.querySelector('.batch-progress .progress-bar');
        const completedCount = document.querySelector('.completed-count');
        const failedCount = document.querySelector('.failed-count');
        const statusBadge = document.querySelector('.batch-status');

        if (progressBar) {
            const progress = ((batchData.completed_sites + batchData.failed_sites) / batchData.total_sites) * 100;
            progressBar.style.width = `${progress}%`;
        }

        if (completedCount) {
            completedCount.textContent = batchData.completed_sites;
        }

        if (failedCount) {
            failedCount.textContent = batchData.failed_sites;
        }

        if (statusBadge) {
            statusBadge.className = `badge bg-${this.getStatusColor(batchData.status)}`;
            statusBadge.textContent = batchData.status.toUpperCase();
        }
    }

    getStatusColor(status) {
        const colors = {
            'pending': 'secondary',
            'running': 'primary',
            'completed': 'success',
            'failed': 'danger'
        };
        return colors[status] || 'secondary';
    }

    // 🆕 НОВІ ФУНКЦІЇ ДЛЯ РОБОТИ З РЕЗУЛЬТАТАМИ
    setupResultActions() {
        // Налаштування дій для сторінки результатів
        const copyButtons = document.querySelectorAll('[data-copy]');
        copyButtons.forEach(button => {
            button.addEventListener('click', () => {
                const text = button.dataset.copy;
                this.copyToClipboard(text);
            });
        });
    }

    setupTableSorting() {
        // Простий пошук в таблицях
        const tables = document.querySelectorAll('table');
        tables.forEach((table, index) => {
            this.addTableSearch(table, `search_${index}`);
        });
    }

    addTableSearch(table, searchId) {
        const searchContainer = document.createElement('div');
        searchContainer.className = 'mb-3';
        searchContainer.innerHTML = `
            <input type="text" class="form-control" id="${searchId}" placeholder="Пошук в таблиці...">
        `;
        
        table.parentNode.insertBefore(searchContainer, table);
        
        const searchInput = document.getElementById(searchId);
        searchInput.addEventListener('input', () => {
            const searchTerm = searchInput.value.toLowerCase();
            const rows = table.querySelectorAll('tbody tr');
            
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(searchTerm) ? '' : 'none';
            });
        });
    }

    // 🆕 ФУНКЦІЇ ПОВІДОМЛЕНЬ
    showLoading() {
        const loadingOverlay = document.getElementById('loadingOverlay') || this.createLoadingOverlay();
        loadingOverlay.style.display = 'flex';
    }

    hideLoading() {
        const loadingOverlay = document.getElementById('loadingOverlay');
        if (loadingOverlay) {
            loadingOverlay.style.display = 'none';
        }
    }

    createLoadingOverlay() {
        const overlay = document.createElement('div');
        overlay.id = 'loadingOverlay';
        overlay.className = 'loading-overlay';
        overlay.innerHTML = `
            <div class="text-center">
                <div class="spinner-border spinner-border-lg" role="status">
                    <span class="visually-hidden">Завантаження...</span>
                </div>
                <p class="mt-3">Завантаження...</p>
            </div>
        `;
        document.body.appendChild(overlay);
        return overlay;
    }

    showSuccess(message) {
        this.showNotification(message, 'success');
    }

    showError(message) {
        this.showNotification(message, 'danger');
    }

    showWarning(message) {
        this.showNotification(message, 'warning');
    }

    showInfo(message) {
        this.showNotification(message, 'info');
    }

    showNotification(message, type = 'info') {
        // Показ уведомлення
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible fade show notification`;
        notification.style.position = 'fixed';
        notification.style.top = '20px';
        notification.style.right = '20px';
        notification.style.zIndex = '9999';
        notification.style.minWidth = '350px';
        notification.innerHTML = `
            <i class="fas fa-${this.getNotificationIcon(type)}"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(notification);
        
        // Автоматичне видалення через 5 секунд
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 5000);
    }

    getNotificationIcon(type) {
        const icons = {
            'success': 'check-circle',
            'danger': 'exclamation-triangle',
            'warning': 'exclamation-circle',
            'info': 'info-circle'
        };
        return icons[type] || 'info-circle';
    }

    copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(() => {
            this.showSuccess('Скопійовано в буфер обміну');
        }).catch(() => {
            this.showError('Помилка копіювання');
        });
    }

    // Ініціалізація при завантаженні сторінки
    static init() {
        return new CompetitorAnalysisApp();
    }
}

// 🆕 ГЛОБАЛЬНІ ФУНКЦІЇ ДЛЯ ВИКОРИСТАННЯ В ШАБЛОНАХ

// Показ результатів
function showResultDetails(taskId) {
    window.open(`/result/${taskId}`, '_blank');
}

// Завантаження результату
function downloadResult(taskId) {
    const app = window.app || new CompetitorAnalysisApp();
    app.downloadResult(taskId);
}

// Перегляд детальних результатів пакету
function viewBatchResults(batchId) {
    window.location.href = `/batch/${batchId}/results`;
}

// Копіювання в буфер
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showNotification('Скопійовано в буфер обміну', 'success');
    }).catch(() => {
        showNotification('Помилка копіювання', 'danger');
    });
}

// Показ уведомлень
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible fade show`;
    notification.style.position = 'fixed';
    notification.style.top = '20px';
    notification.style.right = '20px';
    notification.style.zIndex = '9999';
    notification.style.minWidth = '300px';
    
    notification.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check' : type === 'danger' ? 'exclamation-triangle' : type === 'warning' ? 'exclamation-circle' : 'info'}"></i>
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}

// Ініціалізація застосунку
document.addEventListener('DOMContentLoaded', () => {
    window.app = CompetitorAnalysisApp.init();
});

// Утилітарні функції
const Utils = {
    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('uk-UA', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    },

    formatDuration(seconds) {
        if (seconds < 60) {
            return `${seconds.toFixed(1)}с`;
        } else if (seconds < 3600) {
            const minutes = seconds / 60;
            return `${minutes.toFixed(1)}хв`;
        } else {
            const hours = seconds / 3600;
            return `${hours.toFixed(1)}год`;
        }
    },

    truncateText(text, maxLength) {
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    },

    downloadJson(data, filename) {
        const blob = new Blob([JSON.stringify(data, null, 2)], {
            type: 'application/json'
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
};

// Експорт для використання в інших модулях
window.CompetitorAnalysisApp = CompetitorAnalysisApp;
window.Utils = Utils;
