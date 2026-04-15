# -*- coding: utf-8 -*-
"""Reset work mode password helper for emergency recovery."""

import json
import os


def main():
    # reset_workmode_password.py 位于 src/tools/，向上两级到项目根目录
    project_root = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
    config_path = os.path.join(project_root, 'data', 'system_config.json')

    if not os.path.exists(config_path):
        print(f"Config not found: {config_path}")
        return

    with open(config_path, 'r', encoding='utf-8') as f:
        config_data = json.load(f)

    if 'work_mode' not in config_data:
        config_data['work_mode'] = {}

    config_data['work_mode']['enabled'] = False
    config_data['work_mode']['password_hash'] = ''

    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, ensure_ascii=False, indent=2)

    print('Work mode password has been reset.')
    print('Global work mode has been disabled for safety.')


if __name__ == '__main__':
    main()
