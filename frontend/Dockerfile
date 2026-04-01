# frontend/Dockerfile
# 自定义构建脚本，绕过 Zeabur 自动生成的 npm update -g npm 步骤
FROM node:22-alpine AS builder

WORKDIR /app

# 复制 package 文件（利用 Docker 缓存层）
COPY package.json package-lock.json ./
RUN npm ci --legacy-peer-deps

# 复制源码
COPY public/ ./public/
COPY src/ ./src/

# 构建（设置环境变量防 OOM 和 CI 严格模式）
ENV CI=false
ENV GENERATE_SOURCEMAP=false
ENV NODE_OPTIONS=--max_old_space_size=512

RUN npm run build

# 生产镜像：使用轻量 web 服务器
FROM node:22-alpine

RUN npm install -g serve

WORKDIR /app

COPY --from=builder /app/build ./build

EXPOSE 3000

CMD ["serve", "-s", "build", "-l", "3000"]
