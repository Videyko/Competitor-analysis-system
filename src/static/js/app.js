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
            const response = await fetch(`/status/${taskId}`);
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

    async viewResult(e) {
        e.preventDefault();
        
        const taskId = e.target.dataset.taskId;
        const modal = document.getElementById('resultModal');
        const modalBody = modal.querySelector('.modal-body');

        try {
            this.showModalLoading(modalBody);
            
            const response = await fetch(`/api/analysis/result/${taskId}`);
            const data = await response.json();
            
            this.displayResultInModal(modalBody, data);
            
            const modalInstance = new bootstrap.Modal(modal);
            modalInstance.show();
        } catch (error) {
            this.showError('Помилка завантаження результату');
        }
    }

    displayResultInModal(container, resultData) {
        container.innerHTML = `
            <h6>Сайт: ${resultData.site_url}</h6>
            <hr>
            <div class="row">
                <div class="col-md-6">
                    <h6 class="text-success">Позитивні збіги: ${resultData.positive_matches.length}</h6>
                    <ul class="list-unstyled">
                        ${resultData.positive_matches.slice(0, 5).map(match => 
                            `<li><strong>${match.keyword}</strong> (${match.count})</li>`
                        ).join('')}
                    </ul>
                </div>
                <div class="col-md-6">
                    <h6 class="text-danger">Негативні збіги: ${resultData.negative_matches.length}</h6>
                    <ul class="list-unstyled">
                        ${resultData.negative_matches.slice(0, 5).map(match => 
                            `<li><strong>${match.keyword}</strong> (${match.count})</li>`
                        ).join('')}
                    </ul>
                </div>
            </div>
            <hr>
            <p><strong>Сторінок проаналізовано:</strong> ${resultData.pages_analyzed}</p>
            <p><strong>Час аналізу:</strong> ${resultData.analysis_time.toFixed(1)} секунд</p>
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
                if (data.status === 'running') {
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

    showLoading() {
        // Показ індикатора завантаження
        const loadingOverlay = document.getElementById('loadingOverlay') || this.createLoadingOverlay();
        loadingOverlay.style.display = 'flex';
    }

    hideLoading() {
        // Приховування індикатора завантаження
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
        notification.innerHTML = `
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

    // Ініціалізація при завантаженні сторінки
    static init() {
        return new CompetitorAnalysisApp();
    }
}

// Ініціалізація застосунку
document.addEventListener('DOMContentLoaded', () => {
    CompetitorAnalysisApp.init();
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

    copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(() => {
            app.showSuccess('Скопійовано в буфер обміну');
        }).catch(() => {
            app.showError('Помилка копіювання');
        });
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