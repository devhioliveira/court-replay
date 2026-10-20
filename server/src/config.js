// Server configuration
import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';
import { readFileSync, existsSync } from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

dotenv.config();

// Load config.json if it exists, otherwise use defaults
const configPath = path.join(__dirname, '../../config.json');
let fileConfig = {};
if (existsSync(configPath)) {
  try {
    fileConfig = JSON.parse(readFileSync(configPath, 'utf-8'));
  } catch (e) {
    console.warn('[WARN] Failed to parse config.json, using defaults');
  }
}

export const config = {
  app: {
    name: 'Court Replay System',
    version: '1.0.0',
    env: process.env.NODE_ENV || fileConfig.app?.env || 'development',
  },
  server: {
    port: parseInt(process.env.NODE_PORT) || fileConfig.server?.port || 3000,
    host: process.env.NODE_HOST || fileConfig.server?.host || '0.0.0.0',
    trustProxy: process.env.TRUST_PROXY === 'true' || fileConfig.server?.trustProxy || false,
    sessionSecret: process.env.APP_SECRET || fileConfig.server?.sessionSecret || 'change-me-in-production',
    cookieSecure: process.env.COOKIE_SECURE === 'true' || fileConfig.server?.cookieSecure || false,
    cookieMaxAge: fileConfig.server?.cookieMaxAge || 86400000,
  },
  camera: {
    name: fileConfig.camera?.name || 'DAFU-CAMERA',
    ip: fileConfig.camera?.ip || '192.168.3.100',
  },
  buffer: {
    segmentSeconds: fileConfig.buffer?.segmentSeconds || 2,
    preEventSeconds: fileConfig.buffer?.preEventSeconds ?? 30,
    postEventSeconds: fileConfig.buffer?.postEventSeconds ?? 0,
  },
  storage: {
    basePath: fileConfig.storage?.basePath || './storage',
  },
  notebookAgent: {
    host: process.env.NOTEBOOK_HOST || fileConfig.notebookAgent?.host || '127.0.0.1',
    port: parseInt(process.env.NOTEBOOK_PORT) || fileConfig.notebookAgent?.port || 8765,
    timeout: fileConfig.notebookAgent?.timeout || 30000,
    sharedSecret: process.env.NOTEBOOK_SHARED_SECRET || fileConfig.notebookAgent?.sharedSecret || '',
  },
  security: {
    hmacAlgorithm: fileConfig.security?.hmacAlgorithm || 'sha256',
    timestampTolerance: fileConfig.security?.timestampTolerance || 300000,
  },
  auth: {
    // false = painel 100% público, sem login.
    // true  = exige login (usuario/senha) para acessar painel e API.
    enabled: process.env.AUTH_ENABLED === 'true' || fileConfig.auth?.enabled || false,
  },
  panel: {
    // true = painel fora do ar: exibe aviso de "temporariamente indisponivel"
    // (manutencao, ou quando o notebook/camera esta fora do lugar).
    // Nao afeta o agente: o botao do mouse continua gravando clips.
    disabled: process.env.DISABLE_PANEL === 'true' || fileConfig.panel?.disabled || false,
  },
  rateLimit: {
    global: fileConfig.rateLimit?.global || { windowMs: 900000, limit: 120 },
    login: fileConfig.rateLimit?.login || { windowMs: 900000, limit: 10 },
    trigger: fileConfig.rateLimit?.trigger || { windowMs: 60000, limit: 10 },
    download: fileConfig.rateLimit?.download || { windowMs: 60000, limit: 30 },
  },
  cleanup: fileConfig.cleanup || { enabled: true, hour: 0, minute: 0, timezone: 'America/Sao_Paulo' },
  logging: fileConfig.logging || { level: 'info', format: 'structured' },
};
