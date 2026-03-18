// 启动不同模式
async function runMode(mode){
  toastr.info('正在启动模式 ' + mode + '...');
  try {
    const r = await fetch('/api/run_mode',{
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({mode})
    });
    const result = await r.json();
    toastr.success(result.message);
  } catch (e) {
    console.error('启动模式失败:', e);
    toastr.error('启动模式失败: ' + e.message);
  }
}

// 服务诊断
async function runDiagnostics(){
  toastr.info('正在运行服务诊断...');
  try {
    const txt = await fetch('/api/diagnosis').then(r=>r.text());
    const logEl = document.getElementById('log');
    if (logEl) {
      logEl.textContent = txt;
      logEl.scrollTop = logEl.scrollHeight;
    }
    toastr.success('服务诊断完成');
  } catch (e) {
    console.error('服务诊断失败:', e);
    toastr.error('服务诊断失败: ' + e.message);
    const logEl = document.getElementById('log');
    if (logEl) {
      logEl.textContent = '服务诊断失败: ' + e.message;
      logEl.scrollTop = logEl.scrollHeight;
    }
  }
}

// 定时刷新日志
async function refreshLog(){
  try {
    // 只有当日志元素可见时才刷新
    const logViewer = document.getElementById('logViewer');
    if (!logViewer || !logViewer.classList.contains('show')) {
      return; // 面板未展开则不刷新
    }
    
    // 添加超时控制
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000); // 5秒超时
    
    const response = await fetch('/api/logs', { signal: controller.signal });
    clearTimeout(timeoutId);
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const txt = await response.text();
    const logEl = document.getElementById('log');
    if (logEl) {
      logEl.textContent = txt;
      logEl.scrollTop = logEl.scrollHeight;
    }
  } catch (e) {
    if (e.name === 'AbortError') {
      console.error('刷新日志超时');
      toastr.error('刷新日志超时');
    } else {
      console.error('刷新日志失败:', e);
      toastr.error('刷新日志失败: ' + e.message);
    }
  }
}

// 终端命令处理
async function handleTerminalCommand(event) {
  if (event.key === 'Enter') {
    const input = event.target;
    const command = input.value.trim();
    
    if (command) {
      // 显示命令在日志中
      const logEl = document.getElementById('log');
      if (logEl) {
        logEl.textContent += `\n$ ${command}`;
        logEl.scrollTop = logEl.scrollHeight;
      }
      
      // 清空输入框
      input.value = '';
      
      try {
        // 发送命令到服务器，添加超时控制
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000); // 10秒超时
        
        const res = await fetch('/api/exec_cmd', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ cmd: command }),
          signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        const result = await res.text();
        
        // 显示结果在日志中
        if (logEl) {
          logEl.textContent += `\n${result}`;
          logEl.scrollTop = logEl.scrollHeight;
        }
        
        toastr.success('命令执行完成');
      } catch (e) {
        if (e.name === 'AbortError') {
          console.error('执行命令超时');
          const errorMsg = '执行命令超时';
          
          const logEl = document.getElementById('log');
          if (logEl) {
            logEl.textContent += `\n${errorMsg}`;
            logEl.scrollTop = logEl.scrollHeight;
          }
          
          toastr.error(errorMsg);
        } else {
          console.error('执行命令失败:', e);
          const errorMsg = `执行命令失败: ${e.message}`;
          
          const logEl = document.getElementById('log');
          if (logEl) {
            logEl.textContent += `\n${errorMsg}`;
            logEl.scrollTop = logEl.scrollHeight;
          }
          
          toastr.error(errorMsg);
        }
      }
    }
  }
}

// 加载聊天记录
async function refreshRecords(){
  try {
    // 只有当数据库管理面板可见时才刷新
    const dbPanel = document.getElementById('databaseManagement');
    if (!dbPanel || !dbPanel.classList.contains('show')) {
      return; // 面板未展开则不刷新
    }
    
    // 显示加载指示器
    const tbody = document.querySelector('#records tbody');
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="3" class="text-center">加载中...</td></tr>`;
    }
    
    // 添加超时控制
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000); // 10秒超时（增加超时时间）
    
    // 减少请求数量到50条记录
    const response = await fetch('/api/records?limit=50', { signal: controller.signal });
    clearTimeout(timeoutId);
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    
    if (tbody) {
      tbody.innerHTML = '';
      if (data.length === 0) {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td colspan="3" class="text-center">暂无聊天记录</td>`;
        tbody.appendChild(tr);
      } else {
        // 限制显示的记录数量
        const displayData = data.slice(0, 50);
        displayData.forEach((row,i)=>{
          const tr = document.createElement('tr');
          // 格式化聊天记录显示
          let messageDisplay = '';
          if (row.length >= 3) {
            // 假设字段顺序为: id, user_message, bot_response, timestamp
            const userMessage = row[1] || '';
            const botResponse = row[2] || '';
            // 限制显示长度
            const userMessageDisplay = userMessage.length > 100 ? userMessage.substring(0, 100) + '...' : userMessage;
            const botResponseDisplay = botResponse.length > 100 ? botResponse.substring(0, 100) + '...' : botResponse;
            messageDisplay = `<strong>用户:</strong> ${userMessageDisplay}<br><strong>机器人:</strong> ${botResponseDisplay}`;
          } else {
            // 限制显示长度
            const rowString = JSON.stringify(row);
            messageDisplay = rowString.length > 200 ? rowString.substring(0, 200) + '...' : rowString;
          }
          
          tr.innerHTML = `<td>${i+1}</td>
                          <td>${messageDisplay}</td>
                          <td><button class="btn btn-sm btn-danger" onclick="deleteRecord(${row[0]})">删除</button></td>`;
          tbody.appendChild(tr);
        });
      }
    }
    toastr.success('记录加载成功');
  } catch (e) {
    if (e.name === 'AbortError') {
      console.error('加载记录超时');
      toastr.error('加载记录超时');
    } else {
      console.error('加载记录失败:', e);
      toastr.error('加载记录失败: ' + e.message);
    }
    
    // 即使出错也确保表格有内容
    const tbody = document.querySelector('#records tbody');
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="3" class="text-center">加载记录失败: ${e.message}</td></tr>`;
    }
  }
}

// 删除单条
async function deleteRecord(id){
  if(!confirm('确认删除 ID='+id+'？')) return;
  try {
    const response = await fetch('/api/delete_record',{
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id})
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    await refreshRecords();
    toastr.success('记录删除成功');
  } catch (e) {
    console.error('删除记录失败:', e);
    toastr.error('删除记录失败: ' + e.message);
  }
}

// 清空所有
async function clearAll(){
  if(!confirm('确认清空所有聊天记录？')) return;
  try {
    const response = await fetch('/api/clear_records',{method:'POST'});
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    await refreshRecords();
    toastr.success('所有记录已清空');
  } catch (e) {
    console.error('清空记录失败:', e);
    toastr.error('清空记录失败: ' + e.message);
  }
}

// 删除前 N 条
async function deleteFirstN(){
  const n = parseInt(document.getElementById('delN').value);
  if(!n || n<1){ toastr.warning('请输入有效 N'); return; }
  try {
    const response = await fetch('/api/delete_first_n',{
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({n})
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    await refreshRecords();
    toastr.success(`前${n}条记录已删除`);
  } catch (e) {
    console.error('删除前N条记录失败:', e);
    toastr.error('删除前N条记录失败: ' + e.message);
  }
}

// 诊断功能 - 用于诊断页面
async function runDiagnosis() {
  try {
    const response = await fetch('/api/diagnosis');
    const result = await response.text();
    const resultEl = document.getElementById('result');
    if (resultEl) {
      resultEl.innerHTML = result;
    }
  } catch (e) {
    console.error('诊断执行失败:', e);
    const resultEl = document.getElementById('result');
    if (resultEl) {
      resultEl.textContent = '诊断执行失败: ' + e.message;
    }
  }
}

// 直接启动沙箱聊天模式
async function startSandbox() {
  toastr.info('正在启动沙箱聊天模式...');
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000); // 10秒超时
    
    const response = await fetch('/api/batch/2', {
      method: 'POST',
      signal: controller.signal
    });
    
    clearTimeout(timeoutId);
    
    if (response.ok) {
      // 在新窗口中打开沙箱页面
      setTimeout(() => {
        window.open('/sandbox', '_blank');
        toastr.success('沙箱聊天模式已启动');
      }, 1000); // 等待1秒确保服务已启动
    } else {
      toastr.error('启动沙箱聊天失败');
    }
  } catch (error) {
    if (error.name === 'AbortError') {
      toastr.error('启动沙箱聊天超时');
    } else {
      console.error('Error starting sandbox:', error);
      toastr.error('启动沙箱聊天失败: ' + error.message);
    }
  }
}