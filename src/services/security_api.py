# -*- coding: utf-8 -*-
"""
安全认证 API 模块

提供两层密码验证系统：
- Level 1: 工作模式密码
- Level 2: 广域管理模式密码
"""

from flask import Blueprint, request, jsonify
import hashlib
import time
import json
from src.core.config import CONFIG
from src.agent.amala_sandbox import AmalaSandbox

security_bp = Blueprint('security', __name__, url_prefix='/api/security')

# 初始化沙箱
sandbox = AmalaSandbox('agent_datas/workspace', CONFIG)

@security_bp.route('/status', methods=['GET'])
def get_security_status():
    """获取安全模式状态"""
    return jsonify({
        "ok": True,
        "global_admin_enabled": CONFIG.get('work_mode', {}).get('security_modes', {}).get('global_admin_enabled', False),
        "level1_configured": bool(CONFIG.get('work_mode', {}).get('security_modes', {}).get('level1_password_hash', '')),
        "level2_configured": bool(CONFIG.get('work_mode', {}).get('security_modes', {}).get('level2_password_hash', '')),
        "sandbox_mode": CONFIG.get('work_mode', {}).get('security_modes', {}).get('sandbox_mode', 'amala'),
        "platform": sandbox.get_status().get('platform', 'unknown'),
        "has_docker": sandbox.has_docker,
        "has_wsl": sandbox.has_wsl,
    })

@security_bp.route('/authenticate/level1', methods=['POST'])
def authenticate_level1():
    """
    Level 1 认证 (工作模式)
    
    Request JSON:
    {
        "password": "user_password"
    }
    
    Response:
    {
        "ok": true,
        "session_id": "uuid",
        "message": "Authentication successful"
    }
    """
    try:
        data = request.get_json() or {}
        password = data.get('password', '')
        
        if not password:
            return jsonify({"ok": False, "error": "Password required"}), 400
        
        # 验证密码
        level1_hash = CONFIG.get('work_mode', {}).get('security_modes', {}).get('level1_password_hash', '')
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        
        if pwd_hash != level1_hash or not level1_hash:
            return jsonify({"ok": False, "error": "Invalid password"}), 401
        
        # 创建会话
        session_id = sandbox.create_secure_session(1)
        
        return jsonify({
            "ok": True,
            "session_id": session_id,
            "level": 1,
            "message": "Level 1 authentication successful"
        }), 200
        
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@security_bp.route('/authenticate/level2', methods=['POST'])
def authenticate_level2():
    """
    Level 2 认证 (广域管理模式) - 需要先完成 Level 1
    
    Request JSON:
    {
        "session_id": "level1_session_id",
        "password": "level2_password"
    }
    
    Response:
    {
        "ok": true,
        "session_id": "new_uuid",
        "message": "Level 2 authentication successful"
    }
    """
    try:
        data = request.get_json() or {}
        session_id_l1 = data.get('session_id', '')
        password_l2 = data.get('password', '')
        
        if not password_l2:
            return jsonify({"ok": False, "error": "Password required"}), 400
        
        # 验证 Level 1 会话
        if not sandbox.verify_session(session_id_l1, required_level=1):
            return jsonify({"ok": False, "error": "Invalid or expired Level 1 session"}), 401
        
        # 验证 Level 2 密码
        level2_hash = CONFIG.get('work_mode', {}).get('security_modes', {}).get('level2_password_hash', '')
        pwd_hash = hashlib.sha256(password_l2.encode()).hexdigest()
        
        if pwd_hash != level2_hash or not level2_hash:
            return jsonify({"ok": False, "error": "Invalid Level 2 password"}), 401
        
        # 检查全局管理模式是否启用
        if not CONFIG.get('work_mode', {}).get('security_modes', {}).get('global_admin_enabled', False):
            return jsonify({"ok": False, "error": "Global admin mode is not enabled"}), 403
        
        # 创建 Level 2 会话
        session_id_l2 = sandbox.create_secure_session(2)
        
        return jsonify({
            "ok": True,
            "session_id": session_id_l2,
            "level": 2,
            "message": "Level 2 authentication successful"
        }), 200
        
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@security_bp.route('/execute', methods=['POST'])
def execute_with_security():
    """
    在指定安全级别执行代码
    
    Request JSON:
    {
        "code": "python code",
        "language": "python" or "javascript",
        "security_level": 0/1/2,
        "session_id": "session_uuid (required for level 1 and 2)"
    }
    """
    try:
        data = request.get_json() or {}
        code = data.get('code', '')
        language = data.get('language', 'python')
        security_level = int(data.get('security_level', 0))
        session_id = data.get('session_id', '')
        
        if not code:
            return jsonify({"ok": False, "error": "Code required"}), 400
        
        # 执行代码
        result = sandbox.execute(code, language, security_level, session_id)
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@security_bp.route('/config/set-passwords', methods=['POST'])
def set_passwords():
    """
    设置两层密码 (需要系统管理员权限)
    
    Request JSON:
    {
        "level1_password": "new password",
        "level2_password": "new password"
    }
    """
    try:
        data = request.get_json() or {}
        level1_pwd = data.get('level1_password', '')
        level2_pwd = data.get('level2_password', '')
        
        if not level1_pwd or not level2_pwd:
            return jsonify({"ok": False, "error": "Both passwords required"}), 400
        
        # 设置密码
        result = sandbox.set_security_passwords(level1_pwd, level2_pwd)
        
        if result.get('ok'):
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@security_bp.route('/config/enable-global-admin', methods=['POST'])
def enable_global_admin():
    """启用全局管理模式"""
    try:
        # 这应该由系统管理员仅通过系统级别的调用执行
        from src.core.config import CONFIG, SYSTEM_CONFIG_DATA
        
        wm = SYSTEM_CONFIG_DATA.get('work_mode', {})
        if not wm.get('security_modes'):
            wm['security_modes'] = {}
        
        wm['security_modes']['global_admin_enabled'] = True
        
        # 保存到文件
        data_dir = os.path.dirname(SYSTEM_CONFIG_DATA.get('_file_path', ''))
        config_path = os.path.join(data_dir, 'system_config.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(SYSTEM_CONFIG_DATA, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            "ok": True,
            "message": "Global admin mode enabled"
        }), 200
        
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@security_bp.route('/session/verify', methods=['POST'])
def verify_session():
    """
    验证会话是否有效
    
    Request JSON:
    {
        "session_id": "uuid",
        "required_level": 1/2
    }
    """
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id', '')
        required_level = int(data.get('required_level', 1))
        
        is_valid = sandbox.verify_session(session_id, required_level)
        
        return jsonify({
            "ok": is_valid,
            "valid": is_valid,
            "required_level": required_level
        }), 200
        
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
