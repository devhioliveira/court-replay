// Court Replay System - Node.js/Express Server
import express from 'express';
import session from 'express-session';
import helmet from 'helmet';
import cors from 'cors';
import hpp from 'hpp';
import rateLimit from 'express-rate-limit';
import path from 'path';
import { fileURLToPath } from 'url';
import dotenv from 'dotenv';

import { config } from './config.js';
import { errorHandler, notFound } from './middleware/errorHandler.js';
import { requestLogger } from './middleware/requestLogger.js';
import { panelDisabled } from './middleware/maintenance.js';
import authRoutes from './routes/auth.js';
import apiRoutes from './routes/api.js';
import pageRoutes from './routes/pages.js';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Absolute paths: the server must not depend on the current working directory
// (systemd sets WorkingDirectory, Docker containers often do not).
export const PUBLIC_DIR = path.join(__dirname, '../public');
export const VIEWS_DIR = path.join(__dirname, '../views');

const app = express();

// Trust proxy must be configured explicitly when running behind nginx/traefik.
// When enabled, req.ip comes from X-Forwarded-For, so rate limiting keys on the
// real client IP instead of the proxy's. Only enable it behind a trusted proxy -
// otherwise clients can spoof X-Forwarded-For and bypass rate limits.
if (config.server.trustProxy) {
  app.set('trust proxy', config.server.trustProxy);
}

// Security middleware
app.use(helmet({
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      scriptSrc: ["'self'", "'unsafe-inline'"],
      styleSrc: ["'self'", "'unsafe-inline'"],
      imgSrc: ["'self'", "data:", "blob:"],
      mediaSrc: ["'self'", "blob:"],
      connectSrc: ["'self'"],
    },
  },
  crossOriginEmbedderPolicy: false,
}));

// CORS - restrictive
app.use(cors({
  origin: config.server.trustProxy ? true : false,
  credentials: true,
}));

// Prevent HTTP parameter pollution
app.use(hpp());

// Body parsing
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));

// Session
app.use(session({
  name: 'court.sid',
  secret: config.server.sessionSecret,
  resave: false,
  saveUninitialized: false,
  cookie: {
    secure: config.server.cookieSecure,
    httpOnly: true,
    sameSite: 'strict',
    maxAge: config.server.cookieMaxAge,
  },
}));

// Request logging
app.use(requestLogger);

// Rate limiting
const globalLimiter = rateLimit({
  windowMs: config.rateLimit.global.windowMs,
  limit: config.rateLimit.global.limit,
  standardHeaders: 'draft-7',
  legacyHeaders: false,
  message: { error: 'Too many requests, please try again later.' },
});
app.use(globalLimiter);

// Maintenance switch (DISABLE_PANEL=true): must come before static files and
// routes so that nothing from the panel is served while it is disabled.
app.use(panelDisabled);

// Static files
app.use(express.static(PUBLIC_DIR));

// Routes
app.use('/', pageRoutes);
app.use('/login', authRoutes);
app.use('/api', apiRoutes);

// Error handling
app.use(notFound);
app.use(errorHandler);

// Start server
const server = app.listen(config.server.port, config.server.host, () => {
  console.log(`[INFO] Court Replay Server running on http://${config.server.host}:${config.server.port}`);
  console.log(`[INFO] Environment: ${config.app.env}`);
  if (config.panel.disabled) {
    console.warn('[WARN] DISABLE_PANEL=true - panel is offline (maintenance page being served)');
  }
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('[INFO] SIGTERM received, shutting down gracefully');
  server.close(() => {
    console.log('[INFO] Server closed');
    process.exit(0);
  });
});

process.on('SIGINT', () => {
  console.log('[INFO] SIGINT received, shutting down gracefully');
  server.close(() => {
    console.log('[INFO] Server closed');
    process.exit(0);
  });
});

export default app;
