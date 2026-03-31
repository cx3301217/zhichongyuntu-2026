# 智充云图 - Zeabur 云端部署指南

本文档帮助你将智充云图项目部署到 Zeabur 云平台，让别人可以通过网页访问你的充电桩预测系统。

---

## 目录

1. [准备工作](#准备工作)
2. [上传代码到 GitHub](#上传代码到-github)
3. [部署到 Zeabur](#部署到-zeabur)
4. [配置高德地图 Key](#配置高德地图-key)
5. [常见问题](#常见问题)

---

## 准备工作

### 需要你拥有的账号

1. **GitHub 账号** - 用于存储代码
   - 注册地址: https://github.com

2. **Zeabur 账号** - 用于部署
   - 注册地址: https://zeabur.com
   - 推荐使用 GitHub 账号登录

### 检查你的电脑环境

1. 安装 Git（如果没有）：
   - 下载地址: https://git-scm.com/download/win
   - 安装时一路点"Next"即可

2. 检查是否已安装：打开命令提示符，输入：
   ```bash
   git --version
   ```
   如果显示版本号，说明已安装。

---

## 上传代码到 GitHub

### 步骤 1：创建 GitHub 仓库

1. 打开浏览器，访问 https://github.com
2. 登录你的 GitHub 账号
3. 点击右上角的 **+** 按钮 → **New repository**
4. 填写以下信息：
   - **Repository name**: `zhichongyuntu-2026`（仓库名称）
   - **Description**: `基于TFT的城市级新能源汽车充电桩网络服务拥挤度可视化信息系统`
   - **选择 Public**（公开仓库，Zeabur 才能访问）
5. 点击 **Create repository**

### 步骤 2：初始化本地 Git 仓库

打开命令提示符（PowerShell），依次执行：

```bash
# 进入项目目录
cd "c:\Users\27621\Desktop\智充云图"

# 初始化 Git 仓库
git init

# 添加所有文件（注意：node_modules 和 pycache 会被自动忽略）
git add .

# 提交代码
git commit -m "first commit - 智充云图项目"

# 重命名主分支为 main
git branch -M main

# 添加远程仓库（把 YOUR_USERNAME 换成你的 GitHub 用户名）
git remote add origin https://github.com/YOUR_USERNAME/zhichongyuntu-2026.git

# 推送代码到 GitHub
git push -u origin main
```

> **提示**: 执行 `git push` 时会让你登录 GitHub，按提示操作即可。

### 步骤 3：验证上传成功

刷新 GitHub 仓库页面，应该能看到所有文件了。

---

## 部署到 Zeabur

### 步骤 1：创建 Zeabur 项目

1. 打开浏览器，访问 https://zeabur.com
2. 点击 **Sign In**，使用 GitHub 账号登录
3. 登录后，点击 **New Project**
4. 输入项目名称：`zhichongyuntu-2026`
5. 点击 **Create**

### 步骤 2：添加后端服务

1. 在项目页面，点击 **Add Service**
2. 选择 **Deploy from GitHub**
3. 首次使用需要授权 GitHub 账号
4. 选择你刚创建的仓库 `zhichongyuntu-2026`
5. Zeabur 会自动检测到这是一个 Python + FastAPI 项目
6. 点击 **Deploy**

### 步骤 3：添加前端服务

1. 再次点击 **Add Service**
2. 选择 **Deploy from GitHub**
3. 选择同一个仓库 `zhichongyuntu-2026`
4. Zeabur 会自动检测到这是 React 前端
5. 点击 **Deploy**

### 步骤 4：等待部署完成

1. 部署过程可能需要 5-15 分钟
2. 后端会先部署完成
3. 前端会自动等待后端就绪后再部署
4. 部署成功后，每个服务旁边会显示绿色的 ✓

### 步骤 5：访问你的网站

1. 点击前端服务
2. 在 **Domains** 部分可以看到分配的域名
3. 格式类似：`https://zhichongyuntu-2026-xxxx.zeabur.app`
4. 点击域名即可访问你的网站

> **恭喜！** 你的网站现在可以通过这个链接访问了！

---

## 配置高德地图 Key

### 为什么需要配置？

系统使用高德地图显示深圳地图，默认使用的是开发 Key，有访问限制。

### 获取自己的高德地图 Key

1. 访问 https://console.amap.com/dev/key/app
2. 登录高德开放平台
3. 点击 **创建应用**
4. 应用名称：`智充云图`
5. 类型：Web端
6. 添加 Key：
   - Key 名称：`Web端Key`
   - 服务类型：`JavaScript API` + `Web服务`
   - 域名白名单：可以留空或填 `*`

### 在 Zeabur 中配置

1. 在 Zeabur 项目中，点击后端服务
2. 进入 **Environment Variables**
3. 添加以下变量：

```
REACT_APP_AMAP_KEY = 你的新Key
REACT_APP_AMAP_SECURITY_KEY = 你的新安全密钥
REACT_APP_AMAP_WEB_SERVICE_KEY = 你的新Web服务Key
```

4. 点击 **Redeploy** 重新部署

---

## 常见问题

### Q1: 部署失败怎么办？

1. 点击失败的服务，查看日志
2. 常见问题：
   - **依赖安装失败**: 检查 requirements.txt 或 package.json 是否正确
   - **端口冲突**: 确保配置的端口与代码中一致
   - **模型文件过大**: GitHub 对单文件有 100MB 限制，模型文件约 200MB 可能需要特殊处理

### Q2: 部署成功但页面空白？

1. 检查浏览器控制台（F12）是否有错误
2. 常见问题：
   - **API 请求失败**: 检查后端是否正常运行
   - **跨域问题**: 确保后端 CORS 已配置（代码中已配置）
   - **高德地图 Key 无效**: 重新配置 Key

### Q3: 如何更新代码？

1. 在本地修改代码
2. 执行：
   ```bash
   git add .
   git commit -m "更新说明"
   git push
   ```
3. Zeabur 会自动检测到更新并重新部署

### Q4: 费用问题

- **免费额度**: Zeabur 提供免费额度，足够个人项目和小比赛演示使用
- **如果额度用完**: 可以考虑使用其他免费平台

---

## 项目已完成的配置

以下文件已为你准备好，无需再修改：

- ✅ `zeabur.toml` - Zeabur 部署配置
- ✅ `.env.example` - 环境变量示例
- ✅ `frontend/src/utils/config.js` - 已支持环境变量

---

## 技术支持

如果部署过程中遇到问题，可以：
1. 查看 Zeabur 官方文档: https://zeabur.com/docs
2. 查看项目 README.md
3. 检查服务日志获取错误信息

---

祝你部署成功！比赛加油！ 🚀
