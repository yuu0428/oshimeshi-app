// 推しメシアプリ統合JavaScript
// 既存HTML構造に対応したインタラクション機能

document.addEventListener('DOMContentLoaded', function() {
    // 初期化処理
    initializeApp();
});

// CSRFトークンを取得する関数
function getCSRFToken() {
    // まずwindowオブジェクトから取得を試行
    if (window.csrf_token) {
        return window.csrf_token;
    }
    
    // 次にmetaタグから取得を試行
    const metaToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    if (metaToken) {
        return metaToken;
    }
    
    console.warn('CSRFトークンが見つかりません');
    return '';
}

// アプリケーション初期化
function initializeApp() {
    initializeAnimations();
    initializeLikeButtons();
    initializeModals();
    initializeFormsValidation();
    initializeMobileMenu();
    initializeSearchFilters();
    initializeImagePreview();
    initializeScrollEffects();
}

// スムーズアニメーション初期化
function initializeAnimations() {
    // カード要素のフェードインアニメーション
    const cards = document.querySelectorAll('.post-card, .ranking-item');
    
    if (cards.length > 0) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry, index) => {
                if (entry.isIntersecting) {
                    setTimeout(() => {
                        entry.target.style.opacity = '1';
                        entry.target.style.transform = 'translateY(0)';
                    }, index * 100);
                }
            });
        }, {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        });

        cards.forEach(card => {
            card.style.opacity = '0';
            card.style.transform = 'translateY(20px)';
            card.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
            observer.observe(card);
        });
    }
}

// いいね機能
function initializeLikeButtons() {
    const likeButtons = document.querySelectorAll('.like-button');
    
    likeButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            toggleLike(this);
        });
    });
}

function toggleLike(button) {
    const postId = button.getAttribute('data-post-id');
    const heartIcon = button.querySelector('.heart-icon') || button.querySelector('span:first-child');
    const likeCount = button.querySelector('span:last-child');
    const currentCount = parseInt(likeCount?.textContent || '0');
    
    // ローカル状態の更新（即座にUI反映）
    if (button.classList.contains('liked')) {
        button.classList.remove('liked');
        if (heartIcon) heartIcon.textContent = '🤍';
        if (likeCount) likeCount.textContent = Math.max(0, currentCount - 1);
    } else {
        button.classList.add('liked');
        if (heartIcon) heartIcon.textContent = '❤️';
        if (likeCount) likeCount.textContent = currentCount + 1;
        
        // ハートビートアニメーション
        if (heartIcon) {
            heartIcon.style.animation = 'heartBeat 0.6s ease';
            setTimeout(() => {
                heartIcon.style.animation = '';
            }, 600);
        }
    }

    // サーバーへのリクエスト（非同期）
    if (postId) {
        const csrfToken = getCSRFToken();
    
        fetch(`/like/${postId}`, {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': csrfToken
            },
            body: `csrf_token=${encodeURIComponent(csrfToken)}`,
            credentials: 'same-origin'
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'ok' && likeCount) {
                likeCount.textContent = data.like_count;
                // ハートの状態も更新
                if (heartIcon) {
                    heartIcon.textContent = data.is_liked ? '❤️' : '🤍';
                }
            }
        })
        .catch(error => {
            console.error('いいね処理エラー:', error);
            // エラー時は元の状態に戻す
            toggleLike(button);
        });
    }
}

// モーダル機能
function initializeModals() {
    // 管理者ログインモーダル
    const adminLoginBtn = document.getElementById('adminLoginBtn');
    const adminModal = document.getElementById('adminModal');
    const closeModal = document.getElementById('closeModal');
    const cancelBtn = document.getElementById('cancelBtn');

    if (adminLoginBtn && adminModal) {
        adminLoginBtn.addEventListener('click', function(e) {
            e.preventDefault();
            openModal(adminModal);
        });
    }

    if (closeModal && adminModal) {
        closeModal.addEventListener('click', function() {
            closeModalFunc(adminModal);
        });
    }

    if (cancelBtn && adminModal) {
        cancelBtn.addEventListener('click', function() {
            closeModalFunc(adminModal);
        });
    }

    // モーダル外クリックで閉じる
    if (adminModal) {
        adminModal.addEventListener('click', function(e) {
            if (e.target === adminModal) {
                closeModalFunc(adminModal);
            }
        });
    }

    // 🆕 公式情報モーダル
    initializeOfficialInfoModal();

    // ESCキーでモーダルを閉じる
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const openModals = document.querySelectorAll('.modal[style*="display: block"], .modal[style*="display:block"], .official-info-modal[style*="display: block"]');
            openModals.forEach(modal => {
                if (modal.classList.contains('official-info-modal')) {
                    closeOfficialModal(modal);
                } else {
                    closeModalFunc(modal);
                }
            });
        }
    });

    // 投稿詳細モーダル
    initializePostDetailModal();
}

// 投稿詳細モーダルの初期化
function initializePostDetailModal() {
    const postCards = document.querySelectorAll('.post-card');
    const postModal = document.getElementById('postDetailModal');
    const closeBtn = document.getElementById('closePostModal');
    
    if (!postModal) return;

    // 投稿カードクリックイベント
    postCards.forEach(card => {
        card.addEventListener('click', function(e) {
            // いいねボタンや削除ボタンがクリックされた場合は除外
            if (e.target.closest('.like-button, .delete-button')) {
                return;
            }
            
            e.preventDefault();
            showPostDetail(this);
        });
        
        // カードにカーソルスタイルを適用
        card.style.cursor = 'pointer';
    });

    // モーダル閉じるボタン
    if (closeBtn) {
        closeBtn.addEventListener('click', function() {
            closeModalFunc(postModal);
        });
    }

    // モーダル外クリックで閉じる
    postModal.addEventListener('click', function(e) {
        if (e.target === postModal) {
            closeModalFunc(postModal);
        }
    });
}

// 投稿詳細をモーダルで表示
function showPostDetail(cardElement) {
    const modal = document.getElementById('postDetailModal');
    if (!modal) return;

    // カードからデータを取得
    const image = cardElement.querySelector('.post-image');
    const storeName = cardElement.querySelector('h3').textContent;
    const postMeta = cardElement.querySelector('.post-meta');
    const caption = cardElement.querySelector('.post-caption').textContent;
    const likeButton = cardElement.querySelector('.like-button');
    
    // 地域、価格帯、投稿者、高校情報を抽出
    const metaText = postMeta.textContent;
    const areaMatch = metaText.match(/地域:\s*([^|]+)/);
    const priceMatch = metaText.match(/価格帯:\s*([^|]+)/);
    const userMatch = metaText.match(/投稿者:\s*([^|]+)/);
    const schoolMatch = metaText.match(/高校:\s*(.+)/);
    
    const area = areaMatch ? areaMatch[1].trim() : '';
    const priceRange = priceMatch ? priceMatch[1].trim() : '';
    const username = userMatch ? userMatch[1].trim() : '';
    const school = schoolMatch ? schoolMatch[1].trim() : '';

    // モーダル内容を更新
    const modalImage = modal.querySelector('.modal-image');
    const modalStoreName = modal.querySelector('.modal-store-name');
    const modalArea = modal.querySelector('.modal-area');
    const modalPrice = modal.querySelector('.modal-price');
    const modalUser = modal.querySelector('.modal-user');
    const modalSchool = modal.querySelector('.modal-school');
    const modalCaption = modal.querySelector('.modal-caption');
    const modalLikeButton = modal.querySelector('.modal-like-button');

    // 画像
    if (image && modalImage) {
        modalImage.src = image.src;
        modalImage.alt = image.alt;
        modalImage.style.display = 'block';
    } else if (modalImage) {
        modalImage.style.display = 'none';
    }

    // テキスト情報
    if (modalStoreName) modalStoreName.textContent = storeName;
    if (modalArea) modalArea.textContent = area;
    if (modalPrice) modalPrice.textContent = priceRange;
    if (modalUser) modalUser.textContent = username;
    if (modalSchool) {
        if (school) {
            modalSchool.textContent = school;
            modalSchool.parentElement.style.display = 'block';
        } else {
            modalSchool.parentElement.style.display = 'none';
        }
    }
    if (modalCaption) modalCaption.textContent = caption;

    // いいねボタン
    if (modalLikeButton && likeButton) {
        modalLikeButton.className = likeButton.className;
        modalLikeButton.setAttribute('data-post-id', likeButton.getAttribute('data-post-id'));
        modalLikeButton.innerHTML = likeButton.innerHTML;
    }

    // モーダルを表示
    openModal(modal);
}

// 🆕 公式情報モーダル初期化
function initializeOfficialInfoModal() {
    const officialBtn = document.getElementById('officialInfoBtn');
    const officialModal = document.getElementById('officialInfoModal');
    const closeBtn = document.getElementById('closeOfficialModal');
    
    if (!officialBtn || !officialModal) return;

    // 公式情報ボタンクリック
    officialBtn.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        openOfficialModal(officialModal);
    });

    // 閉じるボタンクリック
    if (closeBtn) {
        closeBtn.addEventListener('click', function(e) {
            e.preventDefault();
            closeOfficialModal(officialModal);
        });
    }

    // モーダル外クリックで閉じる
    officialModal.addEventListener('click', function(e) {
        if (e.target === officialModal) {
            closeOfficialModal(officialModal);
        }
    });

    // Instagramボタンの処理
    const instagramBtn = officialModal.querySelector('.instagram-btn');
    if (instagramBtn) {
        instagramBtn.addEventListener('click', function(e) {
            e.preventDefault();
            // デプロイ後にInstagramアカウント作成時にリンクを設定
            const instagramURL = 'https://instagram.com/oshimeshi_yamanashi';
            
            // 実際のリンクが設定されるまでは案内メッセージ
            if (this.getAttribute('href') === '#' || !this.getAttribute('href')) {
                alert('Instagramアカウントは近日公開予定です！\nしばらくお待ちください。');
                return;
            }
            
            window.open(instagramURL, '_blank', 'noopener,noreferrer');
        });
    }
}

// 🆕 公式情報モーダルを開く
function openOfficialModal(modal) {
    modal.style.display = 'block';
    document.body.style.overflow = 'hidden';
    
    // フェードイン効果
    modal.style.opacity = '0';
    setTimeout(() => {
        modal.style.opacity = '1';
    }, 10);
    
    // フォーカス管理
    const closeBtn = modal.querySelector('.official-info-close');
    if (closeBtn) {
        closeBtn.focus();
    }
}

// 🆕 公式情報モーダルを閉じる
function closeOfficialModal(modal) {
    modal.style.opacity = '0';
    
    setTimeout(() => {
        modal.style.display = 'none';
        document.body.style.overflow = 'auto';
        
        // フォーカスを公式情報ボタンに戻す
        const officialBtn = document.getElementById('officialInfoBtn');
        if (officialBtn) {
            officialBtn.focus();
        }
    }, 300);
}



function openModal(modal) {
    modal.style.display = 'block';
    document.body.style.overflow = 'hidden';
    
    // フェードインアニメーション
    modal.style.opacity = '0';
    setTimeout(() => {
        modal.style.opacity = '1';
    }, 10);
}

function closeModalFunc(modal) {
    modal.style.opacity = '0';
    setTimeout(() => {
        modal.style.display = 'none';
        document.body.style.overflow = 'auto';
    }, 300);
}

// フォームバリデーション
function initializeFormsValidation() {
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            // 既存のバリデーション
            if (!validateForm(this)) {
                e.preventDefault();
                return false;
            }
            
            // CSRFトークン確認を追加
            const csrfToken = getCSRFToken();
            if (!csrfToken) {
                e.preventDefault();
                alert('セキュリティトークンが見つかりません。ページを更新してください。');
                return false;
            }
            
            // フォームにCSRFトークンがない場合は追加
            let csrfInput = form.querySelector('input[name="csrf_token"]');
            if (!csrfInput) {
                csrfInput = document.createElement('input');
                csrfInput.type = 'hidden';
                csrfInput.name = 'csrf_token';
                csrfInput.value = csrfToken;
                form.appendChild(csrfInput);
            }
        });

        // リアルタイムバリデーション
        const inputs = form.querySelectorAll('input[required], textarea[required], select[required]');
        inputs.forEach(input => {
            input.addEventListener('blur', function() {
                validateField(this);
            });
            
            input.addEventListener('input', function() {
                clearFieldError(this);
            });
        });
    });
}

function validateForm(form) {
    let isValid = true;
    const requiredFields = form.querySelectorAll('input[required], textarea[required], select[required]');
    
    requiredFields.forEach(field => {
        if (!validateField(field)) {
            isValid = false;
        }
    });
    
    return isValid;
}

function validateField(field) {
    const value = field.value.trim();
    const fieldName = field.name;
    let isValid = true;
    let errorMessage = '';

    // 必須チェック
    if (field.hasAttribute('required') && !value) {
        isValid = false;
        errorMessage = 'この項目は必須です';
    }

    // 特定フィールドの詳細バリデーション
    if (value) {
        switch (fieldName) {
            case 'store_name':
                if (value.length > 50) {
                    isValid = false;
                    errorMessage = '店名は50文字以内で入力してください';
                }
                break;
            case 'caption':
                if (value.length > 500) {
                    isValid = false;
                    errorMessage = 'キャプションは500文字以内で入力してください';
                }
                break;
            case 'new_username':
                if (value.length > 50) {
                    isValid = false;
                    errorMessage = 'ユーザー名は50文字以内で入力してください';
                } else if (!/^[a-zA-Z0-9あ-んア-ヶー一-龯\s]+$/.test(value)) {
                    isValid = false;
                    errorMessage = 'ユーザー名に使用できない文字が含まれています';
                }
                break;
        }
    }

    // エラー表示
    if (!isValid) {
        showFieldError(field, errorMessage);
    } else {
        clearFieldError(field);
    }

    return isValid;
}

function showFieldError(field, message) {
    clearFieldError(field);
    
    field.style.borderColor = '#ff6b6b';
    field.style.backgroundColor = 'rgba(255, 107, 107, 0.05)';
    
    const errorDiv = document.createElement('div');
    errorDiv.className = 'field-error';
    errorDiv.textContent = message;
    errorDiv.style.cssText = `
        color: #ff6b6b;
        font-size: 0.8rem;
        margin-top: 0.25rem;
        display: block;
    `;
    
    field.parentNode.insertBefore(errorDiv, field.nextSibling);
}

function clearFieldError(field) {
    field.style.borderColor = '';
    field.style.backgroundColor = '';
    
    const errorDiv = field.parentNode.querySelector('.field-error');
    if (errorDiv) {
        errorDiv.remove();
    }
}

// モバイルメニュー
function initializeMobileMenu() {
    const nav = document.querySelector('nav');
    if (!nav) return;

    // モバイルメニューボタンを作成
    const mobileMenuBtn = document.createElement('button');
    mobileMenuBtn.className = 'mobile-menu-btn';
    mobileMenuBtn.innerHTML = '☰';
    mobileMenuBtn.style.cssText = `
        display: none;
        background: none;
        border: none;
        font-size: 1.5rem;
        color: #4A4A4A;
        cursor: pointer;
        padding: 0.5rem;
    `;

    // ナビゲーションリンクを取得
    const navLinks = nav.querySelectorAll('a:not(.mobile-menu-btn)');
    
    // モバイルメニューコンテナを作成
    const mobileMenu = document.createElement('div');
    mobileMenu.className = 'mobile-menu';
    mobileMenu.style.cssText = `
        display: none;
        position: absolute;
        top: 100%;
        left: 0;
        right: 0;
        background: rgba(253, 252, 248, 0.95);
        backdrop-filter: blur(10px);
        border-top: 1px solid rgba(164, 165, 132, 0.1);
        padding: 1rem;
        flex-direction: column;
        gap: 1rem;
    `;

    // メニューボタンクリックイベント
    mobileMenuBtn.addEventListener('click', function() {
        const isOpen = mobileMenu.style.display === 'flex';
        mobileMenu.style.display = isOpen ? 'none' : 'flex';
        this.innerHTML = isOpen ? '☰' : '✕';
    });

    // ナビゲーションに追加
    if (nav.firstChild) {
        nav.insertBefore(mobileMenuBtn, nav.firstChild);
    }
    nav.appendChild(mobileMenu);

    // レスポンシブ表示制御
    function updateMobileMenu() {
        if (window.innerWidth <= 768) {
            mobileMenuBtn.style.display = 'block';
            navLinks.forEach(link => {
                if (!mobileMenu.contains(link)) {
                    mobileMenu.appendChild(link.cloneNode(true));
                    link.style.display = 'none';
                }
            });
        } else {
            mobileMenuBtn.style.display = 'none';
            mobileMenu.style.display = 'none';
            navLinks.forEach(link => {
                link.style.display = '';
            });
        }
    }

    window.addEventListener('resize', updateMobileMenu);
    updateMobileMenu();
}

// 検索・フィルタ機能
function initializeSearchFilters() {
    const searchForm = document.querySelector('.search-form form');
    const filterSelects = document.querySelectorAll('select[onchange]');
    
    // 検索フォームの拡張
    if (searchForm) {
        const searchInput = searchForm.querySelector('input[type="text"]');
        if (searchInput) {
            // リアルタイム検索（デバウンス付き）
            let searchTimeout;
            searchInput.addEventListener('input', function() {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    performSearch(this.value);
                }, 500);
            });
        }
    }

    // フィルタ選択の拡張
    filterSelects.forEach(select => {
        select.addEventListener('change', function() {
            // アニメーション付きでフィルタを適用
            const container = document.querySelector('.posts-container, .ranking-container');
            if (container) {
                container.style.opacity = '0.5';
                container.style.transform = 'scale(0.98)';
                
                setTimeout(() => {
                    this.form.submit();
                }, 150);
            } else {
                this.form.submit();
            }
        });
    });
}

function performSearch(query) {
    // 実際の検索処理はサーバーサイドで行うため、
    // ここではUI的なフィードバックのみ実装
    const searchResults = document.querySelector('.posts-container, .search-results');
    if (searchResults && query.length > 2) {
        searchResults.style.opacity = '0.7';
        
        // 模擬的な検索処理
        setTimeout(() => {
            searchResults.style.opacity = '1';
        }, 300);
    }
}

// 画像プレビュー機能
function initializeImagePreview() {
    const imageInput = document.getElementById('image');
    if (!imageInput) return;

    imageInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (!file) return;

        // ファイルタイプチェック
        if (!file.type.match('image.*')) {
            alert('画像ファイルを選択してください');
            this.value = '';
            return;
        }

        // ファイルサイズチェック（5MB制限）
        const maxSize = 5 * 1024 * 1024;
        if (file.size > maxSize) {
            alert('ファイルサイズは5MB以下にしてください');
            this.value = '';
            return;
        }

        // プレビュー表示
        const reader = new FileReader();
        reader.onload = function(e) {
            showImagePreview(e.target.result);
        };
        reader.readAsDataURL(file);
    });
}

function showImagePreview(src) {
    // 既存のプレビューを削除
    const existingPreview = document.querySelector('.image-preview');
    if (existingPreview) {
        existingPreview.remove();
    }

    // プレビュー要素を作成
    const preview = document.createElement('div');
    preview.className = 'image-preview';
    preview.style.cssText = `
        margin-top: 1rem;
        text-align: center;
        position: relative;
        display: inline-block;
    `;

    const img = document.createElement('img');
    img.src = src;
    img.style.cssText = `
        max-width: 300px;
        max-height: 200px;
        border-radius: 8px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        object-fit: cover;
        display: block;
    `;

    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.innerHTML = '✕';
    removeBtn.style.cssText = `
        position: absolute;
        top: 5px;
        right: 5px;
        background: rgba(255, 107, 107, 0.8);
        color: white;
        border: none;
        border-radius: 50%;
        width: 24px;
        height: 24px;
        cursor: pointer;
        font-size: 14px;
        line-height: 24px;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 1px 5px rgba(0,0,0,0.2);
        transition: background 0.2s ease;
    `;
    removeBtn.onmouseover = () => { removeBtn.style.background = '#ff6b6b'; };
    removeBtn.onmouseout = () => { removeBtn.style.background = 'rgba(255, 107, 107, 0.8)'; };

    removeBtn.addEventListener('click', function() {
        document.getElementById('image').value = '';
        preview.remove();
    });

    preview.appendChild(img);
    preview.appendChild(removeBtn);

    // 画像入力フィールドの後に挿入
    const imageInput = document.getElementById('image');
    imageInput.parentElement.appendChild(preview);
}

// スクロール効果
function initializeScrollEffects() {
    const header = document.querySelector('nav, .header');
    if (!header) return;

    let lastScrollY = window.scrollY;
    let ticking = false;

    function updateHeader() {
        const scrollY = window.scrollY;
        
        if (scrollY > 100) {
            header.style.background = 'rgba(253, 252, 248, 0.95)';
            header.style.backdropFilter = 'blur(10px)';
            header.style.boxShadow = '0 2px 20px rgba(164, 165, 132, 0.1)';
        } else {
            header.style.background = 'rgba(253, 252, 248, 0.8)';
            header.style.backdropFilter = 'blur(5px)';
            header.style.boxShadow = 'none';
        }

        lastScrollY = scrollY;
        ticking = false;
    }

    function requestTick() {
        if (!ticking) {
            requestAnimationFrame(updateHeader);
            ticking = true;
        }
    }

    window.addEventListener('scroll', requestTick);
}

// ユーティリティ関数
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// エラーハンドリング
window.addEventListener('error', function(e) {
    console.error('JavaScript Error:', e.error);
});

// パフォーマンス最適化
if ('requestIdleCallback' in window) {
    requestIdleCallback(() => {
        // 非重要な初期化処理
        console.log('推しメシアプリが正常に初期化されました');
    });
}

// Service Worker登録（PWA対応準備）
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        // 将来的なPWA化に備えた準備
        console.log('Service Worker準備完了');
    });
}