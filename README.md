# 供应商合同自动化 Demo

SaaS / API 供应商分销协议 · 从申请到可签 · 全流程可追溯

一个可试运行的内部小工具，把「供应商申请 → 信息校验 → 补 Schedule A → 生成合同草稿 → 双人审批 → 可发签 → Mock 签署 → 归档」这条链路变成一个可点、可卡、可追溯的流程。

---

## 一、Demo 场景

- **合同类型**：SaaS / API 产品供应商分销协议
- **模拟供应商**：Singapore Cloud Pte Ltd（新加坡）
- **产品**：API 数据服务
- **商务条款**：平台 70% / 供应商 30%，月结 30 天，供应商承担退款、供应商开票
- **签字人**：张三（COO）
- **内部审批人**：Legal_Alice（法务）、CEO_Bob（CEO）

---

## 二、核心功能

### 1. 状态机（11 个状态）

主状态：`Draft → Needs Information → Under Review → Approved to Send → Sent for Signature → Signed → Active`

异常状态：`Returned`、`Declined`、`Expired`、`Signed_Unpaid`

每次状态变更都写日志，前端可实时看到当前状态与当前负责人。

### 2. Schedule A 校验与阻断

- 结构化字段覆盖：供应商主体、产品/服务、商业条款、签字人信息。
- 关键字段（分成比例、收入口径、退款责任、签约主体等）缺失时：
  - 状态变 `Needs Information`
  - 「批准发签」被阻断
  - 明确列出缺失字段

### 3. 合同版本号

- 任意字段变更都触发版本 +1。
- 版本变化时旧审批自动失效。
- 保留每次版本快照。

### 4. 串行审批

- 两位审批人：法务先批，CEO 后批。
- 两人必须审批**同一版本**才能进入 `Approved to Send`。
- 法务退回 → 状态变 `Returned`，CEO 不能批。
- 修改合同后版本 +1，重新走审批。

### 5. 操作日志

记录谁在何时提交、修改、审批、退回、发签、签署，全程可查。

### 6. Mock 电子签

- 只有 `Approved to Send` 才能发起签署。
- 支持模拟签署完成 / 拒签 / 过期。
- 签署完成后展示应归档的 5 项证据：合同预览、审批记录、签署证书、Schedule A、操作日志。

---

## 三、技术栈

| 层 | 选型 |
|---|---|
| 后端 | Python + FastAPI |
| 数据库 | SQLite（本地文件） |
| 前端 | 原生 HTML + JS（单页多视图） |
| 部署 | Render |
| 电子签 | Mock |
| 付款 / 邮件 | Mock |

---

## 四、本地运行 
```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动服务
uvicorn app.main:app --reload --port 8000

# 3. 浏览器打开
http://127.0.0.1:8000/


##五、真实实现 vs Mock 边界

✅ 真实实现
供应商申请表单录入

11 状态机与状态流转

Schedule A 结构化字段与必填校验

缺失字段阻断发签

合同版本号与版本快照

修改后旧审批自动失效

双人串行审批（同版本）

合同草稿 HTML 预览

审批记录 / 版本历史 / 操作日志

归档证据清单

🔶 Mock 部分
电子签（签署、拒签、过期均为按钮模拟）

付款结算

邮件通知

营业执照 OCR

供应商外部登录

##六、测试路径（建议按顺序）
打开链接 → 「新建合同」→ 直接点「创建合同」（表单已预填模拟数据）

「提交申请」→ 状态变 Under Review

先点「CEO 审批通过」→ 按钮为灰色，不可点（串行规则）

点「法务审批通过」→ CEO 按钮变亮

点「CEO 审批通过」→ 状态变 Approved to Send

「发起签署」→ 状态变 Sent for Signature

「模拟签署完成」→ 状态变 Active

查看「合同预览」「审批记录」「版本历史」「操作日志」「归档证据」

演示版本变更与审批失效
新建合同 → 提交 → 法务退回

在「修改合同」卡片中改分成比例 → 提交修改

版本 V1 → V2，旧审批全部失效

重新提交 → 重新走法务 → CEO 审批

演示阻断
新建合同 → 把「退款处理」字段清空 → 创建

提交申请 → 状态变 Needs Information，列出缺失字段

补齐后才能进入审批

##七、项目结构
text
vendor-contract-automation/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 审批人配置
│   ├── db.py                # SQLite 连接与建表
│   ├── state_machine.py     # 状态机
│   ├── validation.py        # Schedule A 校验
│   ├── versioning.py        # 版本号与快照
│   ├── approval.py          # 串行审批
│   ├── audit.py             # 操作日志
│   ├── signature.py         # Mock 电子签
│   ├── routes.py            # API 路由
│   └── static/
│       └── index.html       # 前端单页
├── tests/                   # 单元测试
│   ├── test_state_machine.py
│   ├── test_validation.py
│   ├── test_versioning.py
│   ├── test_approval.py
│   ├── test_audit.py
│   └── test_signature.py
├── requirements.txt
├── render.yaml
└── README.md


##八、已知限制

使用 SQLite 存储，Render 免费版重启后数据会重置。面试演示时重新走一遍流程即可。

电子签、付款、邮件为 Mock，接真实接口时替换对应模块即可。

Render 免费版有冷启动，首次访问可能需要 10~30 秒。