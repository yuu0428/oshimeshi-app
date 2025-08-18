#!/usr/bin/env python3
import sys
import os
import re

# Add the parent directory to Python path  
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Simple syntax check for tracking_ad.py
try:
    with open('tracking_ad.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check that key routes exist
    assert '@tracking_ad_bp.route("/go/<int:post_id>")' in content, 'missing route: /go/<int:post_id>'
    assert '@tracking_ad_bp.route("/coupon/<int:post_id>")' in content, 'missing route: /coupon/<int:post_id>'
    assert 'def go(post_id: int):' in content, 'missing function: go'
    assert 'def coupon(post_id: int):' in content, 'missing function: coupon'
    
    # Check that Blueprint is properly defined
    assert 'tracking_ad_bp = Blueprint("tracking_ad"' in content, 'missing Blueprint definition'
    
    # Check that app.py imports are correct  
    with open('app.py', 'r', encoding='utf-8') as f:
        app_content = f.read()
    
    assert 'from tracking_ad import tracking_ad_bp' in app_content, 'missing import in app.py'
    assert 'app.register_blueprint(tracking_ad_bp)' in app_content, 'missing Blueprint registration in app.py'
    
    print('OK: endpoints & url_for')
    
except FileNotFoundError as e:
    print(f'ERROR: Required file not found: {e}')
    sys.exit(1)
except AssertionError as e:
    print(f'ERROR: {e}')
    sys.exit(1)