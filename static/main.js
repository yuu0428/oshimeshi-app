// 推しメシアプリ統合JavaScript
// 既存HTML構造に対応したインタラクション機能

document.addEventListener('DOMContentLoaded', function() {
    //console.log('アプリケーション初期化開始');

    // フリーズ防止のための安全対策
    document.addEventListener('click', function(e) {
        // 透明なオーバーレイがある場合は削除
        const invisibleOverlays = document.querySelectorAll('[style*="z-index: 999"], [style*="z-index: 1000"]');
        invisibleOverlays.forEach(overlay => {
            if (overlay.style.opacity === '0' || overlay.style.display === 'none') {
                overlay.remove();
            }
        });
    }, true);
    
    // CSRFトークン取得関数
    function getCSRFToken() {
        if (window.csrf_token) {
            return window.csrf_token;
        }
        const metaToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
        if (metaToken) {
            return metaToken;
        }
        console.warn('CSRFトークンが見つかりません');
        return '';
    }
    
    // 1. いいね機能初期化
    initializeLikeButtons();
    
    // 2. モーダル機能初期化
    initializeModals();
    
    // 3. モバイルメニュー初期化
    initializeMobileMenu();
    
    // 5. フォーム関連の処理は最小限に
    initializeMinimalForms();
    
    // 6. アニメーション初期化
    initializeAnimations();
    
    // 7. スクロール効果
    initializeScrollEffects();

    // 8. 画像プレビュー初期化
    initializeImagePreview();

    // === 関数定義 ===
    
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
        document.addEventListener('click', function(e) {
            const likeButton = e.target.closest('.like-button');
            if (!likeButton) return;
            
            e.preventDefault();
            toggleLike(likeButton);
        });
    }
    
    function toggleLike(button) {
        const postId = button.getAttribute('data-post-id');
        const heartIcon = button.querySelector('.heart-icon') || button.querySelector('span:first-child');
        const likeCount = button.querySelector('span:last-child');
        const currentCount = parseInt(likeCount?.textContent || '0');
        
        // UI更新
        if (button.classList.contains('liked')) {
            button.classList.remove('liked');
            if (heartIcon) heartIcon.textContent = '🤍';
            if (likeCount) likeCount.textContent = Math.max(0, currentCount - 1);
        } else {
            button.classList.add('liked');
            if (heartIcon) heartIcon.textContent = '❤️';
            if (likeCount) likeCount.textContent = currentCount + 1;
        }
        
        // サーバーリクエスト
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
            .then(response => response.json())
            .then(data => {
                if (data.status === 'ok' && likeCount) {
                    likeCount.textContent = data.like_count;
                    if (heartIcon) {
                        heartIcon.textContent = data.is_liked ? '❤️' : '🤍';
                    }
                }
            })
            .catch(error => {
                console.error('いいね処理エラー:', error);
                toggleLike(button); // エラー時は元に戻す
            });
        }
    }

    // 画像プレビュー機能
    function initializeImagePreview() {
        const imageInput = document.querySelector('input[type="file"][name="image"]');
        if (!imageInput) return;

        // 既存のイベントリスナーをクリア
        const newInput = imageInput.cloneNode(true);
        imageInput.parentNode.replaceChild(newInput, imageInput);

        newInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (!file) return;
    
            // ファイル形式チェック
            if (!file.type.match(/^image\/(jpeg|jpg|png)$/i)) {
                alert('JPEG、PNG形式の画像のみ対応しています。');
                this.value = '';
                return;
            }
    
            // ファイルサイズチェック（10MB）
            if (file.size > 10 * 1024 * 1024) {
                alert('ファイルサイズは10MB以下にしてください。');
                this.value = '';
                return;
            }
    
            // プレビュー表示の前に既存のプレビューを削除
            const existingPreview = document.querySelector('.image-preview');
            if (existingPreview) {
                existingPreview.remove();
            }
    
            const reader = new FileReader();
            reader.onload = function(e) {
                try {
                    // 少し遅延を入れてDOMの準備を確実にする
                    setTimeout(() => {
                        showImagePreview(e.target.result, newInput);
                    }, 50);
                } catch (error) {
                    console.error('プレビュー表示エラー:', error);
                    alert('プレビューの表示に失敗しました。');
                }
            };
        
            reader.onerror = function() {
                alert('画像の読み込みに失敗しました。');
                newInput.value = '';
            };
        
            reader.readAsDataURL(file);
        });
    }

    // 画像プレビュー表示
    function showImagePreview(src, inputElement) {
        // 既存のプレビューを削除
        const existingPreview = document.querySelector('.image-preview');
        if (existingPreview) existingPreview.remove();

        // 新しいプレビューを作成
        const preview = document.createElement('div');
        preview.className = 'image-preview';
        preview.style.cssText = `
            position: relative;
            margin-top: 1rem;
            z-index: 10;
            background: white;
            padding: 10px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
            display: inline-block;
    `   ;
    
        const img = document.createElement('img');
        img.src = src;
        img.style.cssText = `
            max-width: 300px;
            max-height: 200px;
            border-radius: 8px;
            display: block;
    `   ;
    
        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'remove-preview';
        removeBtn.textContent = '✕';
        removeBtn.style.cssText = `
            position: absolute;
            top: 5px;
            right: 5px;
            background: #dc3545;
            color: white;
            border: none;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            font-size: 18px;
            cursor: pointer;
            z-index: 11;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
    `   ;
    
        preview.appendChild(img);
        preview.appendChild(removeBtn);
    
        // 親要素に追加（より安全な方法）
        const container = inputElement.closest('.form-group') || inputElement.parentElement;
        container.appendChild(preview);
    
        // 削除ボタンのイベント（確実にバインド）
        removeBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            inputElement.value = '';
            preview.remove();
        });
    
        // プレビューをスクロールして表示
        setTimeout(() => {
            preview.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }, 100);
    }

    // モーダル機能
    function initializeModals() {
        // 管理者モーダル
        const adminLoginBtn = document.getElementById('adminLoginBtn');
        const adminModal = document.getElementById('adminModal');
        
        if (adminLoginBtn && adminModal) {
            adminLoginBtn.addEventListener('click', function(e) {
                e.preventDefault();
                adminModal.style.display = 'block';
            });
        }
        
        // モーダルを閉じる処理
        document.addEventListener('click', function(e) {
            if (e.target.classList.contains('modal') || 
                e.target.id === 'closeModal' || 
                e.target.id === 'cancelBtn') {
                const modal = e.target.closest('.modal') || document.querySelector('.modal[style*="block"]');
                if (modal) modal.style.display = 'none';
            }
        });
        
        // 公式情報モーダル
        const officialBtns = document.querySelectorAll('#officialInfoBtn, #officialInfoBtnMobile');
        const officialModal = document.getElementById('officialInfoModal');
        
        officialBtns.forEach(btn => {
            if (btn && officialModal) {
                btn.addEventListener('click', function(e) {
                    e.preventDefault();
                    officialModal.style.display = 'block';
                });
            }
        });
        
        // ESCキーでモーダルを閉じる
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                const openModals = document.querySelectorAll('.modal[style*="display: block"], .official-info-modal[style*="display: block"]');
                openModals.forEach(modal => {
                    modal.style.display = 'none';
                });
            }
        });
        
        // 投稿詳細モーダル
        initializePostDetailModal();

        //  公式情報モーダルの初期化を追加
        initializeOfficialInfoModal();
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

        // モーダル閉じるボタン（一度だけ設定）
        if (closeBtn) {
            closeBtn.addEventListener('click', function() {
                postModal.style.display = 'none';
                document.body.style.overflow = 'auto';
            });
        }

        // モーダル外クリックで閉じる（一度だけ設定）
        postModal.addEventListener('click', function(e) {
            if (e.target === postModal) {
                postModal.style.display = 'none';
                document.body.style.overflow = 'auto';
            }
        });

        // ESCキーで閉じる（一度だけ設定）
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && postModal.style.display === 'block') {
                postModal.style.display = 'none';
                document.body.style.overflow = 'auto';
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
        modal.style.display = 'block';
        document.body.style.overflow = 'hidden';
    }

    // 公式情報モーダル初期化
    function initializeOfficialInfoModal() {
        // デスクトップ版
        const officialBtn = document.getElementById('officialInfoBtn');
        // モバイル版
        const officialBtnMobile = document.getElementById('officialInfoBtnMobile');
        const officialModal = document.getElementById('officialInfoModal');
        const closeBtn = document.getElementById('closeOfficialModal');
    
        if (!officialModal) return;

        // デスクトップ版ボタン
        if (officialBtn) {
            officialBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                openOfficialModal(officialModal);
            });
        }

        // モバイル版ボタン
        if (officialBtnMobile) {
            officialBtnMobile.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                openOfficialModal(officialModal);
            });
        }

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
                const instagramURL = 'https://instagram.com/oshimeshi_yamanashi';
            
                if (this.getAttribute('href') === '#' || !this.getAttribute('href')) {
                    alert('Instagramアカウントは近日公開予定です！\nしばらくお待ちください。');
                    return;
                }
            
                window.open(instagramURL, '_blank', 'noopener,noreferrer');
            });
        }
    }

    // 公式情報モーダルを開く
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

    // 公式情報モーダルを閉じる
    function closeOfficialModal(modal) {
        modal.style.opacity = '0';
    
        setTimeout(() => {
            modal.style.display = 'none';
            document.body.style.overflow = 'auto';
        
            // フォーカスを公式情報ボタンに戻す
            const officialBtn = document.getElementById('officialInfoBtn') || document.getElementById('officialInfoBtnMobile');
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

    // フォームバリデーションの修正版
    function initializeFormsValidation() {
        const forms = document.querySelectorAll('form');
    
        forms.forEach(form => {
            // iOS Safariでは簡略化されたバリデーション
            if (isiOSSafari()) {
                form.addEventListener('submit', function(e) {
                    const csrfToken = getCSRFToken();
                    if (!csrfToken) {
                        e.preventDefault();
                        alert('セキュリティトークンが見つかりません。ページを更新してください。');
                        return false;
                    }
                
                    let csrfInput = form.querySelector('input[name="csrf_token"]');
                    if (!csrfInput) {
                        csrfInput = document.createElement('input');
                        csrfInput.type = 'hidden';
                        csrfInput.name = 'csrf_token';
                        csrfInput.value = csrfToken;
                        form.appendChild(csrfInput);
                    }
                });
                return; // iOS Safariではリアルタイムバリデーションをスキップ
            }
        
            // デスクトップ版の既存コード
            form.addEventListener('submit', function(e) {
                if (!validateForm(this)) {
                    e.preventDefault();
                    return false;
                }
            
                const csrfToken = getCSRFToken();
                if (!csrfToken) {
                    e.preventDefault();
                    alert('セキュリティトークンが見つかりません。ページを更新してください。');
                    return false;
                }
            
                let csrfInput = form.querySelector('input[name="csrf_token"]');
                if (!csrfInput) {
                    csrfInput = document.createElement('input');
                    csrfInput.type = 'hidden';
                    csrfInput.name = 'csrf_token';
                    csrfInput.value = csrfToken;
                    form.appendChild(csrfInput);
                }
            });

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
    `   ;
    
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
        const mobileMenuBtn = document.getElementById('mobileMenuBtn');
        const mobileMenu = document.getElementById('mobileMenu');
        
        if (!mobileMenuBtn || !mobileMenu) return;
        
        mobileMenuBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            mobileMenu.classList.toggle('show');
            
            const isOpen = mobileMenu.classList.contains('show');
            const icon = this.querySelector('.hamburger-icon');
            if (icon) {
                icon.textContent = isOpen ? '✕' : '☰';
            }
        });
        
        // メニュー外クリックで閉じる
        document.addEventListener('click', function(e) {
            // クリックイベントを少し遅延させる
            setTimeout(() => {
                if (mobileMenu.classList.contains('show') && 
                    !mobileMenu.contains(e.target) && 
                    !mobileMenuBtn.contains(e.target)) {
                    mobileMenu.classList.remove('show');
                    const icon = mobileMenuBtn.querySelector('.hamburger-icon');
                    if (icon) icon.textContent = '☰';
                }
            }, 10);
        });
    }

    // iOS Safariの検出
    function isiOSSafari() {
        const ua = window.navigator.userAgent;
        const iOS = !!ua.match(/iPad/i) || !!ua.match(/iPhone/i);
        const webkit = !!ua.match(/WebKit/i);
        const iOSSafari = iOS && webkit && !ua.match(/CriOS/i);
        return iOSSafari;
    }

    // 検索・フィルタ機能
    function initializeSearchFilters() {
        // iOS Safariの場合は特別な処理を行わない
        if (isiOSSafari()) {
            //console.log('iOS Safari detected: Using native form controls');
        
            // すべてのselect要素からonchange属性を削除
            document.querySelectorAll('select[onchange]').forEach(select => {
                select.removeAttribute('onchange');
            });
        
            // タッチイベントの最適化
            document.querySelectorAll('input, select, textarea').forEach(element => {
                // 既存のイベントリスナーをすべて削除
                const newElement = element.cloneNode(true);
                element.parentNode.replaceChild(newElement, element);
            
                // iOSに最適化されたイベントリスナーを追加
                newElement.addEventListener('touchstart', function(e) {
                    // デフォルトの動作を維持
                    e.stopPropagation();
                }, { passive: true });
            });
        
            return; // iOS Safariでは以降の処理をスキップ
        }
    
        // デスクトップのみの処理
        const searchForm = document.querySelector('.search-form form');
        const filterSelects = document.querySelectorAll('select[onchange]');
    
        if (searchForm) {
            const searchInput = searchForm.querySelector('input[type="text"]');
            if (searchInput) {
                let searchTimeout;
                searchInput.addEventListener('input', function() {
                    clearTimeout(searchTimeout);
                    searchTimeout = setTimeout(() => {
                        performSearch(this.value);
                    }, 500);
                });
            }
        }

        filterSelects.forEach(select => {
            select.addEventListener('change', function() {
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


    // 最小限のフォーム処理
    function initializeMinimalForms() {
        // CSRFトークンの確認のみ
        document.querySelectorAll('form').forEach(form => {
            form.addEventListener('submit', function(e) {
                const csrfToken = getCSRFToken();
                if (!csrfToken) {
                    e.preventDefault();
                    alert('セキュリティトークンが見つかりません。ページを更新してください。');
                    return false;
                }
                
                // CSRFトークンをフォームに追加
                let csrfInput = form.querySelector('input[name="csrf_token"]');
                if (!csrfInput) {
                    csrfInput = document.createElement('input');
                    csrfInput.type = 'hidden';
                    csrfInput.name = 'csrf_token';
                    csrfInput.value = csrfToken;
                    form.appendChild(csrfInput);
                }
            });
        });
        
        // モバイルデバイスの場合、select要素の自動送信を無効化
        if (window.innerWidth <= 768) {
            document.querySelectorAll('select[onchange]').forEach(select => {
                select.removeAttribute('onchange');
            });
        }
    }

    // エラーハンドリング
    window.addEventListener('error', function(e) {
        console.error('JavaScript Error:', e.error);
    });

    // スクロール効果
    function initializeScrollEffects() {
        const header = document.querySelector('nav');
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


    // パフォーマンス最適化
    if ('requestIdleCallback' in window) {
        requestIdleCallback(() => {
            // 非重要な初期化処理
            //console.log('推しメシアプリが正常に初期化されました');
        });
    }

    // Service Worker登録（PWA対応準備）
    if ('serviceWorker' in navigator) {
        window.addEventListener('load', () => {
            // 将来的なPWA化に備えた準備
            //console.log('Service Worker準備完了');
        });
    }

    // iOS Safari用の追加最適化
    if (isiOSSafari()) {
        document.addEventListener('DOMContentLoaded', function() {
            // フォーム要素のタッチ最適化
            const formElements = document.querySelectorAll('input, select, textarea, button');
        
            formElements.forEach(element => {
                // タッチイベントの最適化
                element.style.webkitTouchCallout = 'default';
                element.style.webkitUserSelect = 'text';
            
                // z-indexの確認
                const computedStyle = window.getComputedStyle(element);
                if (computedStyle.position === 'static') {
                    element.style.position = 'relative';
                }
            });
        
            // ナビゲーションがフォーム要素を隠していないか確認
            const nav = document.querySelector('nav');
            if (nav) {
                nav.style.pointerEvents = 'auto';
                // ナビゲーション内の要素以外はpointer-eventsを継承しない
                document.querySelectorAll('nav *').forEach(el => {
                    el.style.pointerEvents = 'auto';
                });
            }
        });
    }
});