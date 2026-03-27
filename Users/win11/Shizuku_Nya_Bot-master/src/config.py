def generate_system_prompt(character, system_prompt_template):
    # 确保 brother_qqid 存在，否则使用默认值
    brother_qqid = character.get('brother_qqid', '')  # 使用 get 方法避免 KeyError
    
    # 其他逻辑保持不变
    return system_prompt_template.format(
        character_name=character['name'],
        character_description=character['description'],
        brother_qqid=brother_qqid,
        # 其他参数...
    )