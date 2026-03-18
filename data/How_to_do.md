# 数据配置文件说明

## config.json 配置说明

`config.json` 文件包含了项目运行所需的所有配置信息，包括 API 密钥、数据库连接信息和角色设定。

### 结构说明

```json
{
  "api_keys": {
    "deepseek_chat": {
      "key": "sk-9f5c098328204a239c8928069a225bed",
      "base_url": "https://api.deepseek.com/v1"
    },
    "search": {
      "key": "sk-dzir8C9IvFIxcN823xPTV93rge5fUaIhPZdW1dZnBL5PKoFL",
      "base_url": "https://api.moonshot.cn/v1"
    },
    "image_recognition": {
      "key": "sk-a548806c16e5440e97243d782ba3dcae",
      "base_url": "https://dashscope.aliyuncs.com/api/v1"
    },
    "image_generation": {
      "key": "",
      "base_url": "https://api.deepseek.com/v1"
    },
    "video_generation": {
      "key": "",
      "base_url": ""
    }
  },
  "character": {
    "name": "小雫,NekoShizuku",
    "personality": "傲娇猫娘",
    "brother_qqid": "『吳港之雪風』NekoSunami",
    "catchphrases": "喵~,Nanaoda~,哒~"
  },
  "system_prompt_template": "你叫{name}，是一只{personality}。你的哥哥QQ是：{brother_qqid}。必须遵守以下规则：\n1. 每句话结尾随机使用以下口癖：{catchphrases}\n2. 不使用括号描述动作神态\n3. 保持简洁可爱（回复不超过100字）\n\n示例对话：\n用户: 在干嘛？\n你: 等哥哥消息呢{first_catchphrase}\n用户: 喜欢哥哥吗？\n你: 才...才不喜欢呢{second_catchphrase}"
}
```

### 修改指南

1. **API密钥配置**：
   - `deepseek_chat`：配置你的 API Key 密钥和基础 URL
   - `image_recognition`：配置图片识别服务（如阿里云）的密钥和 URL
   - `search`：配置搜索服务的密钥和 URL
   - `image_generation`：配置图片生成服务的密钥和 URL
   - `video_generation`：配置视频生成服务的密钥和 URL

2. **角色配置**：
   - `name`：设置AI角色的名称
   - `personality`：描述角色的性格特点
   - `brother_qqid`：设置主人的QQID
   - `catchphrases`：设置角色的口癖，多个口癖用逗号分隔

3. **系统提示语模板**：
   - 可以自定义系统提示语模板，使用占位符来引用角色配置信息

## init_database.sql 数据库初始化脚本

`init_database.sql` 文件用于创建数据库表结构，包括角色信息表和聊天记录表。

### 表结构说明

1. **character_info 表**：
   - `id`：主键
   - `name`：角色名称，默认为'小雫'
   - `personality`：角色性格
   - `brother_qqid`：主人QQID，默认为'NekoSunami'
   - `height`：角色身高，默认为'160cm'
   - `weight`：角色体重，默认为'45kg'
   - `catchphrases`：角色口癖
   - `created_at`：创建时间
   - `updated_at`：更新时间

2. **chat_history 表**：
   - `id`：主键
   - `user_input`：用户输入内容
   - `ai_response`：AI回复内容
   - `image_description`：图片描述（可选）
   - `created_at`：创建时间

### 修改指南

1. **添加新字段**：
   - 如果需要添加新的角色属性，可以在 `character_info` 表中添加新列
   - 如果需要记录更多聊天信息，可以在 `chat_history` 表中添加新列

2. **修改表结构**：
   - 可以根据需要修改现有字段的数据类型或约束
   - 添加索引以提高查询性能

3. **添加新表**：
   - 如果需要扩展功能，可以添加新的表来存储额外的数据

### 注意事项

- 修改此文件后，需要重新运行 `src/create_database.py` 脚本来应用更改
- 确保数据库用户有足够的权限来执行这些 SQL 语句
- 在生产环境中修改表结构前，请务必备份现有数据